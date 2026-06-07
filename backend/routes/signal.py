"""Signal routes."""
from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Blueprint, Response, g, jsonify, request, stream_with_context

from config import Config
from database import get_db, new_id, utc_now, row_to_dict, rows_to_dicts
from middleware.auth import require_auth
from services.openai_service import AzureOpenAIService
from services.content_extractor import ContentExtractor

logger = logging.getLogger(__name__)

signal_bp = Blueprint("signal", __name__)

DEFAULT_TASTE_PROFILE = (
    "I want analysis, not summaries. Focus on what actually changed, why it matters, "
    "and what intelligent operators or practitioners would notice beneath the surface narrative. "
    "Prioritize strategic implications, incentives, product direction, business mechanics, "
    "technical tradeoffs, ecosystem shifts, and second-order effects over announcements, benchmarks, "
    "or hype cycles.\n\n"
    "Do not spend time on raw metrics unless they materially change the interpretation of the story. "
    "A benchmark result is only useful if it signals something broader about capability, economics, "
    "adoption, market positioning, infrastructure shifts, or competitive dynamics.\n\n"
    "I care more about why a company is doing something, what constraints they are reacting to, "
    "what hidden incentives exist, what operational realities shape decisions, and what long-term pattern "
    "this might represent.\n\n"
    "The taste profile should also act as an aggressive filtering layer before deep analysis happens. "
    "If a piece of content does not appear aligned with these priorities, the system should discard it "
    "early instead of wasting time processing or summarizing it. Articles that are mostly incremental news, "
    "engagement bait, shallow commentary, repetitive benchmark coverage, marketing fluff, or low-information "
    "reactions should be skipped entirely. The system should spend its reasoning budget only on material "
    "that contains meaningful insight, strategic relevance, operational lessons, novel perspectives, "
    "or evidence of important shifts.\n\n"
    "Surface disagreements when they reveal competing mental models or conflicting incentives. "
    "Highlight when insiders and outsiders appear to view a situation differently. Point out hidden "
    "assumptions that the article or discussion relies on. Explain what people may be misunderstanding "
    "or overlooking.\n\n"
    "Write in clean, direct prose using simple language with high insight density. Avoid bullet points, "
    "excessive formatting, motivational language, corporate jargon, and AI-sounding phrasing. "
    "Do not use em dashes. The writing should feel like a thoughtful analyst briefing a smart founder "
    "or CEO at the end of the day.\n\n"
    "Do not try to sound impressive. Be precise, skeptical, grounded, and useful."
)

@signal_bp.route("/taste-profile", methods=["GET"])
@require_auth
def get_taste_profile():
    conn = get_db()
    row = conn.execute("SELECT taste_profile FROM users WHERE id = ?", (g.user.id,)).fetchone()
    profile = row["taste_profile"] if row else None
    if not profile or not profile.strip():
        profile = DEFAULT_TASTE_PROFILE
    return jsonify({"taste_profile": profile})

@signal_bp.route("/taste-profile", methods=["PUT"])
@require_auth
def update_taste_profile():
    data = request.get_json() or {}
    profile = data.get("taste_profile", "").strip()
    conn = get_db()
    conn.execute(
        "UPDATE users SET taste_profile = ?, updated_at = ? WHERE id = ?",
        (profile, utc_now(), g.user.id)
    )
    conn.commit()
    return jsonify({"success": True, "taste_profile": profile or DEFAULT_TASTE_PROFILE})

@signal_bp.route("/briefs", methods=["GET"])
@require_auth
def list_briefs():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM signal_briefs WHERE user_id = ? ORDER BY created_at DESC",
        (g.user.id,)
    ).fetchall()
    return jsonify({"briefs": rows_to_dicts(rows)})

