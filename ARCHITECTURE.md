# Markly Architecture & Data Flow Guide

This document maps the database models, integration pipelines, and authentication flows of `markly` to provide a mental model of the system for developers and AI agents.

Implementation code is the source of truth. If this guide disagrees with the current code, follow the code and update this document in the same change.

---

## 🗄️ Database Entity-Relationship Map
The SQLite schema is initialized procedurally in [database.py](backend/database.py). Below is a mapping of tables, constraints, and relationships:

```mermaid
erDiagram
    users {
        text id PK
        text email UNIQUE
        text username UNIQUE
        text full_name
        text avatar_url
        text taste_profile
        integer signal_candidate_limit
        text signal_filter_prompt
        text signal_synthesis_prompt
        text created_at
        text updated_at
    }

    folders {
        text id PK
        text user_id FK "REFERENCES users(id) ON DELETE CASCADE"
        text name
        text icon
        text color
        text created_at
        text updated_at
    }

    bookmarks {
        text id PK
        text user_id FK "REFERENCES users(id) ON DELETE CASCADE"
        text url
        text domain
        text original_title
        text clean_title
        text favicon_url
        text thumbnail_url
        text raw_notes
        text user_description
        text ai_summary
        text content_extract
        text key_quotes "serialized JSON string"
        text auto_tags "serialized JSON string"
        text intent_type
        text technical_level
        text content_type
        text embedding "serialized JSON string"
        text archive_content
        text archive_format
        text archive_status
        text archive_error
        text archived_at
        integer archive_word_count
        integer archive_char_count
        integer access_count
        text enrichment_status
        text enrichment_error
        integer is_public
        text folder_id FK "REFERENCES folders(id) ON DELETE SET NULL"
        text suggested_folder_name
        text created_at
        text updated_at
        text last_accessed_at
    }

    subscribers {
        text id PK
        text curator_username
        text email
        text subscribed_at
        text unsubscribed_at
    }

    feeds {
        text id PK
        text user_id FK "REFERENCES users(id) ON DELETE CASCADE"
        text feed_url
        text title
        text site_url
        text favicon_url
        text etag
        text last_modified
        text last_fetched_at
        integer failure_count
        text last_error
        integer is_active
        integer retention_limit
        text created_at
        text updated_at
    }

    feed_items {
        text id PK
        text user_id FK "REFERENCES users(id) ON DELETE CASCADE"
        text feed_id FK "REFERENCES feeds(id) ON DELETE CASCADE"
        text guid
        text url
        text title
        text author
        text published_at
        text summary
        text content
        text content_format
        text status
        text bookmark_id FK "REFERENCES bookmarks(id) ON DELETE SET NULL"
        text embedding
        text last_briefed_at
        text first_seen_at
        text updated_at
    }

    signal_briefs {
        text id PK
        text user_id FK "REFERENCES users(id) ON DELETE CASCADE"
        text content
        integer article_count
        text created_at
    }

    hn_syntheses {
        text id PK
        integer hn_id UNIQUE
        text title
        text article_url
        text comments_url
        integer points
        integer num_comments
        text classification
        text synthesis_md
        text story_published_at
        text created_at
        text updated_at
    }

    bookmarks_fts {
        text bookmark_id UNINDEXED
        text user_id UNINDEXED
        text body
    }

    users ||--o{ folders : "owns"
    users ||--o{ bookmarks : "owns"
    users ||--o{ feeds : "subscribes"
    users ||--o{ feed_items : "receives"
    users ||--o{ signal_briefs : "generates"
    folders ||--o{ bookmarks : "groups"
    feeds ||--o{ feed_items : "delivers"
    bookmarks ||--o| feed_items : "originates"
    bookmarks ||--o| bookmarks_fts : "indexes"
    hn_syntheses ||--o{ feed_items : "fans out to"
```

> **Internal HN Synthesis feed:** Each user has one internal `feeds` row with `feed_url = 'markly-internal://hn-synthesis'` and `is_active = 0`. `hn_syntheses` rows are fanned out as `feed_items` attached to this feed so syntheses appear in the inbox and are included as daily-brief candidates. The internal feed is never HTTP-fetched by `refresh_feeds`.

---

## 🔑 Authentication Flow (Google OAuth)
Authentication utilizes Google OAuth with cookie sessions managed by the Flask backend.

```mermaid
sequenceDiagram
    autonumber
    actor User as Developer / Browser
    participant FE as React Frontend (Vite)
    participant BE as Flask Backend (app.py)
    participant GO as Google OAuth Service

    User->>FE: Click "Login with Google"
    FE->>BE: GET /api/auth/google/login
    BE->>User: Redirect to Google authorization URI
    User->>GO: Authenticate credentials
    GO->>BE: Redirect with authorization code to callback route
    Note over BE: /api/auth/google/callback
    BE->>GO: Exchange code for user token info (email, full name, avatar)
    BE->>BE: Check ALLOWED_EMAILS restriction
    BE->>BE: upsert_user() record in SQLite
    BE->>BE: Establish session cookie (client side cookie)
    BE->>FE: Redirect back to SPA home
    FE->>BE: GET /api/auth/me (validates session state)
    BE->>FE: Return {is_authenticated: true, user: {...}}
```

---

