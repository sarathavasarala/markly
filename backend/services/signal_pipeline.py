"""Shared Signal daily-brief pipeline.

Pure stage functions used by both the blocking and streaming Signal endpoints.
The blocking endpoint calls them in sequence; the streaming endpoint calls the
same functions and yields SSE events between stages. Prompt templates live in
routes/signal.py and are passed in, so the text the model sees stays identical.
"""
from __future__ import annotations

import json
import logging
import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from config import Config
from database import db_session, new_id, row_to_dict, utc_now
from services.content_extractor import ContentExtractor
from services.openai_service import AzureOpenAIService

logger = logging.getLogger(__name__)


DEFAULT_TASTE_PROFILE = (
    "I want analysis, not summaries. Focus on what actually changed, why it matters, "
    "and what intelligent operators or practitioners would notice beneath the surface narrative.\n\n"
    "Prioritize strategic implications, incentives, product direction, business mechanics, "
    "technical tradeoffs, ecosystem shifts, and second-order effects. I care more about why a "
    "company is doing something, what constraints it is reacting to, what hidden incentives exist, "
    "and what longer pattern a move might represent, than about the raw event itself.\n\n"
    "Significant developments matter even when they are announcements. A major product launch, "
    "release, or strategic move from a company that matters is worth knowing about. For those, "
    "the value is what changed and why, not the announcement.\n\n"
    "What I do not want: incremental news with no larger meaning, engagement bait, shallow hot takes, "
    "marketing fluff, repetitive benchmark coverage, and low-information reactions. Treat the taste "
    "profile as an aggressive filter. Spend reasoning budget only on material with genuine insight, "
    "strategic relevance, operational lessons, or evidence of a real shift, and discard the rest early.\n\n"
    "A benchmark or metric is only interesting if it signals something broader about capability, "
    "economics, adoption, market position, or competitive dynamics. Do not dwell on numbers for "
    "their own sake.\n\n"
    "Assume I am sharp but not a specialist in every domain these feeds cover. I want enough "
    "grounding to follow a topic outside my core areas, without insider vocabulary used unexplained."
)


# ---------------------------------------------------------------------------
# Pure text helpers (output kept byte-identical to the previous inline versions)
# ---------------------------------------------------------------------------

def _resolve_taste_profile(row) -> str:
    profile = row["taste_profile"] if row else None
    if not profile or not profile.strip():
        return DEFAULT_TASTE_PROFILE
    return profile


def _build_articles_list_str(items) -> str:
    out = ""
    for item in items:
        out += (
            f"ID: {item['id']}\n"
            f"Title: {item['title']}\n"
            f"Feed: {item['feed_title']}\n"
            f"Summary: {item['summary'] or 'No summary'}\n---\n"
        )
    return out


def truncate_article_content(content: str | None) -> str:
    """Keep most of the article body. Analysis pieces carry their argument in the
    middle, so retain a large head and a small tail rather than coring out the center."""
    if not content:
        return "No content extracted"
    if len(content) <= Config.SIGNAL_CONTENT_MAX_CHARS:
        return content
    first_part = content[: Config.SIGNAL_CONTENT_HEAD_CHARS]
    last_part = content[-Config.SIGNAL_CONTENT_TAIL_CHARS:]
    return f"{first_part}\n\n[... middle content truncated ...]\n\n{last_part}"


def _build_articles_contents_str(selected_items) -> str:
    out = ""
    for idx, item in enumerate(selected_items):
        truncated = truncate_article_content(item.get("content"))
        out += (
            f"ARTICLE {idx + 1}:\n"
            f"ID: {item['id']}\n"
            f"Title: {item['title']}\n"
            f"Feed: {item['feed_title']}\n"
            f"URL: {item['url']}\n"
            f"Content:\n{truncated}\n====================\n"
        )
    return out


def _clean_brief_text(content: str) -> str:
    """Strip em/en dashes and collapse runs of spaces left behind."""
    content = content.replace(" \u2014 ", " - ").replace(" \u2013 ", " - ")
    content = content.replace("\u2014", " - ").replace("\u2013", " - ")
    content = re.sub(r" {2,}", " ", content)
    return content


# ---------------------------------------------------------------------------
# Embedding helpers
# ---------------------------------------------------------------------------

