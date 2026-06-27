# Runbook: Reset "last briefed" so a Signal brief can regenerate

Use this when you want to regenerate a daily Signal brief from articles that were
already used in a recent brief. Markly excludes any feed item briefed within the
last `SIGNAL_BRIEFED_EXCLUDE_DAYS` (default **7**) days, so those articles will not
reappear until you clear their `last_briefed_at` stamp.

## How it works (why this is needed)

- When a brief is saved, [`save_brief()`](../../backend/services/signal_pipeline.py)
  stamps every selected article with `last_briefed_at = <brief.created_at>` (the same
  timestamp for all items in that brief).
- Brief generation excludes recently briefed items via `_briefed_exclude_clause()`:
  ```sql
  AND (i.last_briefed_at IS NULL
       OR datetime(i.last_briefed_at) < datetime('now', '-7 days'))
  ```
- Setting `last_briefed_at = NULL` makes those articles eligible again. No app
  restart is required; the next brief generation picks them up.

A `[Safe Mode]` brief never stamps items, so there is nothing to clear for those.

## Where the database lives

| Environment | Path |
| --- | --- |
| Production (App Service container, Kudu SSH) | `/home/data/markly.db` (you land in `~/data`) |
| Local | `backend/markly.db` |

`'now'` is UTC and `datetime(last_briefed_at)` normalizes the stored `+00:00`
timestamps to UTC, so all comparisons below match the app's exclusion logic exactly.

---

## Option A: Reset the most recent brief's articles (rolling 24h window)

This clears every article briefed in the last day, for **all users**. Simplest and
matches "regenerate today's brief."

```bash
# 0. Back up first
cp markly.db "markly.db.bak.$(date +%Y%m%d_%H%M%S)"

# 1. Preview the count before writing
sqlite3 markly.db "SELECT COUNT(*) FROM feed_items WHERE datetime(last_briefed_at) >= datetime('now','-1 day');"

# 2. Clear them (prints number of rows changed)
sqlite3 markly.db "UPDATE feed_items SET last_briefed_at = NULL WHERE datetime(last_briefed_at) >= datetime('now','-1 day'); SELECT changes();"
```

Variants:
- "Since the start of yesterday" instead of a rolling 24h:
  `datetime('now','-1 day','start of day')`
- Restrict to one user: add `AND user_id = '<USER_ID>'` to the `WHERE` clause.

## Option B: Reset one specific brief's articles

Use when you want to free up exactly the articles from a known brief (any date),
not just the last 24 hours.

```bash
# 1. Find the brief and copy its id
sqlite3 markly.db "SELECT id, title, article_count, created_at FROM signal_briefs ORDER BY created_at DESC LIMIT 10;"

# 2. Preview the exact articles it used (should be ~article_count rows)
sqlite3 markly.db "SELECT fi.id, fi.title FROM feed_items fi WHERE fi.user_id = (SELECT user_id FROM signal_briefs WHERE id = '<BRIEF_ID>') AND fi.last_briefed_at = (SELECT created_at FROM signal_briefs WHERE id = '<BRIEF_ID>');"

# 3. Clear the stamp
sqlite3 markly.db "UPDATE feed_items SET last_briefed_at = NULL WHERE user_id = (SELECT user_id FROM signal_briefs WHERE id = '<BRIEF_ID>') AND last_briefed_at = (SELECT created_at FROM signal_briefs WHERE id = '<BRIEF_ID>'); SELECT changes();"
```

## Option C: Reset everything for a user (blunt)

Frees up **every** previously briefed article for that user, not just one brief.

```bash
sqlite3 markly.db "UPDATE feed_items SET last_briefed_at = NULL WHERE user_id = '<USER_ID>'; SELECT changes();"
```

---

## Notes & safety

- Always run the preview/count query before the `UPDATE`.
- These commands only un-stamp articles; they do **not** delete the old brief row.
  Regenerating creates a new brief and reconsiders the freed articles plus anything newer.
- The running app uses SQLite WAL mode, so writing live is safe. No restart needed.
- If you prefer not to edit the prod DB in place, see
  [Azure operations guide](../../.github/instructions/azure.instructions.md) for the
  pull/edit/push workflow.
