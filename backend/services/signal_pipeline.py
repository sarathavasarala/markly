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
    "state the news plainly first, then explain what changed and why. Do not force the repeated "
    "'the story is not X, it is Y' framing; it gets stale quickly and makes every item sound "
    "artificially contrarian.\n\n"
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


def load_recent_brief_titles(conn, user_id, limit=3) -> list[str]:
    """Return the titles of the user's most recent briefs (newest first).

    Used to give the synthesis step short-term memory so consecutive briefs do
    not keep re-explaining the same theme when one story dominates the feed.
    """
    rows = conn.execute(
        "SELECT title FROM signal_briefs "
        "WHERE user_id = ? AND title IS NOT NULL AND TRIM(title) != '' "
        "ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    return [row["title"].strip() for row in rows if row["title"] and row["title"].strip()]


def _build_recent_briefs_str(titles) -> str:
    if not titles:
        return "None yet. This is the first brief for this user."
    return "\n".join(f"- {t}" for t in titles)


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

def load_user_settings(conn, user_id, *, default_filter_template, default_synthesis_template, default_planning_template):
    """Load taste profile, candidate limit, synthesis limit, and (custom or default) prompt templates."""
    user_row = conn.execute(
        "SELECT taste_profile, signal_candidate_limit, signal_synthesis_limit, signal_filter_prompt, signal_planning_prompt, signal_synthesis_prompt, signal_web_search_enabled "
        "FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()

    taste_profile = _resolve_taste_profile(user_row)
    candidate_limit = (
        user_row["signal_candidate_limit"]
        if user_row and user_row["signal_candidate_limit"] is not None
        else Config.SIGNAL_CANDIDATE_LIMIT
    )
    synthesis_limit = (
        user_row["signal_synthesis_limit"]
        if user_row and user_row["signal_synthesis_limit"] is not None
        else Config.SIGNAL_MAX_SYNTHESIS_ARTICLES
    )
    filter_template = (
        user_row["signal_filter_prompt"]
        if user_row and user_row["signal_filter_prompt"]
        else default_filter_template
    )
    planning_template = (
        user_row["signal_planning_prompt"]
        if user_row and user_row["signal_planning_prompt"]
        else default_planning_template
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
        "synthesis_limit": synthesis_limit,
        "filter_template": filter_template,
        "planning_template": planning_template,
        "planning_enabled": Config.SIGNAL_BRIEF_PLANNING_ENABLED,
        "synthesis_template": synthesis_template,
        "web_search_enabled": web_search_enabled,
        "recent_briefs": _build_recent_briefs_str(load_recent_brief_titles(conn, user_id)),
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

def llm_filter(items, taste_profile, filter_template, synthesis_limit=None):
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

    if synthesis_limit is None:
        synthesis_limit = Config.SIGNAL_MAX_SYNTHESIS_ARTICLES
    selected_ids = selected_ids[:synthesis_limit]
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
# Stage 5: brief planning
# ---------------------------------------------------------------------------

def _fallback_brief_plan(selected_items) -> str:
    """Return a conservative plan if the planner LLM is unavailable."""
    lines = [
        "Editorial plan:",
        "- Treat each selected article as a standalone candidate unless the final writer finds a clear connection in the full text.",
        "- Collapse duplicate coverage if multiple articles describe the same event without adding distinct analysis.",
        "- Prefer source tensions, concrete mechanisms, and what changed over generic theme labels.",
        "",
        "Selected items:",
    ]
    for item in selected_items:
        lines.append(f"- {item.get('title')} ({item.get('feed_title') or 'Unknown source'}): standalone unless strongly connected by the article text.")
    return "\n".join(lines)


def plan_brief(selected_items, taste_profile, planning_template, recent_briefs=""):
    """Create an ephemeral editorial plan for today's selected articles.

    The plan is a scratchpad for research and synthesis, not a persistent cluster
    model. It should help the final writer group only real themes, preserve
    strong standalone stories, and notice source tensions.
    """
    articles_contents_str = _build_articles_contents_str(selected_items)
    fmt_args = {
        "taste_profile": taste_profile,
        "articles_contents_str": articles_contents_str,
        "recent_briefs": recent_briefs,
    }

    import string
    formatter = string.Formatter()
    try:
        for _, field_name, _, _ in formatter.parse(planning_template):
            if field_name and field_name not in fmt_args:
                fmt_args[field_name] = ""
        planning_prompt = planning_template.format(**fmt_args)
    except Exception as exc:
        logger.warning("Error formatting planning template: %s. Using fallback plan.", exc)
        return _fallback_brief_plan(selected_items)

    try:
        client, model = AzureOpenAIService.get_signal_chat_client_and_model()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an editorial planning assistant for an intelligence brief. "
                        "Write concise planning notes only. Do not draft the final brief."
                    ),
                },
                {"role": "user", "content": planning_prompt},
            ],
        )
        plan = (response.choices[0].message.content or "").strip()
        return plan or _fallback_brief_plan(selected_items)
    except Exception as exc:
        logger.warning("Brief planning failed, using fallback plan: %s", exc)
        return _fallback_brief_plan(selected_items)