@signal_bp.route("/briefs", methods=["POST"])
@require_auth
def generate_brief():
    conn = get_db()
    
    # 1. Load taste profile
    user_row = conn.execute("SELECT taste_profile FROM users WHERE id = ?", (g.user.id,)).fetchone()
    taste_profile = user_row["taste_profile"] if user_row else None
    if not taste_profile or not taste_profile.strip():
        taste_profile = DEFAULT_TASTE_PROFILE

    # 2. Fetch RSS feed items (latest N unread/new)
    candidate_limit = Config.SIGNAL_CANDIDATE_LIMIT
    unread_rows = conn.execute(
        """
        SELECT i.id, i.url, i.title, i.summary, f.title as feed_title
        FROM feed_items i
        JOIN feeds f ON f.id = i.feed_id AND f.user_id = i.user_id
        LEFT JOIN bookmarks b ON b.user_id = i.user_id AND b.url = i.url
        WHERE i.user_id = ? AND i.status = 'new' AND b.id IS NULL
        ORDER BY COALESCE(i.published_at, i.first_seen_at) DESC
        LIMIT ?
        """,
        (g.user.id, candidate_limit)
    ).fetchall()
    
    items = [dict(r) for r in unread_rows]
    
    # Fallback to recent items if unread is too small
    if len(items) < 10:
        recent_rows = conn.execute(
            """
            SELECT i.id, i.url, i.title, i.summary, f.title as feed_title
            FROM feed_items i
            JOIN feeds f ON f.id = i.feed_id AND f.user_id = i.user_id
            LEFT JOIN bookmarks b ON b.user_id = i.user_id AND b.url = i.url
            WHERE i.user_id = ? AND i.status != 'saved' AND b.id IS NULL
              AND datetime(COALESCE(i.published_at, i.first_seen_at)) >= datetime('now', '-5 days')
            ORDER BY COALESCE(i.published_at, i.first_seen_at) DESC
            LIMIT ?
            """,
            (g.user.id, candidate_limit)
        ).fetchall()
        existing_ids = {item["id"] for item in items}
        for r in recent_rows:
            if r["id"] not in existing_ids:
                items.append(dict(r))
                existing_ids.add(r["id"])

    if not items:
        return jsonify({
            "success": False,
            "reason": "no_content",
            "message": "No recent RSS feed content found to analyze. Try adding some feeds first in the Radar tab!"
        }), 200

    # 3. LLM Step 1: Filter articles based on Taste Profile
    articles_list_str = ""
    for idx, item in enumerate(items):
        articles_list_str += f"ID: {item['id']}\nTitle: {item['title']}\nFeed: {item['feed_title']}\nSummary: {item['summary'] or 'No summary'}\n---\n"

    filter_prompt = f"""You are an expert analyst assistant. You are given a list of recent articles from followed RSS feeds. Your task is to filter this list aggressively to identify only the articles that align with the user's Taste Profile.

User's Taste Profile:
\"\"\"
{taste_profile}
\"\"\"

Recent RSS Articles:
\"\"\"
{articles_list_str}
\"\"\"

Task:
Select the articles that contain genuine insight, strategic relevance, ecosystem shifts, product directions, or important second-order implications. Skip incremental news, announcements, engagement bait, benchmark hype, or repetitive coverage.
Discard any articles that do not align with the priorities.

Return a JSON object containing a single key "selected_ids" mapping to an array of string IDs of the chosen articles.
Return ONLY valid JSON.
"""

    selected_ids = []
    try:
        client, model = AzureOpenAIService.get_signal_chat_client_and_model()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful analyst assistant. You always respond in valid JSON format."},
                {"role": "user", "content": filter_prompt}
            ],
            response_format={"type": "json_object"}
        )
        selected_data = json.loads(response.choices[0].message.content)
        selected_ids = selected_data.get("selected_ids", [])
    except Exception as exc:
        logger.error(f"Error in signal filtering LLM call: {exc}")
        # If filtering fails, fallback to selecting up to the latest 10 items
        selected_ids = [item["id"] for item in items[:10]]

    # Cap to top 15 items to process
    selected_ids = selected_ids[:15]
    selected_items = [item for item in items if item["id"] in selected_ids]

    if not selected_items:
        return jsonify({
            "success": False,
            "reason": "no_high_signal_content",
            "message": "We analyzed recent feeds, but none of them matched your Taste Profile. Adjust your profile or add more high-quality feeds!"
        }), 200

    # 4. Extract content for selected items in parallel
    updates = []
    def ensure_content(item):
        item_id = item["id"]
        from database import db_session
        with db_session() as thread_conn:
            cached_row = thread_conn.execute("SELECT content, content_format FROM feed_items WHERE id = ?", (item_id,)).fetchone()
            if cached_row and cached_row["content"] and cached_row["content"].strip():
                return (item_id, cached_row["content"], cached_row["content_format"], False)
        
        try:
            extracted = ContentExtractor.extract(item["url"])
            content = extracted.get("content")
            if content and content.strip():
                content_format = extracted.get("content_format") or "markdown"
                return (item_id, content, content_format, True)
        except Exception as exc:
            logger.error(f"Failed content extraction during signal generation for {item['url']}: {exc}")
        return None

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(ensure_content, item) for item in selected_items]
        for fut in futures:
            res = fut.result()
            if res:
                item_id, content, content_format, needs_update = res
                for item in selected_items:
                    if item["id"] == item_id:
                        item["content"] = content
                        item["content_format"] = content_format
                if needs_update:
                    updates.append((item_id, content, content_format))

    if updates:
        for item_id, content, content_format in updates:
            conn.execute(
                "UPDATE feed_items SET content = ?, content_format = ?, updated_at = ? WHERE id = ?",
                (content, content_format, utc_now(), item_id)
            )
        conn.commit()

    # 5. LLM Step 2: Synthesis and Clustering
    def truncate_article_content(content: str | None) -> str:
        if not content:
            return "No content extracted"
        if len(content) <= 4000:
            return content
        first_part = content[:2000]
        last_part = content[-2000:]
        return f"{first_part}\n\n[... middle content truncated ...]\n\n{last_part}"

    articles_contents_str = ""
    for idx, item in enumerate(selected_items):
        truncated = truncate_article_content(item.get("content"))
        articles_contents_str += f"ARTICLE {idx+1}:\nID: {item['id']}\nTitle: {item['title']}\nFeed: {item['feed_title']}\nURL: {item['url']}\nContent:\n{truncated}\n====================\n"

    synthesis_prompt = f"""You are a top-tier analyst and chief of staff. Your goal is to prepare a daily intelligence briefing memo for a smart founder or CEO. This memo is synthesized from followed RSS feeds.

The user's Taste Profile is:
\"\"\"
{taste_profile}
\"\"\"

Here are the selected high-signal articles:
\"\"\"
{articles_contents_str}
\"\"\"

Instructions:
1. Synthesize the material into a small number of important conversations or thematic clusters. Combine multiple articles into coherent interpretations rather than treating every article as an isolated object.
2. Explain what actually mattered, what changed underneath the surface, what smart practitioners would notice, where the important tensions or disagreements are, what second-order implications emerge, and which narratives seem overstated versus genuinely meaningful.
3. Writing Style:
   - Use clean, direct prose and simple language while carrying substantial depth.
   - Do NOT use bullet points (no asterisks or hyphens for lists; write in paragraphs).
   - Do NOT use em dashes (—). Use commas, hyphens, colons, or parentheses instead.
   - Avoid excessive formatting, corporate jargon, motivational language, exaggerated claims, and AI-sounding phrasing.
   - Sound like a thoughtful industry insider explaining reality to another intelligent person.
   - Explain mechanisms and incentives, connect isolated events into broader patterns, identify hidden assumptions, and discuss second-order implications.
   - Acknowledge uncertainty when evidence is weak instead of manufacturing false confidence or artificial depth.
   - Do not try to sound impressive. Be precise, skeptical, grounded, and useful.
4. Source Attribution:
   - When referencing information or insights drawn from a specific article, include an inline hyperlink to the source using Markdown link syntax: [descriptive anchor text](URL).
   - Weave links naturally into the prose. For example: "As [this analysis from Stratechery](https://example.com/article) argues, the real shift is...".
   - Do not group all sources at the end. Embed them where they are most contextually relevant.
   - Every thematic section should contain at least one source link.
5. Output Format:
   - Provide the response in Markdown format.
   - Use simple headers (e.g. `##` for conversation clusters) to organize the memo.
   - Do not include any greeting, introduction, signature, or filler. Start directly with the first thematic header.
"""

    try:
        client, model = AzureOpenAIService.get_signal_chat_client_and_model()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a thoughtful industry analyst writing briefings for a CEO. Always write in clean prose and format in Markdown."},
                {"role": "user", "content": synthesis_prompt}
            ]
        )
        content = response.choices[0].message.content
        # Replace em-dashes and clean up any double spaces
        content = content.replace(" — ", " - ").replace(" – ", " - ")
        content = content.replace("—", " - ").replace("–", " - ")
        import re
        content = re.sub(r" {2,}", " ", content)
    except Exception as exc:
        logger.error(f"Error in signal brief synthesis LLM call: {exc}")
        return jsonify({"error": f"Failed to generate brief content: {str(exc)}"}), 500

    # 6. Count articles used in this brief
    article_count = len(selected_items)

    # 7. Save the brief to SQLite
    brief_id = new_id()
    created_at = utc_now()
    conn.execute(
        "INSERT INTO signal_briefs (id, user_id, content, article_count, created_at) VALUES (?, ?, ?, ?, ?)",
        (brief_id, g.user.id, content, article_count, created_at)
    )
    conn.commit()

    row = conn.execute("SELECT * FROM signal_briefs WHERE id = ?", (brief_id,)).fetchone()
    return jsonify(row_to_dict(row)), 201


