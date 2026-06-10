"""Radar Clusters grouping and analysis report synthesis service."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from config import Config
from database import db_session, new_id, row_to_dict, rows_to_dicts, utc_now
from services.openai_service import AzureOpenAIService
from services.signal_pipeline import (
    _resolve_taste_profile,
    _cosine_similarity,
    _parse_embedding,
    run_extract_contents,
    persist_content_updates,
    research,
    _clean_brief_text,
    parse_and_clean_brief,
    load_user_settings
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM Prompts
# ---------------------------------------------------------------------------

CLUSTER_VALIDATION_PROMPT_TEMPLATE = """You are organizing RSS articles into meaningful topic clusters for an intelligence briefing product.

The user's Taste Profile is:

\"\"\"
{taste_profile}
\"\"\"

You are given a candidate group of articles. Decide whether these articles form a real cluster. A real cluster means they are about the same story, topic, product shift, market debate, company move, technical pattern, or ecosystem change. Do not force a cluster just because the articles share broad words like AI, startup, cloud, chips, or productivity.

Candidate articles:

\"\"\"
{articles_list}
\"\"\"

Return only valid JSON with this shape:

{{
  "is_real_cluster": true,
  "title": "Short specific cluster title",
  "summary": "One or two plain sentences explaining what connects these articles.",
  "topic_key": "short-stable-slug",
  "confidence": 0.0,
  "reject_reason": null
}}

Rules:
- If the connection is weak, set "is_real_cluster" to false.
- The title should be specific, not generic. Bad: "AI News". Good: "OpenAI's enterprise push meets reliability concerns".
- The summary should explain the actual relationship between the articles.
- The topic_key should be lowercase, hyphenated, and stable enough that future related articles could map to it.
- confidence must be between 0 and 1.
"""

CLUSTER_REPORT_PROMPT_TEMPLATE = """You are a top-tier analyst writing a focused intelligence report from a cluster of related RSS articles.

The user's Taste Profile is:

\"\"\"
{taste_profile}
\"\"\"

Cluster title:

\"\"\"
{cluster_title}
\"\"\"

Cluster description:

\"\"\"
{cluster_summary}
\"\"\"

Articles in this cluster:

\"\"\"
{articles_contents_str}
\"\"\"

Background Research:

\"\"\"
{research_brief}
\"\"\"

Your task:
Write a thorough analysis of this cluster. This is not a summary of each article. It is a synthesis across multiple sources and takes.

Instructions:
1. Start by explaining what this cluster is actually about in plain language.
2. Identify what changed, what is newly visible, or why this topic matters now.
3. Compare the articles. Explain where they agree, where they disagree, and what each source notices that the others miss.
4. Separate signal from noise. Call out claims that seem overstated, weakly supported, or mostly narrative.
5. Explain the incentives, constraints, technical tradeoffs, business mechanics, ecosystem shifts, or second-order effects that matter.
6. If the evidence is thin, say so. Do not manufacture certainty.
7. Include inline Markdown links when referencing specific articles.
8. Do not group all sources at the end.
9. Use clean prose. Avoid bullet points unless a short watch-list genuinely helps.
10. Do not use em dashes.
11. Do not write a generic conclusion. End with what the reader should watch next if there is something concrete to watch.

Output format:
- Markdown.
- First line must be an H1 title starting with "# ".
- Use "##" section headings.
- Include a section called "## What the sources collectively show".
- Include a section called "## Where the tension is".
- Include a section called "## What to watch next" only if there are concrete next indicators.
"""

REPORT_TITLE_CLEANUP_PROMPT_TEMPLATE = """Extract a short report title from this Markdown report.

Return only valid JSON:

{{
  "title": "Short title"
}}

Report:

\"\"\"
{report_content}
\"\"\"
"""

# ---------------------------------------------------------------------------
# Formatting Helpers
# ---------------------------------------------------------------------------

def format_articles_for_validation(items: list[dict[str, Any]]) -> str:
    """Format candidate feed items for Prompt 1 cluster validation."""
    out = ""
    for item in items:
        pub = item.get("published_at") or item.get("first_seen_at")
        out += (
            f"ID: {item['id']}\n"
            f"Title: {item['title']}\n"
            f"Feed: {item.get('feed_title') or 'Unknown'}\n"
            f"Published: {pub}\n"
            f"Summary: {item.get('summary') or 'No summary'}\n"
            f"---\n"
        )
    return out


def _build_articles_contents_str(selected_items: list[dict[str, Any]]) -> str:
    """Build the prompt content string for synthesizing cluster articles."""
    out = ""
    from services.signal_pipeline import truncate_article_content
    for idx, item in enumerate(selected_items):
        truncated = truncate_article_content(item.get("content"))
        out += (
            f"ARTICLE {idx + 1}:\n"
            f"ID: {item['id']}\n"
            f"Title: {item['title']}\n"
            f"Feed: {item.get('feed_title') or 'Unknown'}\n"
            f"URL: {item['url']}\n"
            f"Content:\n{truncated}\n====================\n"
        )
    return out


# ---------------------------------------------------------------------------
# Core Service Logic
# ---------------------------------------------------------------------------

def archive_stale_clusters(conn: Any, user_id: str) -> int:
    """Auto-archive active clusters with no new items for CLUSTER_ARCHIVE_AFTER_DAYS."""
    lookback_days = Config.CLUSTER_ARCHIVE_AFTER_DAYS
    cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
    
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE signal_clusters
        SET status = 'archived', updated_at = ?
        WHERE user_id = ? AND status = 'active'
          AND datetime(last_seen_at) < datetime(?)
        """,
        (utc_now(), user_id, cutoff),
    )
    return cursor.rowcount