# ---------------------------------------------------------------------------
# Stage 6: research (web search grounding)
# ---------------------------------------------------------------------------

RESEARCH_PROMPT_TEMPLATE = """You are a research assistant preparing background context for a daily intelligence brief.

You are given a set of high-signal articles selected from RSS feeds. Your job is NOT to analyze or summarize them. Your job is to find the factual context a smart reader would want in order to understand these stories properly, using web search and page fetches.

Here are the articles:
\"\"\"
{articles_contents_str}
\"\"\"

Editorial Brief Plan:
\"\"\"
{brief_plan}
\"\"\"

Instructions:
1. Read the articles and the Editorial Brief Plan. Identify the factual gaps a sharp reader would want filled for the planned themes, standalone stories, source tensions, and novelty claims: relevant dates, prior context, competitor or regulatory status, financial figures, what a referenced term or product actually is, what happened before this that the article assumes you know.
2. Formulate at least 5 and up to 8 specific, factual questions that close those gaps. Prefer questions tied to the planned themes rather than generic background.
3. You have two tools:
   - web_search: find candidate sources and snippets.
   - web_fetch: pull the full text of the most relevant URLs.
4. Run at least 5 distinct search queries using the web_search tool. For meaningful search results, you MUST use the web_fetch tool to download the webpage content fully to extract grounded facts.
5. For each question, write a comprehensive factual grounding entry answering it with detailed context and findings from the search. Include source URLs.
6. Do NOT analyze or editorialize. Only report retrieved facts.
7. If everything in the articles is already clear and needs no follow-up, return a brief note saying no additional context is needed.

Output Format:
Return plain text, one entry per paragraph, in this shape:

**[Question or concept]**: [Detailed factual grounding and findings]. Source: [URL if available]

Keep the total under about 2000 words.
"""


def research(selected_items, web_search_enabled=True, brief_plan=""):
    """Run web search grounding on the selected articles and return a research brief and queries list.

    When web_search_enabled is False, this step is skipped and returns ("", []).
    Uses the default (cheaper) model with the Responses API for web search.
    """
    if not web_search_enabled:
        return "", []

    articles_contents_str = _build_articles_contents_str(selected_items)
    research_prompt = (
        RESEARCH_PROMPT_TEMPLATE
        .replace("{articles_contents_str}", articles_contents_str)
        .replace("{brief_plan}", brief_plan or "No separate editorial plan was generated.")
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
# Stage 7: synthesis
# ---------------------------------------------------------------------------

def synthesize(selected_items, taste_profile, synthesis_template, research_brief="", recent_briefs="", brief_plan=""):
    """Run the synthesis LLM call and return cleaned brief text.

    This is a pure writing step — no tools, no web search. If a research brief
    is provided, it is injected into the prompt for the model to reference.
    `recent_briefs` lists the titles of the user's last few briefs so the model
    can avoid repeating themes already covered.
    """
    articles_contents_str = _build_articles_contents_str(selected_items)
    
    # Safely format the template (in case they have other custom placeholders)
    fmt_args = {
        "taste_profile": taste_profile,
        "articles_contents_str": articles_contents_str,
        "research_brief": research_brief,
        "recent_briefs": recent_briefs,
        "brief_plan": brief_plan,
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
            .replace("{recent_briefs}", recent_briefs)
            .replace("{brief_plan}", brief_plan)
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
    title = None
    if first_line.startswith("# Theme:"):
        title = first_line[8:].strip()
    elif first_line.startswith("#Theme:"):
        title = first_line[7:].strip()
    elif first_line.startswith("## Theme:"):
        title = first_line[9:].strip()
    elif first_line.startswith("# "):
        title = first_line[2:].strip()
    elif first_line.startswith("## "):
        title = first_line[3:].strip()

    if title is not None:
        # Strip any markdown bold/italic formatting from the title
        title = title.strip("*_").strip()

        clean_content = "\n".join(lines[1:]).lstrip()
        return title, clean_content

    return None, content


# ---------------------------------------------------------------------------
# Stage 8: persist brief
# ---------------------------------------------------------------------------

def save_brief(conn, user_id, content, selected_items):
    """Persist the brief and stamp last_briefed_at on the synthesized items.

    Stamping and the insert happen in one transaction, committed before the row
    is returned, so callers never report success on an uncommitted brief."""
    article_count = len(selected_items)
    brief_id = new_id()
    created_at = utc_now()

    parsed_title, clean_content = parse_and_clean_brief(content)

    # Dedicated title pass: a small, cheap model writes a sharper, more consistent
    # title from the finished memo. Fall back to the title parsed from the first
    # line if the dedicated pass fails or returns nothing.
    title = AzureOpenAIService.generate_signal_title(clean_content) or parsed_title

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
