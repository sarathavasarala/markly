"""Feed discovery, parsing, and refresh service."""
from __future__ import annotations

import ipaddress
import logging
from datetime import datetime, timedelta, timezone
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

from database import new_id, row_to_dict, utc_now

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "markly-feed-radar/1.0 (+https://markly.azurewebsites.net)",
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*;q=0.8",
}
COMMON_FEED_PATHS = ("/feed/", "/feed.xml", "/rss/", "/rss.xml", "/atom.xml", "/index.xml")
REQUEST_TIMEOUT = 10
MAX_RESPONSE_BYTES = 2_000_000
MAX_ENTRIES_PER_FEED = 25


class FeedError(ValueError):
    """Raised when a URL cannot be used as a feed source."""


def _ensure_url(raw_url: str) -> str:
    url = raw_url.strip()
    if not url:
        raise FeedError("URL is required")
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise FeedError("Please enter a valid website or feed URL")
    _reject_private_host(parsed.hostname)
    return url


def _reject_private_host(hostname: str | None):
    if not hostname:
        raise FeedError("Please enter a valid website or feed URL")
    normalized = hostname.strip().lower().rstrip(".")
    if normalized == "localhost" or normalized.endswith(".localhost"):
        raise FeedError("Local feed URLs are not supported")
    try:
        ip = ipaddress.ip_address(normalized)
    except ValueError:
        return
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
        raise FeedError("Private network feed URLs are not supported")


def _fetch(url: str, *, etag: str | None = None, last_modified: str | None = None) -> requests.Response:
    headers = dict(HEADERS)
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True)
    response.raise_for_status()
    final_url = response.url or url
    parsed = urlparse(final_url)
    _reject_private_host(parsed.hostname)
    if len(response.content) > MAX_RESPONSE_BYTES:
        raise FeedError("Feed response is too large")
    return response


def _parse_feed_bytes(content: bytes, url: str):
    parsed = feedparser.parse(content)
    has_feed_shape = bool(parsed.get("version") or parsed.feed.get("title") or parsed.entries)
    if not has_feed_shape:
        raise FeedError(f"No RSS or Atom feed found at {url}")
    return parsed


def _feed_title(parsed, fallback_url: str) -> str:
    return parsed.feed.get("title") or urlparse(fallback_url).netloc or fallback_url


def _site_url(parsed, feed_url: str) -> str | None:
    link = parsed.feed.get("link")
    if link:
        return link
    parsed_url = urlparse(feed_url)
    return f"{parsed_url.scheme}://{parsed_url.netloc}" if parsed_url.netloc else None


def _favicon_url(site_url: str | None) -> str | None:
    if not site_url:
        return None
    domain = urlparse(site_url).netloc.replace("www.", "")
    return f"https://www.google.com/s2/favicons?domain={domain}&sz=64" if domain else None


