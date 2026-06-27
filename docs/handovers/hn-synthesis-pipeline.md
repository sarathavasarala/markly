# Handover: HN Synthesis Ingestion Pipeline

You are implementing a new background pipeline for **Markly** that ingests Hacker News
front-page stories, classifies the interesting ones, fetches their comment threads, runs
them through a "critical reader" LLM prompt, and lands the resulting synthesis as
readable feed items inside Markly.

Read `AGENTS.md` and `.github/instructions/backend.instructions.md` before writing code.
Implementation code is the source of truth; follow existing patterns over docs.

---

## 1. Goal & product intent

Build a pipeline that, every 12 hours:

1. Fetches the HN front page RSS: `https://hnrss.org/frontpage?comments=50`.
2. Looks at each item's title + brief description and **classifies** which ones qualify as
   *interesting news*, *product launch announcements*, or *factoids* (drop the rest).
3. For the selected items, fetches the **entire comment thread** for the HN item
   (e.g. `https://news.ycombinator.com/item?id=48689028`) — as a good citizen, in a
   single API request per story, not by scraping nested HTML.
4. Runs the article + comments through the **CRITICAL HN READER prompt** (provided in
   section 7) to produce a synthesis.
5. Surfaces the synthesis inside Markly so the owner can (a) **read each one individually**
   and (b) have them **assessed as candidates for the daily brief**.

This is **not** a public, subscribe-able RSS endpoint. The output must live inside Markly.

### Chosen architecture (decided — do not redesign)

Syntheses land as rows in the existing **`feed_items`** table, attached to a single
internal **"HN Synthesis"** feed per user. `feed_items` is the unit that powers both the
inbox/reader (individual reading) and `signal_pipeline.select_candidates` (daily-brief
candidates), so this one integration satisfies both requirements automatically.

To avoid re-running the LLM per user, synthesize **once globally** into a new
`hn_syntheses` cache table, then **fan out** cheap copies into each user's HN Synthesis
feed as `feed_items`.

---

## 2. How the existing system works (context you need)

- **Stack:** Flask 3 + SQLite, React/Vite frontend served same-origin in prod. Backend
  owns the DB at `MARKLY_DB_PATH`. Tests via `npm run test:backend` (pytest).
- **DB init:** Schema is procedurally created at startup in `backend/database.py`
  (NOT only `schema.sql`). Any new table must be added to the runtime init in
  `database.py`. Use `?` placeholders for all SQL params.
- **DB connections:** Use `db_session()` context manager for background/script code
  (already imported in `routes/cron.py` and `services/signal_pipeline.py`). Use
  `get_db()` only inside Flask request contexts.
- **Helpers in `backend/database.py`:** `new_id()`, `utc_now()`, `row_to_dict()`,
  `rows_to_dicts()`.
- **LLM access:** `backend/services/openai_service.py` →
  `AzureOpenAIService.get_signal_chat_client_and_model()` returns `(client, model)`.
  Call `client.chat.completions.create(model=model, messages=[...], response_format=...)`.
  Mirror the JSON-mode pattern in `signal_pipeline.llm_filter` (lines ~369-399).
- **Prompts:** Centralized in `class Prompts` in `backend/config.py` (around line 474).
  Add new prompt constants there.
- **Config:** `class Config` in `backend/config.py`. Add tunables there reading from env
  with sensible defaults.
- **Feed parsing reference:** `backend/services/feeds.py` shows the established pattern for
  fetching feeds (`_fetch`, size limits via `Config.FEED_MAX_RESPONSE_BYTES`, SSRF guard
  `_reject_private_host`, `feedparser.parse`, `_plain_summary`). Reuse/adapt these rather
  than inventing new HTTP code. Note `HEADERS` user-agent there.
- **Cron:** `backend/routes/cron.py` — routes gated by `_authenticate_cron()` against
  `Config.CRON_SECRET` (Bearer token). Existing routes `POST /cron/refresh` and
  `POST /cron/brief` iterate `SELECT id, email FROM users`. Mirror this structure.
- **feed_items schema (existing):** columns include `id, user_id, feed_id, guid, url,
  title, author, published_at, summary, content, content_format, status, bookmark_id,
  embedding, last_briefed_at, first_seen_at, updated_at`. `status='new'` items appear in
  the inbox. `content_format` is `'html' | 'markdown' | 'text'`. Insert with
  `INSERT OR IGNORE` keyed on a stable `guid` for dedup (see `feeds._insert_entry`).
