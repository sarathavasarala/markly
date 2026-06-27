"""HN Synthesis pipeline.

Fetches the Hacker News front page, classifies interesting stories,
fetches comment threads via the Algolia HN API (one request per story),
synthesizes each story+thread with the CRITICAL HN READER prompt, and
fans the results out as feed_items into each user's internal HN Synthesis
feed.

Architecture notes:
- synthesize once globally -> hn_syntheses cache table
- fan out cheaply per user -> feed_items with guid='hn-synthesis:{hn_id}'
- comment flattening is depth-first (v1 simplicity); see _flatten_comments docstring
- the internal feed uses feed_url='markly-internal://hn-synthesis' with is_active=0
  so refresh_feeds never HTTP-fetches it
"""
from __future__ import annotations

import json
import logging
import re
import time
import traceback as tb
from datetime import datetime, timedelta, timezone
from html import unescape
from typing import Any
from urllib.parse import parse_qs, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

from config import Config, Prompts
from database import db_session, new_id, utc_now
from services.content_extractor import ContentExtractor
from services.openai_service import AzureOpenAIService

logger = logging.getLogger(__name__)

HN_FAVICON_URL = "https://www.google.com/s2/favicons?domain=news.ycombinator.com&sz=64"
HN_SITE_URL = "https://news.ycombinator.com/"
HN_INTERNAL_FEED_URL = "markly-internal://hn-synthesis"