## ⚡ Bookmark Enrichment & Archiving Pipeline
Saving bookmarks starts an asynchronous background workflow that parses content and generates AI metadata.

```mermaid
flowchart TD
    A[Frontend: POST /api/bookmarks] --> B[Backend: Create bookmark in SQLite with status 'pending']
    B --> C[Trigger background extraction task]
    C --> D{Has Jina API Key?}
    D -- Yes --> E[Query r.jina.ai/URL]
    D -- No --> F[Fallback: Fetch page & parse via BeautifulSoup]
    E --> G{Extraction successful?}
    F --> G
    G -- Yes --> H[Clean & extract article text]
    G -- No --> I[Set status 'failed']
    H --> J[Call Azure OpenAI ChatCompletion]
    J --> K[Generate Title, AI Summary, Key Quotes, suggested tags & intent]
    K --> L[Optional: Generate text embedding vector]
    L --> M[Update SQLite: status 'completed', save metadata & content]
    M --> N[refresh_bookmark_fts: Index content into Full-Text-Search virtual table]
```

---

## 📊 SSE Daily Brief Synthesis Flow (Signal)
The Signal briefing compiles high-signal feed items into a unified daily memo using Server-Sent Events (SSE).

```mermaid
sequenceDiagram
    autonumber
    actor User as Browser Client
    participant BE as Flask Backend (/api/briefs/generate)
    participant DB as SQLite DB
    participant AI as Azure OpenAI Service

    User->>BE: POST request (SSE connection request)
    BE->>User: Establish stream_with_context (text/event-stream)
    BE->>DB: Query user's followed feeds & recent feed_items
    BE->>User: Event: stage: 'scanning'
    BE->>AI: Filter candidates using user's Taste Profile (llm_filter)
    BE->>User: Event: stage: 'filtering'
    AI-->>BE: Return selected item IDs
    BE->>User: Event: stage: 'filtered' (lists selected article titles)
    loop For each selected article
        BE->>BE: Run full text extraction (Jina / BS4 fallback)
        BE->>User: Event: stage: 'extracting' (tracks progress index)
    end
    BE->>DB: persist_content_updates() (Save extracted text to feed_items)
    BE->>User: Event: stage: 'synthesizing'
    BE->>AI: Call synthesis engine (compile memo using thematic templates & inline URLs)
    AI-->>BE: Return Markdown synthesis memo
    opt Humanizer Pass (SIGNAL_HUMANIZER_ENABLED = True)
        BE->>User: Event: stage: 'humanizing'
        BE->>AI: Call Humanizer model (rewrite brief using custom copyediting rules to remove AI patterns)
        AI-->>BE: Return humanized Markdown brief
    end
    BE->>DB: save_brief() (Commit brief to signal_briefs)
    BE->>User: Event: stage: 'complete' (Return final brief data)
```

---

## 🔶 HN Synthesis Pipeline

A background cron pipeline (`POST /api/cron/hn-synthesis`, every 12 h) ingests Hacker News front-page stories, synthesizes them with a "critical reader" LLM prompt, and lands results as `feed_items` in each user's internal **HN Synthesis** feed. Syntheses are cached in `hn_syntheses` (synthesized once globally) then fanned out cheaply per user.

```mermaid
sequenceDiagram
    autonumber
    participant Scheduler as Cron Scheduler
    participant BE as Flask Backend (/api/cron/hn-synthesis)
    participant HNRSS as hnrss.org/frontpage
    participant Algolia as Algolia HN API
    participant CE as ContentExtractor
    participant AI as Azure OpenAI
    participant DB as SQLite DB

    Scheduler->>BE: POST /api/cron/hn-synthesis (Bearer CRON_SECRET)
    BE->>DB: Load already-synthesized hn_ids (within 72h retention window)
    BE->>HNRSS: Fetch front page RSS (comments=50)
    HNRSS-->>BE: RSS feed (titles, points, comment counts, article URLs)
    BE->>AI: Classify items (JSON mode — news / launch / factoid; drop noise)
    AI-->>BE: Selected items with classification labels (max 8)
    loop For each selected story
        BE->>Algolia: GET /api/v1/items/{hn_id} (single request — full comment tree)
        Algolia-->>BE: Nested comment tree JSON
        BE->>BE: Flatten comments (depth-first, char budget)
        BE->>CE: Extract article text (Jina / BS4 fallback)
        CE-->>BE: Article body markdown/text
        BE->>AI: CRITICAL HN READER prompt (article + flattened comments)
        AI-->>BE: Synthesis markdown
        BE->>DB: INSERT INTO hn_syntheses (global cache)
        loop For each user
            BE->>DB: ensure_hn_feed() — get-or-create internal feed row
            BE->>DB: INSERT OR IGNORE INTO feed_items (guid='hn-synthesis:{hn_id}')
        end
    end
    BE->>Scheduler: {stories_seen, classified, synthesized, fanned_out}
```

**Key properties:**
- Comments fetched via a single Algolia API request per story; HN HTML is never scraped.
- Internal feed `markly-internal://hn-synthesis` has `is_active=0` and is explicitly skipped by `refresh_feeds`.
- `guid = 'hn-synthesis:{hn_id}'` and `url = comments_url` ensure deduplication across runs.
- Syntheses appear in the inbox and are candidates for `select_candidates` (daily brief).