- **feeds schema (existing):** `id, user_id, feed_url, title, site_url, favicon_url, etag,
  last_modified, last_fetched_at, failure_count, last_error, is_active, retention_limit,
  next_retry_at, created_at, updated_at`. `feed_url` is unique per user.
- **Inbox query** (`routes/feeds.py::inbox`) and brief candidate query both
  `JOIN feeds f ON f.id = i.feed_id`, so the synthesis items MUST have a real `feeds` row
  to be visible. They filter `status='new'` and exclude items whose URL already exists as a
  bookmark.

---

## 3. RSS item shape (already verified)

`hnrss.org/frontpage?comments=50` returns RSS 2.0 items like:

```
<title><![CDATA[ Previewing GPT-5.6 Sol: a next-generation model ]]></title>
<description><![CDATA[ <p>System card: <a href="...">...</a></p> <hr>
  <p>Comments URL: <a href="https://news.ycombinator.com/item?id=48689028">...</a></p>
  <p>Points: 946</p> <p># Comments: 581</p> ]]></description>
<link>https://openai.com/index/previewing-gpt-5-6-sol/</link>
<comments>https://news.ycombinator.com/item?id=48689028</comments>
<guid isPermaLink="false">https://news.ycombinator.com/item?id=48689028</guid>
```

Extraction rules per entry:
- `hn_id` — integer parsed from the `id=` query param of the `<comments>` (or `<guid>`) URL.
- `article_url` — `entry.link` (the real article; for Ask/Show HN with no external URL it
  equals the HN item URL).
- `title` — `entry.title`, stripped.
- `points` / `num_comments` — parse integers from the description text via regex
  (`Points:\s*(\d+)` and `#\s*Comments:\s*(\d+)`). Tolerate absence (default 0).
- `brief` — plain-text of the description for the classifier (reuse a `_plain_summary`-style
  BeautifulSoup strip; keep it short, ~500 chars).

---

## 4. Good-citizen comment fetching (Algolia HN API)

Do **not** scrape `news.ycombinator.com/item?id=` HTML. Use the official Algolia HN API:

```
GET https://hn.algolia.com/api/v1/items/{hn_id}
```

This returns the **entire nested comment tree** for the story in **one JSON request**.
Shape (recursive):

```json
{
  "id": 48689028,
  "title": "Previewing GPT-5.6 Sol",
  "url": "https://openai.com/...",
  "author": "minimaxir",
  "points": 946,
  "text": null,
  "children": [
    { "id": 1, "author": "alice", "text": "<p>HTML comment…</p>", "children": [ ... ] },
    ...
  ]
}
```

Requirements:
- Timeout + response size cap (reuse `Config.FEED_MAX_RESPONSE_BYTES` ceiling or a
  dedicated `HN_MAX_RESPONSE_BYTES`).
- Be polite: a small `time.sleep(Config.HN_FETCH_DELAY_SECONDS)` (default ~1.0s) between
  stories. One request per story; never fan out to comment permalinks.
- Flatten `children` depth-first into readable text. Strip HTML to text (BeautifulSoup,
  unescape entities). Include author attribution per comment, e.g.
  `[author]: text`, indented by depth. Skip `deleted`/`dead` nodes.
- Cap the flattened thread to a char budget (e.g. `Config.HN_COMMENTS_MAX_CHARS`, default
  ~40000) to control token cost; keep top-level + first levels preferentially (breadth-ish)
  rather than one deep chain. A simple depth-first cap is acceptable for v1 — document the
  choice.
- Set a descriptive `User-Agent` (reuse the `feeds.HEADERS` pattern).

---

## 5. Article content for the synthesis

The CRITICAL HN READER prompt wants the article text too. Reuse
`backend/services/content_extractor.py` → `ContentExtractor.extract(url)` to get the
article body (it already handles Jina + BeautifulSoup fallback). For Show/Ask HN posts
where `article_url` is the HN item itself, use the HN item's own `text` field from the
Algolia response as the "article" and skip extraction. Truncate article text to a budget
(reuse `signal_pipeline.truncate_article_content` or a local cap).

If article extraction fails, proceed with comments only and tell the prompt the article is
missing (the prompt explicitly handles missing inputs — do not fabricate).

---

## 6. Pipeline implementation

Create `backend/services/hn_synthesis.py` with pure, testable functions:

```python
def fetch_frontpage() -> list[dict]:
    """Fetch + parse hnrss frontpage into candidate dicts (hn_id, title, article_url,
    points, num_comments, brief, story_published_at)."""

def classify_items(items: list[dict]) -> list[dict]:
    """One JSON-mode LLM call. Return only items classified as interesting news /
    product launch / factoid, each annotated with `classification`. Cap to
    Config.HN_SYNTHESIS_MAX_ITEMS (default 8). Mirror signal_pipeline.llm_filter:
    response_format={"type":"json_object"}, system msg 'respond in valid JSON'. On error,
    log and fall back to top-N by points."""

def fetch_comments(hn_id: int) -> dict | None:
    """One Algolia request. Return {'item': <root json>, 'flattened': <str>} or None."""

def synthesize(title, article_url, article_text, comments_text, points, num_comments) -> str:
    """Run Prompts.HN_CRITICAL_READER_PROMPT. Return synthesis markdown. On error, log to
    telemetry_logs (see backend instructions) and return '' so the caller skips persisting."""

def run_hn_synthesis(conn) -> dict:
    """Orchestrate: fetch frontpage -> skip hn_ids already in hn_syntheses (within
    retention window) -> classify -> for each kept story: fetch article + comments,
    synthesize, INSERT into hn_syntheses -> fan out into every user's HN Synthesis feed as
    feed_items. Return a summary dict {stories_seen, classified, synthesized, fanned_out}."""
```

### `hn_syntheses` table (add to `database.py` runtime init + `schema.sql`)

```sql
CREATE TABLE IF NOT EXISTS hn_syntheses (
    id TEXT PRIMARY KEY,
    hn_id INTEGER NOT NULL UNIQUE,
    title TEXT NOT NULL,
    article_url TEXT,
    comments_url TEXT NOT NULL,
    points INTEGER DEFAULT 0,
    num_comments INTEGER DEFAULT 0,
    classification TEXT,
    synthesis_md TEXT NOT NULL,
    story_published_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hn_syntheses_created ON hn_syntheses(created_at);
```

### Internal HN Synthesis feed (per user)

- `ensure_hn_feed(conn, user_id) -> feed_id`: get-or-create a `feeds` row with sentinel
  `feed_url = 'markly-internal://hn-synthesis'`, `title = 'HN Synthesis'`,
  `is_active = 0` (so the normal refresher never HTTP-fetches it),
  `site_url = 'https://news.ycombinator.com/'`,
  `favicon_url` = HN favicon. Use `INSERT OR IGNORE` / select-then-insert keyed on
  `(user_id, feed_url)`.
- **Refresh guard:** In `backend/services/feeds.py::refresh_feeds`, the loop already filters
  `is_active = 1`, so `is_active=0` keeps it out. Additionally add an explicit guard: skip
  any feed whose `feed_url` starts with `markly-internal://` (defensive, in case it ever
  gets toggled active). Add a unit test for this guard.

### Fan-out into feed_items

For each synthesized story and each user:
```sql
INSERT OR IGNORE INTO feed_items
  (id, user_id, feed_id, guid, url, title, author, published_at,
   summary, content, content_format, status, first_seen_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'markdown', 'new', ?, ?)
```
- `guid` = `f"hn-synthesis:{hn_id}"` (stable dedup; distinct from any normal HN feed item).
- `url` = `article_url` (so the reader links to the source; matches inbox bookmark-dedup).
- `title` = story title (optionally prefix with classification label).
- `summary` = a 1-2 sentence plain-text teaser (first lines of the synthesis or the
  Executive Summary). Keep <= ~500 chars.
- `content` = the full synthesis markdown; `content_format='markdown'`.
- `published_at` = `story_published_at`.
- After insert, you may call `feeds.embed_pending_feed_items_async(user_id)` so the new
  items get embeddings for taste ranking (optional but consistent with `cron_refresh`).

### Cron route (in `routes/cron.py`)

```python
@cron_bp.route("/hn-synthesis", methods=["POST"])
def cron_hn_synthesis():
    if not _authenticate_cron():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        with db_session() as conn:
            summary = hn_synthesis.run_hn_synthesis(conn)
        return jsonify({"success": True, "summary": summary})
    except Exception as exc:
        logger.exception("HN synthesis cron failed")
        return jsonify({"error": str(exc)}), 500
```
Schedule it every 12h wherever `/cron/refresh` and `/cron/brief` are scheduled (check
`.github/instructions/azure.instructions.md` / deployment config for the existing cron
scheduler and add the new job there).

### Config additions (`backend/config.py`)