def _parse_embedding(value) -> list[float] | None:
    """Defensively parse a stored embedding (JSON string) into a vector.

    Returns None for anything that is missing or malformed so a single bad row
    never breaks brief generation.
    """
    if value in (None, ""):
        return None
    if isinstance(value, list):
        vec = value
    elif isinstance(value, str):
        try:
            vec = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return None
    else:
        return None
    if not isinstance(vec, list) or not vec:
        return None
    try:
        out = [float(x) for x in vec]
    except (TypeError, ValueError):
        return None
    if not any(out):
        return None
    return out


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


def _age_days(timestamp: str | None) -> float:
    if not timestamp:
        return 0.0
    try:
        parsed = datetime.fromisoformat(timestamp)
    except (ValueError, TypeError):
        return 0.0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - parsed
    return max(delta.total_seconds() / 86400.0, 0.0)


def _recency_weight(timestamp: str | None) -> float:
    half_life = Config.SIGNAL_RECENCY_HALF_LIFE_DAYS or 1.0
    return 0.5 ** (_age_days(timestamp) / half_life)


# ---------------------------------------------------------------------------
# Stage 1: settings
# ---------------------------------------------------------------------------

def load_user_settings(conn, user_id, *, default_filter_template, default_synthesis_template):
    """Load taste profile, candidate limit, and (custom or default) prompt templates."""
    user_row = conn.execute(
        "SELECT taste_profile, signal_candidate_limit, signal_filter_prompt, signal_synthesis_prompt, signal_web_search_enabled "
        "FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()

    taste_profile = _resolve_taste_profile(user_row)
    candidate_limit = (
        user_row["signal_candidate_limit"]
        if user_row and user_row["signal_candidate_limit"] is not None
        else Config.SIGNAL_CANDIDATE_LIMIT
    )
    filter_template = (
        user_row["signal_filter_prompt"]
        if user_row and user_row["signal_filter_prompt"]
        else default_filter_template
    )
    synthesis_template = (
        user_row["signal_synthesis_prompt"]
        if user_row and user_row["signal_synthesis_prompt"]
        else default_synthesis_template
    )
    web_search_enabled = (
        bool(user_row["signal_web_search_enabled"])
        if user_row and user_row["signal_web_search_enabled"] is not None
        else True
    )
    return {
        "taste_profile": taste_profile,
        "candidate_limit": candidate_limit,
        "filter_template": filter_template,
        "synthesis_template": synthesis_template,
        "web_search_enabled": web_search_enabled,
    }


# ---------------------------------------------------------------------------
# Stage 2: candidate selection
# ---------------------------------------------------------------------------

def _briefed_exclude_clause(prefix: str = "i") -> str:
    days = Config.SIGNAL_BRIEFED_EXCLUDE_DAYS
    return (
        f"AND ({prefix}.last_briefed_at IS NULL OR "
        f"datetime({prefix}.last_briefed_at) < datetime('now', '-{days} days'))"
    )


def _fetch_base_pool(conn, user_id, candidate_limit):
    """Reproduce the original unread + 5-day fallback selection, plus the anti-repeat
    filter. At small scale (and when no item was briefed recently) this is byte-identical
    to the previous behavior."""
    unread_rows = conn.execute(
        f"""
        SELECT i.id, i.url, i.title, i.summary, f.title as feed_title,
               i.embedding, COALESCE(i.published_at, i.first_seen_at) as sort_ts
        FROM feed_items i
        JOIN feeds f ON f.id = i.feed_id AND f.user_id = i.user_id
        LEFT JOIN bookmarks b ON b.user_id = i.user_id AND b.url = i.url
        WHERE i.user_id = ? AND i.status = 'new' AND b.id IS NULL
        {_briefed_exclude_clause('i')}
        ORDER BY COALESCE(i.published_at, i.first_seen_at) DESC
        LIMIT ?
        """,
        (user_id, candidate_limit),
    ).fetchall()

    items = [dict(r) for r in unread_rows]

    if len(items) < 10:
        recent_rows = conn.execute(
            f"""
            SELECT i.id, i.url, i.title, i.summary, f.title as feed_title,
                   i.embedding, COALESCE(i.published_at, i.first_seen_at) as sort_ts
            FROM feed_items i
            JOIN feeds f ON f.id = i.feed_id AND f.user_id = i.user_id
            LEFT JOIN bookmarks b ON b.user_id = i.user_id AND b.url = i.url
            WHERE i.user_id = ? AND i.status != 'saved' AND b.id IS NULL
              AND datetime(COALESCE(i.published_at, i.first_seen_at)) >= datetime('now', '-5 days')
              {_briefed_exclude_clause('i')}
            ORDER BY COALESCE(i.published_at, i.first_seen_at) DESC
            LIMIT ?
            """,
            (user_id, candidate_limit),
        ).fetchall()
        existing_ids = {item["id"] for item in items}
        for r in recent_rows:
            if r["id"] not in existing_ids:
                items.append(dict(r))
                existing_ids.add(r["id"])

    return items


def _fetch_ranking_pool(conn, user_id, pool_limit):
    """Larger recent unread pool used only for embedding ranking."""
    rows = conn.execute(
        f"""
        SELECT i.id, i.url, i.title, i.summary, f.title as feed_title,
               i.embedding, COALESCE(i.published_at, i.first_seen_at) as sort_ts
        FROM feed_items i
        JOIN feeds f ON f.id = i.feed_id AND f.user_id = i.user_id
        LEFT JOIN bookmarks b ON b.user_id = i.user_id AND b.url = i.url
        WHERE i.user_id = ? AND i.status = 'new' AND b.id IS NULL
        {_briefed_exclude_clause('i')}
        ORDER BY COALESCE(i.published_at, i.first_seen_at) DESC
        LIMIT ?
        """,
        (user_id, pool_limit),
    ).fetchall()
    return [dict(r) for r in rows]


def _rank_by_embedding(pool, taste_embedding):
    """Rank pool items by cosine(taste, item) * recency decay.

    Items without a valid embedding get a neutral similarity (median of the
    embedded items) so fresh-but-unembedded items stay eligible instead of
    silently dropping. Sorting is stable on recency for ties."""
    sims: list[float | None] = []
    for item in pool:
        vec = _parse_embedding(item.get("embedding"))
        sims.append(_cosine_similarity(taste_embedding, vec) if vec else None)

    embedded_sims = sorted(s for s in sims if s is not None)
    if embedded_sims:
        mid = len(embedded_sims) // 2
        if len(embedded_sims) % 2:
            neutral = embedded_sims[mid]
        else:
            neutral = (embedded_sims[mid - 1] + embedded_sims[mid]) / 2
    else:
        neutral = 0.0

    scored = []
    for idx, item in enumerate(pool):
        similarity = sims[idx] if sims[idx] is not None else neutral
        final_score = similarity * _recency_weight(item.get("sort_ts"))
        scored.append((final_score, idx, item))

    scored.sort(key=lambda t: (-t[0], t[1]))
    return [item for _, _, item in scored]


def select_candidates(conn, user_id, candidate_limit, *, taste_profile):
    """Choose the candidate articles fed to the LLM filter.

    Behavior preservation: when the recent unread pool is no larger than the
    candidate limit, or embeddings are unavailable / poorly covered, the original
    recency-ordered selection is returned unchanged and no embedding calls happen.
    Only when the pool genuinely exceeds the limit and embeddings are present does
    ranking by taste similarity + recency decay take over.
    """
    base_items = _fetch_base_pool(conn, user_id, candidate_limit)
    if not base_items:
        return []

    if not Config.ENABLE_EMBEDDINGS:
        return base_items

    pool = _fetch_ranking_pool(conn, user_id, candidate_limit * Config.SIGNAL_CANDIDATE_POOL_MULTIPLIER)
    if len(pool) <= candidate_limit:
        return base_items

    embedded_count = sum(1 for item in pool if _parse_embedding(item.get("embedding")) is not None)
    if embedded_count < Config.SIGNAL_EMBED_MIN_COVERAGE * len(pool):
        return base_items

    try:
        taste_embedding = AzureOpenAIService.generate_embedding(taste_profile)
    except Exception as exc:
        logger.warning("Taste profile embedding failed, falling back to recency: %s", exc)
        return base_items

    ranked = _rank_by_embedding(pool, taste_embedding)
    return ranked[:candidate_limit]


# ---------------------------------------------------------------------------
# Stage 3: LLM filter
# ---------------------------------------------------------------------------

def llm_filter(items, taste_profile, filter_template):
    """Run the taste-profile filter and return the selected items (best-first, capped)."""
    articles_list_str = _build_articles_list_str(items)
    filter_prompt = filter_template.format(
        taste_profile=taste_profile,
        articles_list_str=articles_list_str,
    )

    selected_ids = []
    try:
        client, model = AzureOpenAIService.get_signal_chat_client_and_model()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful analyst assistant. You always respond in valid JSON format."},
                {"role": "user", "content": filter_prompt},
            ],
            response_format={"type": "json_object"},
        )
        selected_data = json.loads(response.choices[0].message.content)
        selected_ids = selected_data.get("selected_ids", [])
    except Exception as exc:
        logger.error(f"Error in signal filtering LLM call: {exc}")
        selected_ids = [item["id"] for item in items[:10]]

    selected_ids = selected_ids[: Config.SIGNAL_MAX_SYNTHESIS_ARTICLES]
    items_by_id = {item["id"]: item for item in items}
    return [items_by_id[sid] for sid in selected_ids if sid in items_by_id]