_HEADERS = {
    "User-Agent": "markly-hn-synthesis/1.0 (+https://markly.azurewebsites.net)",
    "Accept": "application/json, application/rss+xml, */*;q=0.8",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hn_id_from_url(url: str) -> int | None:
    """Extract HN item id integer from a URL like https://news.ycombinator.com/item?id=48689028."""
    try:
        qs = parse_qs(urlparse(url).query)
        ids = qs.get("id", [])
        if ids:
            return int(ids[0])
    except Exception:
        pass
    return None


def _plain_text(html: str | None) -> str:
    """Strip HTML tags and unescape entities to produce plain text."""
    if not html:
        return ""
    text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    return unescape(text)


def _extract_points_and_comments(description_html: str) -> tuple[int, int]:
    """Parse Points and # Comments integers from HN RSS description HTML."""
    points_match = re.search(r"Points:\s*(\d+)", description_html or "")
    comments_match = re.search(r"#\s*Comments:\s*(\d+)", description_html or "")
    points = int(points_match.group(1)) if points_match else 0
    num_comments = int(comments_match.group(1)) if comments_match else 0
    return points, num_comments


# ---------------------------------------------------------------------------
# Stage 1: Fetch + parse frontpage
# ---------------------------------------------------------------------------

def fetch_frontpage() -> list[dict]:
    """Fetch hnrss.org frontpage and return a list of candidate story dicts.

    Each dict has keys: hn_id, title, article_url, comments_url,
    points, num_comments, brief, story_published_at.
    """
    url = Config.HN_FRONTPAGE_URL
    try:
        response = requests.get(
            url, headers=_HEADERS, timeout=Config.HN_HTTP_TIMEOUT_SECONDS, allow_redirects=True
        )
        response.raise_for_status()
        content = response.content
        if len(content) > Config.FEED_MAX_RESPONSE_BYTES:
            logger.warning(
                "HN frontpage response exceeded size limit (%d bytes); using truncated content",
                Config.FEED_MAX_RESPONSE_BYTES,
            )
            content = content[: Config.FEED_MAX_RESPONSE_BYTES]
    except Exception as exc:
        logger.error("Failed to fetch HN frontpage from %s: %s", url, exc)
        return []

    parsed = feedparser.parse(content)
    items: list[dict] = []

    for entry in parsed.entries:
        title = (entry.get("title") or "").strip()
        if not title:
            continue

        # Real article URL lives in <link>
        article_url = (entry.get("link") or "").strip()

        # HN comments URL — <comments> is most reliable, fall back to <guid>
        comments_url = (entry.get("comments") or "").strip()
        guid_val = (entry.get("id") or entry.get("guid") or "").strip()
        hn_item_url = comments_url or guid_val

        hn_id = _hn_id_from_url(hn_item_url)
        if not hn_id:
            logger.debug("Could not extract HN id from entry %r", hn_item_url)
            continue

        # For Ask/Show HN with no external link, article_url == hn_item_url
        if not article_url:
            article_url = hn_item_url

        # Points + comment count from description HTML
        desc_html = entry.get("summary") or entry.get("description") or ""
        points, num_comments = _extract_points_and_comments(desc_html)

        # Short plain-text brief for the classifier
        brief = _plain_text(desc_html)[:500]

        # Publish timestamp
        struct_time = entry.get("published_parsed") or entry.get("updated_parsed")
        story_published_at: str | None = None
        if struct_time:
            try:
                story_published_at = datetime(*struct_time[:6], tzinfo=timezone.utc).isoformat()
            except Exception:
                pass

        items.append(
            {
                "hn_id": hn_id,
                "title": title,
                "article_url": article_url,
                "comments_url": f"https://news.ycombinator.com/item?id={hn_id}",
                "points": points,
                "num_comments": num_comments,
                "brief": brief,
                "story_published_at": story_published_at,
            }
        )

    return items


# ---------------------------------------------------------------------------
# Stage 2: LLM classifier
# ---------------------------------------------------------------------------

def classify_items(items: list[dict]) -> list[dict]:
    """Select HN stories worth synthesizing via a single JSON-mode LLM call.

    Returns items annotated with a 'classification' key, capped at
    Config.HN_SYNTHESIS_MAX_ITEMS, ordered best-first. Falls back to
    top-N by points if the LLM call fails.
    """
    if not items:
        return []

    items_list = "\n".join(
        f"{i + 1}. id={item['hn_id']} | points={item['points']} | comments={item['num_comments']}\n"
        f"   Title: {item['title']}\n"
        f"   Brief: {item['brief'][:300]}"
        for i, item in enumerate(items)
    )

    prompt = Prompts.HN_CLASSIFIER_PROMPT.format(items_list=items_list)

    try:
        client, model = AzureOpenAIService.get_signal_chat_client_and_model()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful analyst assistant. You always respond in valid JSON format.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            timeout=Config.HN_LLM_TIMEOUT_SECONDS,
        )
        data = json.loads(response.choices[0].message.content)
        selected_raw = data.get("selected", [])
    except Exception as exc:
        logger.error("HN classifier LLM call failed: %s. Falling back to top-N by points.", exc)
        fallback = sorted(items, key=lambda x: x["points"], reverse=True)[
            : Config.HN_SYNTHESIS_MAX_ITEMS
        ]
        for item in fallback:
            item = dict(item)
            item["classification"] = "news"
        return [dict(item, classification="news") for item in fallback]

    items_by_id = {item["hn_id"]: item for item in items}
    result: list[dict] = []
    for sel in selected_raw[: Config.HN_SYNTHESIS_MAX_ITEMS]:
        try:
            hn_id = int(sel["id"])
            classification = str(sel.get("classification", "news"))
        except (KeyError, TypeError, ValueError):
            continue
        if hn_id in items_by_id:
            enriched = dict(items_by_id[hn_id])
            enriched["classification"] = classification
            result.append(enriched)

    return result


# ---------------------------------------------------------------------------
# Stage 3: Fetch comments via Algolia HN API
# ---------------------------------------------------------------------------

def _flatten_comments(node: dict, depth: int = 0, budget: list[int] | None = None) -> list[str]:
    """Depth-first flatten of the Algolia HN item tree into attribution-tagged lines.

    v1 implementation note: we traverse depth-first, so a long top-level thread
    can exhaust the char budget before sibling top-level comments are reached.
    This is acceptable for v1 because HN threads tend to be wide rather than
    deep, and the top comments are usually the most substantive. A breadth-first
    implementation would be fairer but more complex.

    Deleted/dead nodes are skipped (their children are still traversed).
    """
    if budget is None:
        budget = [Config.HN_COMMENTS_MAX_CHARS]

    lines: list[str] = []
    if budget[0] <= 0:
        return lines

    is_deleted = node.get("deleted") or node.get("dead")
    author = node.get("author") or "unknown"
    text_html = node.get("text") or ""
    node_type = node.get("type")

    if not is_deleted and text_html and node_type in ("comment", None):
        text = _plain_text(text_html).strip()
        if text:
            indent = "  " * depth
            line = f"{indent}[{author}]: {text}"
            if budget[0] > 0:
                take = min(len(line), budget[0])
                lines.append(line[:take])
                budget[0] -= take

    for child in node.get("children") or []:
        if budget[0] <= 0:
            break
        lines.extend(_flatten_comments(child, depth + 1, budget))

    return lines