```python
HN_FRONTPAGE_URL = os.getenv("HN_FRONTPAGE_URL", "https://hnrss.org/frontpage?comments=50")
HN_ALGOLIA_ITEM_URL = "https://hn.algolia.com/api/v1/items/{id}"
HN_SYNTHESIS_MAX_ITEMS = int(os.getenv("HN_SYNTHESIS_MAX_ITEMS", "8"))
HN_FETCH_DELAY_SECONDS = float(os.getenv("HN_FETCH_DELAY_SECONDS", "1.0"))
HN_COMMENTS_MAX_CHARS = int(os.getenv("HN_COMMENTS_MAX_CHARS", "40000"))
HN_SYNTHESIS_RETENTION_HOURS = int(os.getenv("HN_SYNTHESIS_RETENTION_HOURS", "72"))
```

Add a classifier prompt constant `Prompts.HN_CLASSIFIER_PROMPT` (JSON-mode: given a numbered
list of `{id, title, brief, points, num_comments}`, return
`{"selected": [{"id": ..., "classification": "news|launch|factoid"}]}`; instruct it to drop
engagement bait, drama, low-signal meta, and pure opinion pieces) and the reader prompt
below.

---

## 7. CRITICAL HN READER PROMPT (store verbatim as `Prompts.HN_CRITICAL_READER_PROMPT`)

Provide the article + comment thread to this prompt as the user message. Store the text
below exactly (use a Python triple-quoted raw string; escape as needed). Pass article text
and flattened comments clearly labeled. The prompt already handles missing inputs — never
fabricate.

```
You are an expert analyst extracting high-signal insights from an article and its comment thread.

## Inputs

I will provide some or all of the following:
1. The article text, URL, or a description of its content
2. The Hacker News comment thread

If only a URL is given, work from it if you can access the content; if you cannot, say so plainly instead of guessing what the article says. If the article or the thread is missing, analyze what you have and note what's absent. If the thread is thin or low-signal, say that directly rather than inflating weak comments into false insight. Manufactured depth is worse than an honest "there isn't much here."

## Your job

Not to summarize the article. Explain what's really going on underneath:
- what smart practitioners noticed
- where the real value or tension lies
- which comments reveal deeper truths
- which assumptions deserve scrutiny
- what an intelligent reader should update their worldview on

Focus on non-obvious insights, incentives and business mechanics, the operational reality behind technical systems, strong arguments and counterarguments, hidden moats and network effects, useful mental models, expert corrections, first-hand practitioner experience, tradeoffs and second-order effects, practical implications, and the things people consistently misunderstand.

## Hard rules

- Never fabricate quotes, usernames, attributions, statistics, or facts not present in the source. If you can't quote something exactly, don't put it in quotation marks.
- Don't treat highly upvoted comments as automatically insightful.
- Scale your length to the substance available. Skip or merge sections when there isn't enough real material to fill them (for example, drop the disagreements section if there's no meaningful disagreement). Don't pad.
- When you're genuinely uncertain who's right, say so instead of forcing a verdict.

## Style

Write like a sharp industry insider explaining reality to another smart person. Prefer clear prose over bullet spam. Explain mechanisms, not just conclusions. Translate jargon into plain English. Use concrete examples and analogies when they help. Assume the reader is intelligent but not a specialist in the domain. Prioritize insight density. Be conversational but intellectually serious.

Avoid generic summaries, surface-level restatement of the article, low-effort snark, shallow consensus opinions, excessive formatting, consultant and corporate jargon, AI filler phrases, and unexplained buzzwords.

When discussing companies, products, or technologies, distinguish the visible product from the real business model. Explain where the moat actually comes from, what's hard to replicate versus easy to copy, and how incentives line up between the participants. Separate technical complexity from business complexity. Pay attention to distribution, trust, integrations, data, and operational scale.

## Output structure

### 0. Context You Need

A short briefing for a smart reader who may not know the company, technology, market, or background. Explain what the product actually is, roughly how the business works, why the topic matters, and any technical or historical context worth knowing, in plain English. One to four short paragraphs depending on complexity. This should make the rest of the analysis readable without prior domain knowledge.

### 1. Executive Summary

Five to eight bullets covering the most important ideas: the real economic or technical story, the strongest practitioner insights, what readers are most likely to misunderstand, and the major tensions.

### 2. Most Insightful Takeaways

For each, use:

**Takeaway: [short title]**

*Core idea* — explain it clearly in two to four tight paragraphs.

*Why it matters* — the broader significance, practical consequence, or strategic implication.

*Evidence* — quote the single strongest supporting line from the article or comments, with attribution to "the article" or "a commenter." If no single line captures it and the insight is synthesized across the thread, summarize that instead of forcing a quote.

Prioritize comments with deep operational knowledge, comments that change the framing, and comments that expose hidden incentives or assumptions.

### 3. Best Verbatim Quotes

The strongest exact quotes from the article or comments. For each: the quote, why it's insightful, and the broader principle it illustrates. Prefer quotes that compress a deep truth, reveal an industry reality, expose incentives, explain hidden dynamics, or challenge a naive assumption.

### 4. Key Disagreements

The most meaningful disagreements. For each: what side A believes, what side B believes, what the disagreement reveals, and which side seems more convincing and why (or that it's unresolved). Focus on disagreements that expose different mental models, lifecycle-stage thinking, operator versus outsider perspectives, technical versus business viewpoints, or competing incentives.

### 5. Hidden Assumptions

Assumptions the article or commenters make that aren't obvious. For each: the assumption, why it matters, and whether it seems justified. Look especially at assumptions about markets, incentives, scaling, AI, user behavior, regulation, data value, network effects, and technical feasibility.

### 6. Contrarian or Underrated Points

Thoughtful points that are overlooked, buried, unpopular but right, technically subtle, or economically important. Explain why each matters.

### 7. Final Synthesis

A nuanced conclusion. What's the real story underneath the surface narrative? What should an intelligent reader update their beliefs about? What incentives are driving the situation? What's likely underrated or misunderstood, and what should people watch for going forward? Don't end on a generic or motivational note. Aim for synthesis and worldview-level insight.
```