# ---------------------------------------------------------------------------
# Stage 4: content extraction
# ---------------------------------------------------------------------------

def extract_contents(selected_items):
    """Ensure full content for the selected items, extracting in parallel.

    This is a generator: it yields (done, total) progress tuples as each item
    finishes and returns the list of (item_id, content, content_format) tuples
    that need to be persisted. Selected items are mutated in place with content.
    """
    items_by_id = {item["id"]: item for item in selected_items}
    total = len(selected_items)
    updates = []

    def ensure_content(item):
        item_id = item["id"]
        with db_session() as thread_conn:
            cached_row = thread_conn.execute(
                "SELECT content, content_format FROM feed_items WHERE id = ?", (item_id,)
            ).fetchone()
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

    done = 0
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_map = {executor.submit(ensure_content, item): item for item in selected_items}
        for fut in as_completed(future_map):
            res = fut.result()
            if res:
                item_id, content, content_format, needs_update = res
                target = items_by_id.get(item_id)
                if target is not None:
                    target["content"] = content
                    target["content_format"] = content_format
                if needs_update:
                    updates.append((item_id, content, content_format))
            done += 1
            yield (done, total)

    return updates


def run_extract_contents(selected_items):
    """Drain the extract_contents generator and return its update list.

    Used by the blocking endpoint, which does not stream progress."""
    gen = extract_contents(selected_items)
    try:
        while True:
            next(gen)
    except StopIteration as stop:
        return stop.value or []