def fetch_comments(hn_id: int) -> dict | None:
    """Fetch the full comment tree for an HN story via a single Algolia API request.

    Returns {"item": <root dict>, "flattened": <str>} or None on error.
    The flattened string is capped at HN_COMMENTS_MAX_CHARS characters.
    """
    url = Config.HN_ALGOLIA_ITEM_URL.format(id=hn_id)
    try:
        response = requests.get(
            url, headers=_HEADERS, timeout=Config.HN_HTTP_TIMEOUT_SECONDS, allow_redirects=True
        )
        response.raise_for_status()
        content = response.content
        if len(content) > Config.FEED_MAX_RESPONSE_BYTES:
            logger.warning(
                "Algolia response for hn_id=%s exceeded size limit; content may be partial", hn_id
            )
        item = json.loads(content)
    except Exception as exc:
        logger.error("Failed to fetch Algolia item for hn_id=%s: %s", hn_id, exc)
        return None

    flat_lines = _flatten_comments(item)
    flattened = "\n".join(flat_lines)
    return {"item": item, "flattened": flattened}


# ---------------------------------------------------------------------------
# Stage 4: Article content extraction
# ---------------------------------------------------------------------------

def _fetch_article_text(article_url: str, hn_item: dict | None) -> str:
    """Return article body text, or '' if extraction fails.

    For Show/Ask HN (article_url is an HN page), uses the item's own text
    field from the Algolia response instead of fetching externally.
    """
    is_hn_self = article_url.startswith("https://news.ycombinator.com/")

    if is_hn_self and hn_item:
        return _plain_text(hn_item.get("text") or "")

    try:
        result = ContentExtractor.extract(article_url)
        content = result.get("content") or ""
        # Reuse the signal pipeline's smart-truncation budget
        from services.signal_pipeline import truncate_article_content

        return truncate_article_content(content)
    except Exception as exc:
        logger.warning("Article extraction failed for %s: %s", article_url, exc)
        return ""


# ---------------------------------------------------------------------------
# Stage 5: Synthesis (CRITICAL HN READER)
# ---------------------------------------------------------------------------

def synthesize(
    title: str,
    article_url: str,
    article_text: str,
    comments_text: str,
    points: int,
    num_comments: int,
) -> str:
    """Run the CRITICAL HN READER prompt and return synthesis markdown.

    Returns '' on error (caller should skip persisting empty syntheses).
    Errors are logged to telemetry_logs using the first available user_id as
    a best-effort association.
    """
    article_section = (
        article_text.strip()
        if article_text.strip()
        else "[Article text could not be retrieved. Analyze the comment thread only and note the absence.]"
    )
    comments_section = (
        comments_text.strip() if comments_text.strip() else "[No comments available.]"
    )

    user_msg = (
        f"## Article\n\n"
        f"**Title:** {title}\n"
        f"**URL:** {article_url}\n"
        f"**Points:** {points}  |  **Comments:** {num_comments}\n\n"
        f"### Article Text\n\n{article_section}\n\n"
        f"---\n\n"
        f"### HN Comment Thread\n\n{comments_section}"
    )

    try:
        client, model = AzureOpenAIService.get_signal_chat_client_and_model()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": Prompts.HN_CRITICAL_READER_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            timeout=Config.HN_LLM_TIMEOUT_SECONDS,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.error("HN synthesis LLM call failed for %r: %s", title, exc)
        _log_telemetry_error("hn_synthesis", exc)
        return ""