---

## 8. Tests (`backend/tests/test_hn_synthesis.py`)

Follow backend test rules: in-memory/temp SQLite, mock ALL network + LLM calls. Cover:

- `fetch_frontpage` parsing: feed a fixture RSS byte string (mock `requests.get`/`_fetch`),
  assert `hn_id`, `article_url`, `points`, `num_comments` extracted correctly, including an
  item missing Points/# Comments.
- `classify_items`: mock the OpenAI client to return a JSON object; assert only selected
  ids are kept, classifications attached, and cap honored. Also assert graceful fallback
  when the LLM call raises.
- `fetch_comments`: mock Algolia JSON (nested `children`); assert flattening includes
  authors, respects depth, skips deleted nodes, and honors `HN_COMMENTS_MAX_CHARS`.
- `synthesize`: mock OpenAI; assert prompt is sent and markdown returned; assert empty
  string + telemetry log on error.
- `ensure_hn_feed`: creates exactly one feed per user (idempotent), `is_active=0`,
  sentinel `feed_url`.
- `refresh_feeds` guard: a `markly-internal://` feed is never fetched even if toggled active
  (mock `_fetch` and assert it's not called for that feed).
- `run_hn_synthesis` end-to-end with everything mocked: inserts into `hn_syntheses`, fans
  out `feed_items` with `guid='hn-synthesis:<id>'`, `content_format='markdown'`,
  `status='new'`; second run is idempotent (no duplicate items, already-synthesized ids
  skipped).
- Cron auth: `POST /cron/hn-synthesis` returns 401 without the correct Bearer token, 200
  with it (mock `run_hn_synthesis`).

Run: `npm run test:backend`. Ensure no writes to the real `markly.db`.

---

## 9. Docs & guardrails

- Update `ARCHITECTURE.md`: add `hn_syntheses` to the ER map, the internal HN Synthesis
  feed, the pipeline data flow, and the new cron route. Update in the SAME change.
- Update the cron section of `.github/instructions/azure.instructions.md` (and the
  deployment scheduler config) to include the 12h `/cron/hn-synthesis` job.
- Conventional commit, e.g. `feat: add HN synthesis ingestion pipeline`.
- Do NOT commit secrets. `CRON_SECRET` must be set in prod for the route to work.
- This adds a DB table + an internal feed row — already approved by the repo owner.

## 10. Acceptance criteria

- [ ] `POST /cron/hn-synthesis` (with valid `CRON_SECRET`) fetches the front page,
      classifies, synthesizes ≤8 stories, and creates `feed_items` in each user's
      "HN Synthesis" feed with the synthesis as markdown `content`.
- [ ] Comments fetched via a single Algolia request per story, with polite throttling; HN
      HTML is never scraped.
- [ ] Items are readable in the inbox/reader and appear as daily-brief candidates.
- [ ] Re-running within the retention window does not duplicate work or items.
- [ ] The internal feed is never HTTP-fetched by `refresh_feeds`.
- [ ] All new tests pass under `npm run test:backend` with no real network/LLM/DB writes.