def _candidate_urls(input_url: str, html: bytes | None = None) -> list[str]:
    candidates: list[str] = []
    if html:
        soup = BeautifulSoup(html, "lxml")
        for link in soup.find_all("link"):
            rel = " ".join(link.get("rel") or []).lower()
            feed_type = (link.get("type") or "").lower()
            href = link.get("href")
            if href and "alternate" in rel and feed_type in {
                "application/rss+xml",
                "application/atom+xml",
                "application/feed+json",
                "text/xml",
                "application/xml",
            }:
                candidates.append(urljoin(input_url, href))

    parsed = urlparse(input_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    candidates.extend(urljoin(base, path) for path in COMMON_FEED_PATHS)

    seen = set()
    ordered = []
    for candidate in [input_url, *candidates]:
        if candidate not in seen:
            ordered.append(candidate)
            seen.add(candidate)
    return ordered


def discover_feed(input_url: str) -> tuple[str, Any, requests.Response]:
    """Return the best feed URL, parsed feed, and response for a user-provided URL."""
    url = _ensure_url(input_url)
    first_response = _fetch(url)

    try:
        parsed = _parse_feed_bytes(first_response.content, first_response.url)
        return first_response.url, parsed, first_response
    except FeedError:
        pass

    candidates = _candidate_urls(first_response.url, first_response.content)
    last_error = "No RSS or Atom feed found"
    for candidate in candidates:
        if candidate == first_response.url:
            continue
        try:
            _ensure_url(candidate)
            response = _fetch(candidate)
            parsed = _parse_feed_bytes(response.content, response.url)
            return response.url, parsed, response
        except Exception as exc:
            last_error = str(exc)
            logger.debug("Feed candidate failed for %s: %s", candidate, exc)

    raise FeedError(last_error)


def add_feed(conn, user_id: str, input_url: str) -> dict[str, Any]:
    feed_url, parsed, response = discover_feed(input_url)
    now = utc_now()
    title = _feed_title(parsed, feed_url)
    site_url = _site_url(parsed, feed_url)

    existing = conn.execute(
        "SELECT * FROM feeds WHERE user_id = ? AND feed_url = ?",
        (user_id, feed_url),
    ).fetchone()
    if existing:
        feed = row_to_dict(existing)
        for entry in parsed.entries[:MAX_ENTRIES_PER_FEED]:
            _insert_entry(conn, user_id, feed["id"], entry)
        return feed

    feed_id = new_id()
    conn.execute(
        """
        INSERT INTO feeds (
            id, user_id, feed_url, title, site_url, favicon_url, etag,
            last_modified, failure_count, is_active, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 1, ?, ?)
        """,
        (
            feed_id,
            user_id,
            feed_url,
            title,
            site_url,
            _favicon_url(site_url),
            response.headers.get("ETag"),
            response.headers.get("Last-Modified"),
            now,
            now,
        ),
    )
    for entry in parsed.entries[:MAX_ENTRIES_PER_FEED]:
        _insert_entry(conn, user_id, feed_id, entry)
    row = conn.execute("SELECT * FROM feeds WHERE id = ?", (feed_id,)).fetchone()
    return row_to_dict(row)


def _entry_datetime(entry) -> str | None:
    struct_time = entry.get("published_parsed") or entry.get("updated_parsed")
    if not struct_time:
        return None
    return datetime(*struct_time[:6], tzinfo=timezone.utc).isoformat()


def _plain_summary(entry) -> str | None:
    raw = entry.get("summary") or entry.get("description")
    if not raw:
        return None
    text = BeautifulSoup(raw, "lxml").get_text(" ", strip=True)
    return unescape(text)[:1000] if text else None


def _entry_url(entry) -> str | None:
    link = entry.get("link")
    return link.strip() if isinstance(link, str) and link.strip() else None


def _entry_guid(entry, url: str) -> str:
    value = entry.get("id") or entry.get("guid") or url
    return str(value).strip() or url


def _insert_entry(conn, user_id: str, feed_id: str, entry) -> bool:
    url = _entry_url(entry)
    title = (entry.get("title") or "").strip()
    if not url or not title:
        return False

    now = utc_now()
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO feed_items (
            id, user_id, feed_id, guid, url, title, author, published_at,
            summary, status, first_seen_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?)
        """,
        (
            new_id(),
            user_id,
            feed_id,
            _entry_guid(entry, url),
            url,
            title,
            entry.get("author"),
            _entry_datetime(entry),
            _plain_summary(entry),
            now,
            now,
        ),
    )
    return cursor.rowcount > 0


def _should_skip_feed(feed: dict[str, Any], stale_after_minutes: int, force: bool) -> bool:
    if force or not feed.get("last_fetched_at"):
        return False
    try:
        fetched_at = datetime.fromisoformat(feed["last_fetched_at"])
    except ValueError:
        return False
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - fetched_at < timedelta(minutes=stale_after_minutes)


def refresh_feeds(
    conn,
    user_id: str,
    *,
    force: bool = False,
    stale_after_minutes: int = 30,
) -> dict[str, int]:
    """Fetch active feeds for a user and insert newly discovered inbox items."""
    rows = conn.execute(
        """
        SELECT * FROM feeds
        WHERE user_id = ? AND is_active = 1
        ORDER BY COALESCE(last_fetched_at, '') ASC, created_at ASC
        """,
        (user_id,),
    ).fetchall()

    checked = inserted = skipped = failed = unchanged = 0
    for row in rows:
        feed = row_to_dict(row)
        if _should_skip_feed(feed, stale_after_minutes, force):
            skipped += 1
            continue

        checked += 1
        now = utc_now()
        try:
            response = _fetch(
                feed["feed_url"],
                etag=None if force else feed.get("etag"),
                last_modified=None if force else feed.get("last_modified"),
            )
            if response.status_code == 304:
                unchanged += 1
                conn.execute(
                    "UPDATE feeds SET last_fetched_at = ?, updated_at = ?, last_error = NULL WHERE id = ? AND user_id = ?",
                    (now, now, feed["id"], user_id),
                )
                continue

            parsed = _parse_feed_bytes(response.content, response.url)
            for entry in parsed.entries[:MAX_ENTRIES_PER_FEED]:
                if _insert_entry(conn, user_id, feed["id"], entry):
                    inserted += 1

            conn.execute(
                """
                UPDATE feeds
                SET title = COALESCE(?, title),
                    site_url = COALESCE(?, site_url),
                    etag = ?,
                    last_modified = ?,
                    last_fetched_at = ?,
                    failure_count = 0,
                    last_error = NULL,
                    updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (
                    _feed_title(parsed, feed["feed_url"]),
                    _site_url(parsed, feed["feed_url"]),
                    response.headers.get("ETag"),
                    response.headers.get("Last-Modified"),
                    now,
                    now,
                    feed["id"],
                    user_id,
                ),
            )
        except Exception as exc:
            failed += 1
            logger.warning("Feed refresh failed for %s: %s", feed["feed_url"], exc)
            conn.execute(
                """
                UPDATE feeds
                SET failure_count = failure_count + 1,
                    last_error = ?,
                    last_fetched_at = ?,
                    updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (str(exc)[:500], now, now, feed["id"], user_id),
            )

    return {
        "feeds_checked": checked,
        "feeds_skipped": skipped,
        "feeds_failed": failed,
        "feeds_unchanged": unchanged,
        "items_added": inserted,
    }