def _log_telemetry_error(stage: str, exc: Exception) -> None:
    """Write an error to telemetry_logs using the first available user as anchor."""
    try:
        with db_session() as conn:
            user_row = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
            if user_row:
                conn.execute(
                    """
                    INSERT INTO telemetry_logs
                        (id, user_id, stage, error_message, traceback, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_id(),
                        user_row["id"],
                        stage,
                        str(exc)[:500],
                        tb.format_exc()[:2000],
                        utc_now(),
                    ),
                )
    except Exception:
        pass  # Never let telemetry writes crash the pipeline


# ---------------------------------------------------------------------------
# Stage 6: Persist to hn_syntheses + fan out to feed_items
# ---------------------------------------------------------------------------

def ensure_hn_feed(conn, user_id: str) -> str:
    """Get or create the internal HN Synthesis feed for a user. Returns feed_id.

    The feed uses is_active=0 so refresh_feeds never HTTP-fetches it.
    The sentinel feed_url 'markly-internal://hn-synthesis' is also guarded
    explicitly in feeds.refresh_feeds.
    """
    existing = conn.execute(
        "SELECT id FROM feeds WHERE user_id = ? AND feed_url = ?",
        (user_id, HN_INTERNAL_FEED_URL),
    ).fetchone()
    if existing:
        return existing["id"]

    feed_id = new_id()
    now = utc_now()
    conn.execute(
        """
        INSERT OR IGNORE INTO feeds
            (id, user_id, feed_url, title, site_url, favicon_url,
             failure_count, is_active, retention_limit, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 0, 0, 500, ?, ?)
        """,
        (
            feed_id,
            user_id,
            HN_INTERNAL_FEED_URL,
            "HN Synthesis",
            HN_SITE_URL,
            HN_FAVICON_URL,
            now,
            now,
        ),
    )
    # Re-fetch in case a concurrent INSERT OR IGNORE raced us
    row = conn.execute(
        "SELECT id FROM feeds WHERE user_id = ? AND feed_url = ?",
        (user_id, HN_INTERNAL_FEED_URL),
    ).fetchone()
    return row["id"]


def _teaser_from_synthesis(synthesis_md: str) -> str:
    """Extract a short plain-text teaser from synthesis markdown.

    Skips heading, bullet, and blank lines; takes the first ~400 chars of prose.
    """
    lines = synthesis_md.splitlines()
    parts: list[str] = []
    chars = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Skip headings, bullets, bold markers
        if stripped.startswith(("#", "*", "-", ">")):
            continue
        parts.append(stripped)
        chars += len(stripped)
        if chars >= 400:
            break
    return " ".join(parts)[:500]


def _persist_synthesis(conn, item: dict, synthesis_md: str) -> str:
    """Insert a row into hn_syntheses (IGNORE if already present). Returns row id."""
    existing = conn.execute(
        "SELECT id FROM hn_syntheses WHERE hn_id = ?", (item["hn_id"],)
    ).fetchone()
    if existing:
        return existing["id"]

    row_id = new_id()
    now = utc_now()
    conn.execute(
        """
        INSERT INTO hn_syntheses
            (id, hn_id, title, article_url, comments_url, points, num_comments,
             classification, synthesis_md, story_published_at, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row_id,
            item["hn_id"],
            item["title"],
            item["article_url"],
            item["comments_url"],
            item["points"],
            item["num_comments"],
            item.get("classification"),
            synthesis_md,
            item.get("story_published_at"),
            now,
            now,
        ),
    )
    return row_id


def _fan_out_to_user(conn, user_id: str, item: dict, synthesis_md: str, feed_id: str) -> None:
    """Insert a synthesis feed_item for a user (INSERT OR IGNORE for idempotency).

    url is set to the HN comments URL (not article_url) to avoid collisions with
    the UNIQUE(user_id, url) constraint when the same article already exists in
    another feed for this user.
    """
    guid = f"hn-synthesis:{item['hn_id']}"
    teaser = _teaser_from_synthesis(synthesis_md)
    now = utc_now()

    classification = item.get("classification", "")
    title_prefix = f"[{classification.upper()}] " if classification else ""
    display_title = f"{title_prefix}{item['title']}"

    conn.execute(
        """
        INSERT OR IGNORE INTO feed_items
            (id, user_id, feed_id, guid, url, title, author, published_at,
             summary, content, content_format, status, first_seen_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 'HN Synthesis', ?, ?, ?, 'markdown', 'new', ?, ?)
        """,
        (
            new_id(),
            user_id,
            feed_id,
            guid,
            # Use the HN comments URL so UNIQUE(user_id, url) never conflicts
            # with an article that already exists in another feed for this user.
            item["comments_url"],
            display_title,
            item.get("story_published_at"),
            teaser,
            synthesis_md,
            now,
            now,
        ),
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def _already_synthesized_ids(conn) -> set[int]:
    """Return hn_ids synthesized within the retention window."""
    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(hours=Config.HN_SYNTHESIS_RETENTION_HOURS)
    ).isoformat()
    rows = conn.execute(
        "SELECT hn_id FROM hn_syntheses WHERE created_at > ?", (cutoff,)
    ).fetchall()
    return {row["hn_id"] for row in rows}