@signal_bp.route("/briefs/<brief_id>", methods=["DELETE"])
@require_auth
def delete_brief(brief_id: str):
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM signal_briefs WHERE id = ? AND user_id = ?",
        (brief_id, g.user.id)
    ).fetchone()
    if not row:
        return jsonify({"error": "Brief not found"}), 404
    conn.execute("DELETE FROM signal_briefs WHERE id = ?", (brief_id,))
    conn.commit()
    return jsonify({"success": True}), 200


# ---------------------------------------------------------------------------
# SSE Streaming Endpoint
# ---------------------------------------------------------------------------

def _sse_event(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


def _generate_brief_stream(user_id: str):
    """Generator that yields SSE events as the brief pipeline runs."""
    from database import db_session

    with db_session() as conn:
        # 1. Load taste profile
        user_row = conn.execute("SELECT taste_profile FROM users WHERE id = ?", (user_id,)).fetchone()
        taste_profile = user_row["taste_profile"] if user_row else None
        if not taste_profile or not taste_profile.strip():
            taste_profile = DEFAULT_TASTE_PROFILE

        # 2. Fetch candidate articles
        candidate_limit = Config.SIGNAL_CANDIDATE_LIMIT
        unread_rows = conn.execute(
            """
            SELECT i.id, i.url, i.title, i.summary, f.title as feed_title
            FROM feed_items i
            JOIN feeds f ON f.id = i.feed_id AND f.user_id = i.user_id
            LEFT JOIN bookmarks b ON b.user_id = i.user_id AND b.url = i.url
            WHERE i.user_id = ? AND i.status = 'new' AND b.id IS NULL
            ORDER BY COALESCE(i.published_at, i.first_seen_at) DESC
            LIMIT ?
            """,
            (user_id, candidate_limit)
        ).fetchall()

        items = [dict(r) for r in unread_rows]

        # Fallback to recent items if unread pool is too small
        if len(items) < 10:
            recent_rows = conn.execute(
                """
                SELECT i.id, i.url, i.title, i.summary, f.title as feed_title
                FROM feed_items i
                JOIN feeds f ON f.id = i.feed_id AND f.user_id = i.user_id
                LEFT JOIN bookmarks b ON b.user_id = i.user_id AND b.url = i.url
                WHERE i.user_id = ? AND i.status != 'saved' AND b.id IS NULL
                  AND datetime(COALESCE(i.published_at, i.first_seen_at)) >= datetime('now', '-5 days')
                ORDER BY COALESCE(i.published_at, i.first_seen_at) DESC
                LIMIT ?
                """,
                (user_id, candidate_limit)
            ).fetchall()
            existing_ids = {item["id"] for item in items}
            for r in recent_rows:
                if r["id"] not in existing_ids:
                    items.append(dict(r))
                    existing_ids.add(r["id"])

        if not items:
            yield _sse_event({"stage": "error", "message": "No recent RSS feed content found to analyze. Try adding some feeds first in the Radar tab!"})
            return

        # Count distinct sources
        source_names = list({item["feed_title"] or "Unknown" for item in items})
        yield _sse_event({
            "stage": "scanning",
            "message": f"Scanning {len(items)} articles across {len(source_names)} sources",
            "article_count": len(items),
            "source_count": len(source_names),
        })

        # 3. LLM filter by taste profile
        articles_list_str = ""
        for item in items:
            articles_list_str += f"ID: {item['id']}\nTitle: {item['title']}\nFeed: {item['feed_title']}\nSummary: {item['summary'] or 'No summary'}\n---\n"

        filter_prompt = f"""You are an expert analyst assistant. You are given a list of recent articles from followed RSS feeds. Your task is to filter this list aggressively to identify only the articles that align with the user's Taste Profile.

User's Taste Profile:
\"\"\"
{taste_profile}
\"\"\"

Recent RSS Articles:
\"\"\"
{articles_list_str}
\"\"\"

Task:
Select the articles that contain genuine insight, strategic relevance, ecosystem shifts, product directions, or important second-order implications. Skip incremental news, announcements, engagement bait, benchmark hype, or repetitive coverage.
Discard any articles that do not align with the priorities.

Return a JSON object containing a single key "selected_ids" mapping to an array of string IDs of the chosen articles.
Return ONLY valid JSON.
"""

        yield _sse_event({"stage": "filtering", "message": "Applying taste profile filter..."})

        selected_ids = []
        try:
            client, model = AzureOpenAIService.get_signal_chat_client_and_model()
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful analyst assistant. You always respond in valid JSON format."},
                    {"role": "user", "content": filter_prompt}
                ],
                response_format={"type": "json_object"}
            )
            selected_data = json.loads(response.choices[0].message.content)
            selected_ids = selected_data.get("selected_ids", [])
        except Exception as exc:
            logger.error(f"Error in signal filtering LLM call: {exc}")
            selected_ids = [item["id"] for item in items[:10]]

        selected_ids = selected_ids[:15]
        selected_items = [item for item in items if item["id"] in selected_ids]

        if not selected_items:
            yield _sse_event({"stage": "error", "message": "We analyzed recent feeds, but none of them matched your Taste Profile. Adjust your profile or add more high-quality feeds!"})
            return

        yield _sse_event({
            "stage": "filtered",
            "message": f"Selected {len(selected_items)} high-signal articles",
            "count": len(selected_items),
            "titles": [item["title"] for item in selected_items],
        })

        # 4. Extract content for selected items in parallel
        extract_total = len(selected_items)
        extracted_count = 0
        updates = []

        yield _sse_event({"stage": "extracting", "message": "Extracting full text...", "current": 0, "total": extract_total})

        def ensure_content(item):
            item_id = item["id"]
            with db_session() as thread_conn:
                cached_row = thread_conn.execute("SELECT content, content_format FROM feed_items WHERE id = ?", (item_id,)).fetchone()
                if cached_row and cached_row["content"] and cached_row["content"].strip():
                    return (item_id, cached_row["content"], cached_row["content_format"], False)

            try:
                extracted = ContentExtractor.extract(item["url"])
                content = extracted.get("content")
                if content and content.strip():
                    content_format = extracted.get("content_format") or "markdown"
                    return (item_id, content, content_format, True)
            except Exception as exc:
                logger.error(f"Failed content extraction during signal generation for {item['url']}: {exc}")
            return None

        with ThreadPoolExecutor(max_workers=5) as executor:
            future_map = {executor.submit(ensure_content, item): item for item in selected_items}
            for fut in as_completed(future_map):
                res = fut.result()
                if res:
                    item_id, content, content_format, needs_update = res
                    for item in selected_items:
                        if item["id"] == item_id:
                            item["content"] = content
                            item["content_format"] = content_format
                    if needs_update:
                        updates.append((item_id, content, content_format))
                extracted_count += 1
                yield _sse_event({"stage": "extracting", "message": f"Extracting full text... {extracted_count} of {extract_total}", "current": extracted_count, "total": extract_total})

        if updates:
            for item_id, content, content_format in updates:
                conn.execute(
                    "UPDATE feed_items SET content = ?, content_format = ?, updated_at = ? WHERE id = ?",
                    (content, content_format, utc_now(), item_id)
                )
            conn.commit()

        # 5. LLM synthesis
        yield _sse_event({"stage": "synthesizing", "message": "Writing your daily brief..."})

        def truncate_article_content(content: str | None) -> str:
            if not content:
                return "No content extracted"
            if len(content) <= 4000:
                return content
            first_part = content[:2000]
            last_part = content[-2000:]
            return f"{first_part}\n\n[... middle content truncated ...]\n\n{last_part}"

        articles_contents_str = ""
        for idx, item in enumerate(selected_items):
            truncated = truncate_article_content(item.get("content"))
            articles_contents_str += f"ARTICLE {idx+1}:\nID: {item['id']}\nTitle: {item['title']}\nFeed: {item['feed_title']}\nURL: {item['url']}\nContent:\n{truncated}\n====================\n"

        synthesis_prompt = f"""You are a top-tier analyst and chief of staff. Your goal is to prepare a daily intelligence briefing memo for a smart founder or CEO. This memo is synthesized from followed RSS feeds.

The user's Taste Profile is:
\"\"\"
{taste_profile}
\"\"\"

Here are the selected high-signal articles:
\"\"\"
{articles_contents_str}
\"\"\"

Instructions:
1. Synthesize the material into a small number of important conversations or thematic clusters. Combine multiple articles into coherent interpretations rather than treating every article as an isolated object.
2. Explain what actually mattered, what changed underneath the surface, what smart practitioners would notice, where the important tensions or disagreements are, what second-order implications emerge, and which narratives seem overstated versus genuinely meaningful.
3. Writing Style:
   - Use clean, direct prose and simple language while carrying substantial depth.
   - Do NOT use bullet points (no asterisks or hyphens for lists; write in paragraphs).
   - Do NOT use em dashes (\u2014). Use commas, hyphens, colons, or parentheses instead.
   - Avoid excessive formatting, corporate jargon, motivational language, exaggerated claims, and AI-sounding phrasing.
   - Sound like a thoughtful industry insider explaining reality to another intelligent person.
   - Explain mechanisms and incentives, connect isolated events into broader patterns, identify hidden assumptions, and discuss second-order implications.
   - Acknowledge uncertainty when evidence is weak instead of manufacturing false confidence or artificial depth.
   - Do not try to sound impressive. Be precise, skeptical, grounded, and useful.
4. Source Attribution:
   - When referencing information or insights drawn from a specific article, include an inline hyperlink to the source using Markdown link syntax: [descriptive anchor text](URL).
   - Weave links naturally into the prose. For example: "As [this analysis from Stratechery](https://example.com/article) argues, the real shift is...".
   - Do not group all sources at the end. Embed them where they are most contextually relevant.
   - Every thematic section should contain at least one source link.
5. Output Format:
   - Provide the response in Markdown format.
   - Use simple headers (e.g. `##` for conversation clusters) to organize the memo.
   - Do not include any greeting, introduction, signature, or filler. Start directly with the first thematic header.
"""

        try:
            client, model = AzureOpenAIService.get_signal_chat_client_and_model()
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a thoughtful industry analyst writing briefings for a CEO. Always write in clean prose and format in Markdown."},
                    {"role": "user", "content": synthesis_prompt}
                ]
            )
            content = response.choices[0].message.content
            content = content.replace(" \u2014 ", " - ").replace(" \u2013 ", " - ")
            content = content.replace("\u2014", " - ").replace("\u2013", " - ")
            content = re.sub(r" {2,}", " ", content)
        except Exception as exc:
            logger.error(f"Error in signal brief synthesis LLM call: {exc}")
            yield _sse_event({"stage": "error", "message": f"Failed to generate brief content: {str(exc)}"})
            return

        # 6. Save the brief
        article_count = len(selected_items)
        brief_id = new_id()
        created_at = utc_now()
        conn.execute(
            "INSERT INTO signal_briefs (id, user_id, content, article_count, created_at) VALUES (?, ?, ?, ?, ?)",
            (brief_id, user_id, content, article_count, created_at)
        )

        row = conn.execute("SELECT * FROM signal_briefs WHERE id = ?", (brief_id,)).fetchone()
        yield _sse_event({"stage": "complete", "brief": row_to_dict(row)})


@signal_bp.route("/briefs/generate", methods=["POST"])
@require_auth
def generate_brief_stream():
    user_id = g.user.id
    return Response(
        stream_with_context(_generate_brief_stream(user_id)),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