def persist_content_updates(conn, updates):
    """Persist freshly extracted content back onto feed_items."""
    if not updates:
        return
    for item_id, content, content_format in updates:
        conn.execute(
            "UPDATE feed_items SET content = ?, content_format = ?, updated_at = ? WHERE id = ?",
            (content, content_format, utc_now(), item_id),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Stage 5: research (web search grounding)
# ---------------------------------------------------------------------------

RESEARCH_PROMPT_TEMPLATE = """You are a research assistant preparing background context for a daily intelligence brief.

You are given a set of high-signal articles selected from RSS feeds. Your job is NOT to analyze or summarize them. Your job is to find the factual context a smart reader would want in order to understand these stories properly, using web search and page fetches.

Here are the articles:
\"\"\"
{articles_contents_str}
\"\"\"

Instructions:
1. Read the articles. Identify the gaps a sharp reader would want filled: relevant dates, prior context, competitor or regulatory status, financial figures, what a referenced term or product actually is, what happened before this that the article assumes you know.
2. Formulate at least 3 and up to 8 specific, factual questions that close those gaps. Favor questions whose answers ground the analysis, not speculative or opinion questions.
3. You have two tools:
   - web_search: find candidate sources and snippets.
   - web_fetch: pull the full text of the most relevant 1 to 3 URLs to verify details and get clean facts.
4. For each question, run web_search, then web_fetch the best sources to confirm.
5. For each question, write a short factual grounding entry (2 to 4 sentences) answering it with current facts. Include a source URL when available.
6. Do NOT analyze or editorialize. Only report retrieved facts.
7. If everything in the articles is already clear and needs no follow-up, return a brief note saying no additional context is needed.

Output Format:
Return plain text, one entry per paragraph, in this shape:

**[Question or concept]**: [Factual grounding, 2 to 4 sentences]. Source: [URL if available]

Keep the total under about 800 words.
"""


def research(selected_items, web_search_enabled=True):
    """Run web search grounding on the selected articles and return a research brief and queries list.

    When web_search_enabled is False, this step is skipped and returns ("", []).
    Uses the default (cheaper) model with the Responses API for web search.
    """
    if not web_search_enabled:
        return "", []

    articles_contents_str = _build_articles_contents_str(selected_items)
    research_prompt = RESEARCH_PROMPT_TEMPLATE.replace(
        "{articles_contents_str}", articles_contents_str
    )

    system_content = (
        "You are an elite research assistant. Think like an intelligent Executive or smart operator. "
        "Formulate smart search queries to answer critical follow-up questions about the articles, "
        "and retrieve factual grounding. Do not analyze or editorialize."
    )

    try:
        research_brief, queries = AzureOpenAIService.generate_research_with_search(
            research_prompt, system_content
        )
        return research_brief.strip(), queries
    except Exception as exc:
        logger.warning("Research step failed, proceeding without research brief: %s", exc)
        return "", []


# ---------------------------------------------------------------------------
# Stage 6: synthesis
# ---------------------------------------------------------------------------

def synthesize(selected_items, taste_profile, synthesis_template, research_brief=""):
    """Run the synthesis LLM call and return cleaned brief text.

    This is a pure writing step — no tools, no web search. If a research brief
    is provided, it is injected into the prompt for the model to reference.
    """
    articles_contents_str = _build_articles_contents_str(selected_items)
    
    # Safely format the template (in case they have other custom placeholders)
    fmt_args = {
        "taste_profile": taste_profile,
        "articles_contents_str": articles_contents_str,
        "research_brief": research_brief,
    }
    import string
    formatter = string.Formatter()
    try:
        for _, field_name, _, _ in formatter.parse(synthesis_template):
            if field_name and field_name not in fmt_args:
                fmt_args[field_name] = ""
        synthesis_prompt = synthesis_template.format(**fmt_args)
    except Exception as exc:
        logger.warning(f"Error formatting synthesis template: {exc}. Falling back to default format.")
        synthesis_prompt = (
            synthesis_template.replace("{taste_profile}", taste_profile)
            .replace("{articles_contents_str}", articles_contents_str)
            .replace("{research_brief}", research_brief)
        )

    system_content = "You are a thoughtful industry analyst writing briefings for a CEO. Always write in clean prose and format in Markdown."
    
    # Use Responses API with high verbosity for final memo generation
    content = AzureOpenAIService.generate_brief_with_verbosity(
        synthesis_prompt, system_content, verbosity="high"
    )
        
    return _clean_brief_text(content)


def parse_and_clean_brief(content: str) -> tuple[str | None, str]:
    """Extract the title from the first line if it starts with '# Theme:' or '# ' and return (title, clean_content)."""
    if not content:
        return None, content

    lines = content.strip().splitlines()
    if not lines:
        return None, content

    first_line = lines[0].strip()
    if first_line.startswith("# Theme:") or first_line.startswith("#Theme:") or first_line.startswith("# "):
        if first_line.startswith("# Theme:"):
            title = first_line[8:].strip()
        elif first_line.startswith("#Theme:"):
            title = first_line[7:].strip()
        else:
            title = first_line[2:].strip()
        
        # Strip any markdown bold/italic formatting from the title
        title = title.strip("*_").strip()
        
        clean_content = "\n".join(lines[1:]).lstrip()
        return title, clean_content

    return None, content


# ---------------------------------------------------------------------------
# Stage 7: persist brief
# ---------------------------------------------------------------------------

def save_brief(conn, user_id, content, selected_items):
    """Persist the brief and stamp last_briefed_at on the synthesized items.

    Stamping and the insert happen in one transaction, committed before the row
    is returned, so callers never report success on an uncommitted brief."""
    article_count = len(selected_items)
    brief_id = new_id()
    created_at = utc_now()

    title, clean_content = parse_and_clean_brief(content)

    conn.execute(
        "INSERT INTO signal_briefs (id, user_id, content, title, article_count, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (brief_id, user_id, clean_content, title, article_count, created_at),
    )

    briefed_ids = [item["id"] for item in selected_items]
    if briefed_ids:
        placeholders = ",".join("?" for _ in briefed_ids)
        conn.execute(
            f"UPDATE feed_items SET last_briefed_at = ?, updated_at = ? "
            f"WHERE user_id = ? AND id IN ({placeholders})",
            (created_at, created_at, user_id, *briefed_ids),
        )
    conn.commit()

    row = conn.execute("SELECT * FROM signal_briefs WHERE id = ?", (brief_id,)).fetchone()
    return row_to_dict(row)