def run_hn_synthesis(conn) -> dict[str, Any]:
    """Orchestrate the full HN synthesis pipeline.

    Steps:
    1. Fetch HN frontpage stories
    2. Skip hn_ids already synthesized within the retention window
    3. Classify remaining stories via LLM (keeps <= HN_SYNTHESIS_MAX_ITEMS)
    4. For each classified story:
       a. Polite throttle (HN_FETCH_DELAY_SECONDS)
       b. Fetch comment tree (Algolia, 1 request)
       c. Extract article text (ContentExtractor)
       d. Synthesize (LLM)
       e. Persist to hn_syntheses
       f. Fan out to each user's HN Synthesis feed_items
    5. Trigger background embedding generation (non-blocking)

    Returns a summary dict for logging/monitoring.
    """
    stats: dict[str, Any] = {
        "stories_seen": 0,
        "already_done": 0,
        "classified": 0,
        "synthesized": 0,
        "fanned_out": 0,
    }

    # 1. Fetch frontpage
    candidates = fetch_frontpage()
    stats["stories_seen"] = len(candidates)
    if not candidates:
        logger.warning("HN frontpage fetch returned no items")
        return stats

    # 2. Skip already-synthesized
    done_ids = _already_synthesized_ids(conn)
    fresh = [c for c in candidates if c["hn_id"] not in done_ids]
    stats["already_done"] = len(candidates) - len(fresh)
    if not fresh:
        logger.info("All %d HN frontpage items already synthesized", len(candidates))
        return stats

    # 3. Classify
    classified = classify_items(fresh)
    stats["classified"] = len(classified)
    if not classified:
        logger.info("HN classifier selected no items from %d candidates", len(fresh))
        return stats

    # Load users for fan-out
    users = conn.execute("SELECT id FROM users").fetchall()

    # 4. Per-story: fetch -> synthesize -> persist -> fan-out
    for item in classified:
        hn_id = item["hn_id"]
        logger.info(
            "HN synthesis: processing hn_id=%s points=%s title=%r",
            hn_id,
            item["points"],
            item["title"],
        )

        # Polite throttle between stories
        time.sleep(Config.HN_FETCH_DELAY_SECONDS)

        # Fetch comment tree (single Algolia request)
        comment_data = fetch_comments(hn_id)
        comments_text = comment_data["flattened"] if comment_data else ""
        hn_item_json = comment_data["item"] if comment_data else None

        # Extract article body
        article_text = _fetch_article_text(item["article_url"], hn_item_json)

        # Synthesize
        synthesis_md = synthesize(
            title=item["title"],
            article_url=item["article_url"],
            article_text=article_text,
            comments_text=comments_text,
            points=item["points"],
            num_comments=item["num_comments"],
        )
        if not synthesis_md:
            logger.warning("Empty synthesis for hn_id=%s; skipping persist", hn_id)
            continue

        stats["synthesized"] += 1

        # Persist to global cache
        _persist_synthesis(conn, item, synthesis_md)

        # Fan out to every user's HN Synthesis feed
        for user_row in users:
            user_id = user_row["id"]
            feed_id = ensure_hn_feed(conn, user_id)
            _fan_out_to_user(conn, user_id, item, synthesis_md, feed_id)
            stats["fanned_out"] += 1

        # Commit after each story to keep write transactions short
        conn.commit()

    # 5. Trigger background embedding generation (best-effort)
    try:
        from services.feeds import embed_pending_feed_items_async

        for user_row in users:
            embed_pending_feed_items_async(user_row["id"])
    except Exception as exc:
        logger.warning("Could not trigger embedding generation: %s", exc)

    return stats