def refresh_clusters(user_id: str) -> dict[str, Any]:
    """Load candidates, compute groupings, name clusters via LLM, and upsert."""
    # 1. Load candidate items that lack a cluster
    with db_session() as conn:
        lookback_val = f"-{Config.CLUSTER_LOOKBACK_DAYS} days"
        rows = conn.execute(
            """
            SELECT i.id, i.url, i.title, i.summary, i.content, i.content_format,
                   i.embedding, i.published_at, i.first_seen_at, i.feed_id,
                   f.title AS feed_title, f.site_url AS feed_site_url
            FROM feed_items i
            JOIN feeds f ON f.id = i.feed_id AND f.user_id = i.user_id
            LEFT JOIN bookmarks b ON b.user_id = i.user_id AND b.url = i.url
            LEFT JOIN signal_cluster_items sci ON sci.feed_item_id = i.id
            WHERE i.user_id = ?
              AND i.status != 'saved'
              AND b.id IS NULL
              AND sci.cluster_id IS NULL
              AND datetime(COALESCE(i.published_at, i.first_seen_at)) >= datetime('now', ?)
            ORDER BY COALESCE(i.published_at, i.first_seen_at) DESC
            LIMIT ?
            """,
            (user_id, lookback_val, Config.CLUSTER_MAX_CANDIDATES),
        ).fetchall()
        candidate_items = [dict(r) for r in rows]

    if not candidate_items:
        return {"created": 0, "updated": 0, "archived": 0}

    # 2. Backfill missing embeddings outside long database transaction
    embeds_generated = 0
    for item in candidate_items:
        parsed_embed = _parse_embedding(item["embedding"])
        if parsed_embed is None:
            if embeds_generated >= Config.CLUSTER_EMBED_MAX_PER_RUN:
                continue
            text_to_embed = item["title"]
            if item["summary"]:
                text_to_embed += "\n" + item["summary"]
            try:
                embedding_vec = AzureOpenAIService.generate_embedding(text_to_embed)
                with db_session() as conn:
                    conn.execute(
                        "UPDATE feed_items SET embedding = ?, updated_at = ? WHERE id = ?",
                        (json.dumps(embedding_vec), utc_now(), item["id"]),
                    )
                item["embedding"] = embedding_vec
                embeds_generated += 1
            except Exception as exc:
                logger.error(f"Failed to generate embedding for item {item['id']}: {exc}")

    # 3. Load active clusters in memory to compute assignments
    with db_session() as conn:
        archived_count = archive_stale_clusters(conn, user_id)
        
        active_rows = conn.execute(
            "SELECT * FROM signal_clusters WHERE user_id = ? AND status = 'active'",
            (user_id,)
        ).fetchall()
        active_clusters = rows_to_dicts(active_rows)

        in_memory_clusters = []
        for c in active_clusters:
            item_embeddings = []
            source_feeds = set()
            existing_items = conn.execute(
                """
                SELECT i.id, i.feed_id, i.embedding
                FROM feed_items i
                JOIN signal_cluster_items sci ON sci.feed_item_id = i.id
                WHERE sci.cluster_id = ?
                """,
                (c["id"],)
            ).fetchall()
            for item in existing_items:
                vec = _parse_embedding(item["embedding"])
                if vec:
                    item_embeddings.append(vec)
                source_feeds.add(item["feed_id"])

            in_memory_clusters.append({
                "id": c["id"],
                "title": c["title"],
                "summary": c["summary"],
                "topic_key": c["topic_key"],
                "centroid": _parse_embedding(c["centroid_embedding"]) or [],
                "item_embeddings": item_embeddings,
                "source_feeds": source_feeds,
                "existing_items_count": len(existing_items),
                "first_seen_at": c["first_seen_at"],
                "last_seen_at": c["last_seen_at"],
                "is_new": False,
                "new_items_to_add": [],  # list of tuples (item_id, relevance_score, item)
                "dirty": False
            })

    # Filter candidates to only those with embeddings
    valid_candidates = []
    for item in candidate_items:
        vec = _parse_embedding(item["embedding"])
        if vec:
            item["embedding_vec"] = vec
            valid_candidates.append(item)

    # Sort newest first
    valid_candidates.sort(key=lambda x: x.get("published_at") or x.get("first_seen_at") or "", reverse=True)

    # 4. Greedy clustering logic
    for item in valid_candidates:
        item_embed = item["embedding_vec"]
        best_sim = -1.0
        best_cluster = None

        for cl in in_memory_clusters:
            if not cl["centroid"]:
                continue
            sim = _cosine_similarity(item_embed, cl["centroid"])
            if sim > best_sim:
                best_sim = sim
                best_cluster = cl

        if best_sim >= Config.CLUSTER_SIMILARITY_THRESHOLD:
            best_cluster["new_items_to_add"].append((item["id"], best_sim, item))
            best_cluster["item_embeddings"].append(item_embed)
            best_cluster["source_feeds"].add(item["feed_id"])
            
            item_ts = item.get("published_at") or item.get("first_seen_at")
            if item_ts and (not best_cluster["last_seen_at"] or item_ts > best_cluster["last_seen_at"]):
                best_cluster["last_seen_at"] = item_ts
                
            num_embeds = len(best_cluster["item_embeddings"])
            if num_embeds > 0:
                dim = len(item_embed)
                new_centroid = [sum(v[i] for v in best_cluster["item_embeddings"]) / num_embeds for i in range(dim)]
                best_cluster["centroid"] = new_centroid
            best_cluster["dirty"] = True
        else:
            item_ts = item.get("published_at") or item.get("first_seen_at")
            new_cl = {
                "id": None,
                "title": None,
                "summary": None,
                "topic_key": None,
                "centroid": item_embed,
                "item_embeddings": [item_embed],
                "source_feeds": {item["feed_id"]},
                "first_seen_at": item_ts,
                "last_seen_at": item_ts,
                "is_new": True,
                "new_items_to_add": [(item["id"], 1.0, item)],
                "dirty": True
            }
            in_memory_clusters.append(new_cl)

    # Filter newly proposed clusters with at least CLUSTER_MIN_ARTICLES (default 5)
    candidate_new_clusters = [
        cl for cl in in_memory_clusters 
        if cl["is_new"] and len(cl["new_items_to_add"]) >= Config.CLUSTER_MIN_ARTICLES
    ]

    # 5. Validate new cluster candidates via LLM (outside long db transaction)
    with db_session() as conn:
        user_row = conn.execute("SELECT taste_profile FROM users WHERE id = ?", (user_id,)).fetchone()
        taste_profile = _resolve_taste_profile(user_row)

    validated_new_clusters = []
    for new_cl in candidate_new_clusters:
        items_list = [t[2] for t in new_cl["new_items_to_add"]]
        articles_list_str = format_articles_for_validation(items_list)
        prompt = CLUSTER_VALIDATION_PROMPT_TEMPLATE.format(
            taste_profile=taste_profile,
            articles_list=articles_list_str
        )
        
        try:
            client, model = AzureOpenAIService.get_signal_chat_client_and_model()
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful analyst assistant. You always respond in valid JSON format."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            result = json.loads(response.choices[0].message.content)
            is_real = result.get("is_real_cluster", False)
            confidence = result.get("confidence", 0.0)
            
            # Reject if not real, low confidence, or too few articles
            if is_real and confidence >= 0.65 and len(new_cl["new_items_to_add"]) >= Config.CLUSTER_MIN_ARTICLES:
                new_cl["title"] = result.get("title") or "Unnamed Cluster"
                new_cl["summary"] = result.get("summary")
                new_cl["topic_key"] = result.get("topic_key")
                validated_new_clusters.append(new_cl)
        except Exception as exc:
            logger.error(f"Failed to validate cluster candidate: {exc}")

    # 6. Open short transaction to persist updates and new clusters
    created_count = 0
    updated_count = 0

    with db_session() as conn:
        # A. Update existing active clusters
        for cl in in_memory_clusters:
            if not cl["is_new"] and cl["dirty"]:
                centroid_str = json.dumps(cl["centroid"])
                article_count = cl["existing_items_count"] + len(cl["new_items_to_add"])
                source_count = len(cl["source_feeds"])
                conn.execute(
                    """
                    UPDATE signal_clusters
                    SET centroid_embedding = ?,
                        article_count = ?,
                        source_count = ?,
                        last_seen_at = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (centroid_str, article_count, source_count, cl["last_seen_at"], utc_now(), cl["id"]),
                )
                for item_id, rel_score, _ in cl["new_items_to_add"]:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO signal_cluster_items (cluster_id, feed_item_id, relevance_score, added_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (cl["id"], item_id, rel_score, utc_now()),
                    )
                updated_count += 1

        # B. Insert newly validated clusters
        for new_cl in validated_new_clusters:
            cluster_id = new_id()
            now_ts = utc_now()
            centroid_str = json.dumps(new_cl["centroid"])
            article_count = len(new_cl["item_embeddings"])
            source_count = len(new_cl["source_feeds"])
            
            conn.execute(
                """
                INSERT INTO signal_clusters (
                    id, user_id, title, summary, topic_key, centroid_embedding,
                    status, article_count, source_count, first_seen_at, last_seen_at,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?)
                """,
                (
                    cluster_id, user_id, new_cl["title"], new_cl["summary"], new_cl["topic_key"], centroid_str,
                    article_count, source_count, new_cl["first_seen_at"], new_cl["last_seen_at"],
                    now_ts, now_ts
                ),
            )
            
            for item_id, rel_score, _ in new_cl["new_items_to_add"]:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO signal_cluster_items (cluster_id, feed_item_id, relevance_score, added_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (cluster_id, item_id, rel_score, now_ts),
                )
            created_count += 1

    return {"created": created_count, "updated": updated_count, "archived": archived_count}


def extract_report_title(report_content: str) -> str:
    """Fallback helper to extract a short report title via Prompt 3."""
    title, _ = parse_and_clean_brief(report_content)
    if title:
        return title
        
    prompt = REPORT_TITLE_CLEANUP_PROMPT_TEMPLATE.format(report_content=report_content)
    try:
        client, model = AzureOpenAIService.get_signal_chat_client_and_model()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful analyst assistant. You always respond in valid JSON format."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        res_data = json.loads(response.choices[0].message.content)
        return res_data.get("title", "Cluster Analysis Report")
    except Exception as exc:
        logger.error(f"Failed to extract title using Prompt 3: {exc}")
        return "Cluster Analysis Report"


def generate_cluster_report(user_id: str, cluster_id: str) -> dict[str, Any]:
    """Execute full content extraction, optional web search, synthesis, and persist report."""
    # 1. Load user settings and verify cluster ownership
    with db_session() as conn:
        settings = load_user_settings(
            conn,
            user_id,
            default_filter_template="",
            default_synthesis_template=""
        )
        
        cluster_row = conn.execute(
            "SELECT * FROM signal_clusters WHERE id = ? AND user_id = ?",
            (cluster_id, user_id)
        ).fetchone()
        
        if not cluster_row:
            raise ValueError("Cluster not found or not owned by user")
            
        cluster = row_to_dict(cluster_row)

        # Load clustered feed items
        item_rows = conn.execute(
            """
            SELECT i.id, i.url, i.title, i.summary, i.content, i.content_format,
                   i.published_at, i.first_seen_at, i.feed_id,
                   f.title AS feed_title, f.site_url AS feed_site_url
            FROM feed_items i
            JOIN feeds f ON f.id = i.feed_id AND f.user_id = i.user_id
            JOIN signal_cluster_items sci ON sci.feed_item_id = i.id
            WHERE sci.cluster_id = ?
            ORDER BY sci.relevance_score DESC, COALESCE(i.published_at, i.first_seen_at) DESC
            LIMIT ?
            """,
            (cluster_id, Config.CLUSTER_MAX_SYNTHESIS_ARTICLES)
        ).fetchall()
        cluster_items = [dict(r) for r in item_rows]

    if not cluster_items:
        raise ValueError("No articles found in this cluster")

    # 2. Extract full content for any items lacking it (outside write transaction)
    updates = run_extract_contents(cluster_items)
    with db_session() as conn:
        persist_content_updates(conn, updates)

    # 3. Optional web research grounding
    research_brief, _ = research(
        cluster_items,
        web_search_enabled=settings["web_search_enabled"]
    )

    # 4. Synthesize cluster report
    articles_contents_str = _build_articles_contents_str(cluster_items)
    synthesis_prompt = CLUSTER_REPORT_PROMPT_TEMPLATE.format(
        taste_profile=settings["taste_profile"],
        cluster_title=cluster["title"],
        cluster_summary=cluster["summary"] or "",
        articles_contents_str=articles_contents_str,
        research_brief=research_brief,
    )
    
    system_content = "You are a thoughtful industry analyst writing briefings for a CEO. Always write in clean prose and format in Markdown."
    
    raw_content = AzureOpenAIService.generate_brief_with_verbosity(
        synthesis_prompt, system_content, verbosity="high"
    )
    cleaned_content = _clean_brief_text(raw_content)

    # 5. Extract/clean report title
    title = extract_report_title(cleaned_content)
    _, final_content = parse_and_clean_brief(cleaned_content)

    # 6. Save report and update cluster timestamp in a short transaction
    report_id = new_id()
    now_ts = utc_now()
    
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO signal_cluster_reports (
                id, cluster_id, user_id, title, content, article_count, source_count, generated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                cluster_id,
                user_id,
                title,
                final_content,
                len(cluster_items),
                len({item["feed_id"] for item in cluster_items}),
                now_ts
            )
        )
        
        conn.execute(
            """
            UPDATE signal_clusters
            SET last_report_generated_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (now_ts, now_ts, cluster_id)
        )

    # Return serialized report
    return {
        "id": report_id,
        "cluster_id": cluster_id,
        "user_id": user_id,
        "title": title,
        "content": final_content,
        "article_count": len(cluster_items),
        "source_count": len({item["feed_id"] for item in cluster_items}),
        "generated_at": now_ts
    }
