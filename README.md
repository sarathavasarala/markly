# markly

**Your daily brief from the blogs and newsletters you follow.**

markly follows the blogs and newsletters you care about and turns them into one synthesized brief, instead of another endless feed. Read what's worth your time, save what you want to keep, and let your saved reading become a list other people can follow.

**Live app:** [markly.azurewebsites.net](https://markly.azurewebsites.net/)

**Example public profile:** [@sarathavasarala](https://markly.azurewebsites.net/@sarathavasarala)

## Why markly exists

The internet is full of thoughtful writing, but keeping up with it often turns into inbox clutter, unread tabs, and feeds that never end. markly gives you a quieter way to follow the sources you trust.

It brings your blogs and newsletters together, turns new posts into a daily brief, helps you save the pieces worth keeping, and gives you a public reading list you can share.

## What you can do with markly

- Start the day with a synthesized brief from the sources you follow.
- Follow blogs, newsletters, and publications in one place.
- Browse new posts before deciding what deserves your attention.
- Save articles into a personal reading library.
- Let markly summarize, tag, archive, and suggest folders for saved links.
- Search your library by keyword, folder, topic, domain, and content type.
- Turn selected bookmarks into a public `/@username` reading list.
- Let visitors subscribe to your public profile or save public links into their own library.

## How it works

markly is built around a few core reading workflows:

**Daily brief.** markly looks at recent posts from your followed feeds, filters for the items that match your briefing preferences, extracts the useful article text, and writes a concise briefing with source links. You can adjust your briefing preferences and, if you want deeper control, customize the prompts and article limits used by the brief pipeline.

When enabled, Daily Brief tracing records the major generation stages to an external trace sink. markly owns the trace interface and Langfuse is only the first adapter, so traces can later be sent elsewhere without rewriting the brief pipeline.

**Sources.** Add RSS feeds for the blogs, newsletters, and publications you care about. Sources keeps an inbox of new posts, lets you read clean article content inline, and gives you quick actions to save or dismiss each item.

**Topic clusters.** markly can group related feed items into active clusters and generate focused reports from multiple sources, so a developing topic is easier to understand than a pile of isolated links.

**Saved reading library.** When you save a link, markly extracts the page, stores an archive copy when possible, enriches it with AI-generated metadata, and keeps it searchable. Saved bookmarks can include summaries, key quotes, tags, content type, intent, technical level, thumbnails, favicons, and suggested folders.

**Public reading lists.** Every user can publish selected bookmarks to a public `/@username` profile. Public profiles include topic filters, subscriber capture, owner subscriber management, social sharing metadata, and a save-to-your-library flow for signed-in visitors.

## Tech Stack

| Layer | Stack |
| --- | --- |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Zustand, React Router, Axios, Lucide icons |
| Backend | Python Flask 3, Flask-CORS, Flask-Compress, Gunicorn |
| Database | SQLite owned by the Flask backend, including FTS5 for keyword search |
| AI and extraction | Azure OpenAI, optional brief-specific model overrides, optional stored embeddings, optional Jina Reader, BeautifulSoup/newspaper/lxml fallback extraction |
| AI observability | Optional Daily Brief tracing via a portable Markly trace adapter with Langfuse as the first sink |
| Auth | Google OAuth with Flask cookie sessions, optional email allowlist, optional local dev auth bypass |
| Background work | Flask routes plus background thread executors for enrichment, archiving, feed embeddings, and scheduled cron endpoints |
| Testing | Pytest, Vitest, React Testing Library, Playwright |
| Deployment | Multi-stage Docker image deployed to Azure App Service |

## Architecture

The production container builds the Vite frontend first, then copies `frontend/dist` into `backend/static`. Flask serves both `/api/*` routes and the built single-page app from the same origin, so production uses relative `/api` requests and does not need a separate frontend host.

The backend initializes or migrates the SQLite schema at startup using `MARKLY_DB_PATH`. Local development defaults to `backend/markly.db`; Azure App Service should use persistent storage such as `/home/data/markly.db`.

Main API areas:

- `/api/auth` handles Google login, callback, logout, and current session state.
- `/api/bookmarks` handles analyze, create, list, update, delete, access tracking, retry enrichment, archive retry, and save-public flows.
- `/api/folders` handles folder CRUD.
- `/api/search` handles SQLite FTS keyword search and optional semantic mode.
- `/api/stats` returns top tags.
- `/api/public` powers public profiles, public bookmarks, subscriptions, visibility changes, subscriber management, and account deletion.
- `/api/feeds` handles RSS feed registration, refresh, inbox, item dismissal, saved-item marking, and clean content retrieval.
- `/api/signal` powers daily brief generation, briefing preferences, prompt settings, history retrieval, and brief deletion.
- `/api/clusters` handles topic clusters and cluster report generation.
- `/api/cron` exposes token-protected feed refresh and daily brief generation endpoints.
- `/api/health` returns the service health check.

Public profile pages are served at `/@username`. The Flask app injects profile-specific Open Graph and Twitter metadata server-side so shared profile links render with the right title, description, avatar, and bookmark count.

## Running Locally

### Prerequisites

- Node.js 18+ for root scripts and frontend tooling.
- Python 3.10+ for local development. The Docker runtime uses Python 3.11.
- Azure OpenAI endpoint and key for AI enrichment and daily brief generation.
- Google OAuth credentials for normal login, or `DEV_BYPASS_AUTH=true` for local-only development.

### Setup

```bash
git clone https://github.com/sarathavasarala/markly.git
cd markly

npm run setup

cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Update `backend/.env` with the backend settings you need. For local Vite development, keep `frontend/.env` pointed at the Flask API:

```bash
VITE_API_URL=http://localhost:5050/api
```

Start both dev servers:

```bash
npm start
```

The Flask API runs on `http://localhost:5050` and Vite runs on `http://localhost:5173`. Vite proxies `/api` to Flask during development.

### Google OAuth Callback

For local development, add this redirect URI to your Google OAuth client:

```text
http://localhost:5173/api/auth/google/callback
```

For production on Azure App Service, use:

```text
https://<your-app>.azurewebsites.net/api/auth/google/callback
```

Set `OAUTH_REDIRECT_BASE_URL` to the same base origin, for example `http://localhost:5173` locally or `https://<your-app>.azurewebsites.net` in production.

### Local Auth Bypass

For local development only, you can skip Google OAuth:

```bash
DEV_BYPASS_AUTH=true
DEV_BYPASS_EMAIL=you@example.com
DEV_BYPASS_NAME=Your Name
```

Do not enable this in any deployed environment.

## Configuration

The checked-in examples are [backend/.env.example](backend/.env.example) and [frontend/.env.example](frontend/.env.example). Do not commit real `.env` files.

### Backend Essentials

| Variable | Purpose |
| --- | --- |
| `APP_ENV` | Selects `backend/.env.<APP_ENV>` when present, otherwise falls back to `backend/.env`. Defaults to `prod`. |
| `MARKLY_DB_PATH` | Path to the SQLite database. Defaults to `backend/markly.db` when unset. |
| `SQLITE_JOURNAL_MODE` | SQLite journal mode. Azure App Service should use `DELETE`. |
| `FLASK_SECRET_KEY` | Secret used by Flask sessions. Use a strong random value outside local dev. |
| `FLASK_DEBUG` | Enables Flask debug behavior when set to `true`. |

### Sign-In and Access

| Variable | Purpose |
| --- | --- |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID. |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret. |
| `OAUTH_REDIRECT_BASE_URL` | Base URL used to build the OAuth callback. |
| `ALLOWED_EMAILS` | Optional comma-separated allowlist. When unset, any Google-authenticated user can sign in. |
| `DEV_BYPASS_AUTH` | Local-only login bypass. Must stay false or unset in production. |
| `DEV_BYPASS_EMAIL` | Optional email for the local bypass user. |
| `DEV_BYPASS_NAME` | Optional name for the local bypass user. |

### AI, Extraction, and Search

| Variable | Purpose |
| --- | --- |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI resource endpoint. |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key. |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Main chat model deployment for enrichment and brief generation. |
| `AZURE_OPENAI_NANO_DEPLOYMENT_NAME` | Optional cheaper model for bulk or lightweight operations. |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME` | Embedding model deployment. |
| `AZURE_OPENAI_API_VERSION` | API version for chat/completions calls. |
| `AZURE_OPENAI_EMBEDDING_API_VERSION` | API version for embedding calls. |
| `ENABLE_EMBEDDINGS` | Stores embeddings for bookmarks and feed items when enabled. |
| `ENABLE_SEMANTIC_SEARCH` | Enables semantic bookmark search. Keyword search remains the default. |
| `JINA_READER_API_KEY` | Optional Jina Reader key for stronger article extraction. |
| `PARALLEL_API_KEY` | Optional Parallel Search key used by Signal web research. |

### Daily Briefs and Topic Clusters

| Variable | Purpose |
| --- | --- |
| `SIGNAL_AZURE_OPENAI_API_KEY` | Optional Signal-specific Azure OpenAI API key. Falls back to the main Azure key when unset. |
| `SIGNAL_AZURE_OPENAI_ENDPOINT` | Optional Signal-specific Azure OpenAI endpoint. |
| `SIGNAL_AZURE_OPENAI_DEPLOYMENT_NAME` | Optional Signal-specific model deployment. |
| `SIGNAL_AZURE_OPENAI_API_VERSION` | Optional Signal-specific API version. |
| `SIGNAL_CANDIDATE_LIMIT` | Number of recent feed items considered before filtering. |
| `SIGNAL_MAX_SYNTHESIS_ARTICLES` | Maximum number of selected articles used in a generated brief. |
| `SIGNAL_BRIEF_PLANNING_ENABLED` | Enables an intermediate planning step before synthesis. |
| `SIGNAL_RECENCY_HALF_LIFE_DAYS` | Recency weighting used when ranking embedded candidates. |
| `SIGNAL_CANDIDATE_POOL_MULTIPLIER` | Expands the recent candidate pool before ranking. |
| `SIGNAL_BRIEFED_EXCLUDE_DAYS` | Avoids repeating items already used in recent briefs. |
| `SIGNAL_EMBED_MIN_COVERAGE` | Minimum embedding coverage before embedding ranking is used. |
| `SIGNAL_CONTENT_MAX_CHARS` | Maximum extracted article text passed into Signal synthesis. |
| `SIGNAL_CONTENT_HEAD_CHARS` | Leading article text retained when truncating long content. |
| `SIGNAL_CONTENT_TAIL_CHARS` | Trailing article text retained when truncating long content. |
| `SIGNAL_EMBED_MAX_PER_RUN` | Per-refresh cap for feed item embedding work. |
| `CLUSTER_LOOKBACK_DAYS` | Feed item lookback window for Radar clusters. |
| `CLUSTER_MAX_CANDIDATES` | Maximum candidate feed items considered during clustering. |
| `CLUSTER_MIN_ARTICLES` | Minimum article count for a cluster. |
| `CLUSTER_SIMILARITY_THRESHOLD` | Similarity threshold used for candidate grouping. |
| `CLUSTER_ARCHIVE_AFTER_DAYS` | Auto-archives inactive clusters after this many days. |
| `CLUSTER_EMBED_MAX_PER_RUN` | Per-run cap for cluster embedding work. |
| `CLUSTER_MAX_SYNTHESIS_ARTICLES` | Maximum articles used in a generated cluster report. |

### Daily Brief Tracing

Daily Brief tracing is disabled by default and stores no bulky trace payloads in SQLite. When enabled with Langfuse, markly sends trace data directly to Langfuse and keeps the production `.db` lean.

| Variable | Purpose |
| --- | --- |
| `BRIEF_TRACING_ENABLED` | Enables Daily Brief trace capture when set to `true`. Defaults to `false`. |
| `BRIEF_TRACE_SINK` | Trace sink adapter. Use `langfuse` for Langfuse Cloud, or leave as `noop` to disable external tracing. |
| `LANGFUSE_PUBLIC_KEY` | Langfuse project public key. |
| `LANGFUSE_SECRET_KEY` | Langfuse project secret key. |
| `LANGFUSE_BASE_URL` | Langfuse host. Use `https://cloud.langfuse.com` for the default cloud region, or the region-specific/self-hosted URL. |

To start with Langfuse Hobby:

```bash
BRIEF_TRACING_ENABLED=true
BRIEF_TRACE_SINK=langfuse
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

The traced stages are settings load, candidate selection, LLM filtering, content extraction, optional planning, background research, synthesis, optional style editing, and final brief save. Candidate traces include feed metadata, titles, summaries, URLs, selected IDs, and compact extraction statistics. Selected article content is limited to the exact truncated text passed into Signal synthesis, not the full raw article body.

The Signal route calls [backend/services/brief_tracing.py](backend/services/brief_tracing.py), not Langfuse directly. To switch sinks later, add a new adapter behind the same interface and change `BRIEF_TRACE_SINK`.

### Feeds, Archives, and Cron

| Variable | Purpose |
| --- | --- |
| `CRON_SECRET` | Bearer token required by `/api/cron/refresh` and `/api/cron/brief`. |
| `ARCHIVE_MAX_CHARS` | Maximum archived content length stored per bookmark. |
| `ARCHIVE_BACKFILL_BATCH_SIZE` | Batch size for archive backfill scripts. |
| `FEED_RADAR_ITEMS_PER_SOURCE` | Feed item limit per source during refresh. (internal config name) |
| `FEED_MAX_FAILURES` | Failure count before a feed is skipped/backed off. |
| `FEED_BACKOFF_BASE_MINUTES` | Initial feed refresh backoff window. |
| `FEED_BACKOFF_MAX_MINUTES` | Maximum feed refresh backoff window. |

### Frontend

| Variable | Purpose |
| --- | --- |
| `VITE_API_URL` | Local Vite API target, usually `http://localhost:5050/api`. |

In production, the frontend is served by Flask from the same origin and falls back to `/api`, so a frontend env file is usually only needed for local Vite development.

## Database

SQLite is the source of truth, and the app creates the required tables and indexes automatically when Flask starts.

The database stores users, folders, bookmarks, bookmark archives, feed sources, feed items, daily briefs, topic clusters, public-profile subscribers, telemetry logs, and SQLite FTS search rows. JSON-like fields such as `auto_tags`, `key_quotes`, and embeddings are serialized into SQLite text columns and converted back into API JSON responses.

For Azure App Service, set:

```bash
WEBSITES_ENABLE_APP_SERVICE_STORAGE=true
MARKLY_DB_PATH=/home/data/markly.db
SQLITE_JOURNAL_MODE=DELETE
```

Keep a periodic backup of `/home/data/markly.db`. For small personal deployments, a manual download is enough to start; scheduled copy to Azure Blob Storage is safer as usage grows.

## Available Commands

| Command | What it does |
| --- | --- |
| `npm run setup` | Create the Python virtualenv and install backend/frontend dependencies |
| `npm start` | Start Flask on port 5050 and Vite on port 5173 |
| `npm run start:test` | Start the test backend on port 5051 and test frontend on port 5274 |
| `npm run backend` | Start only the Flask backend |
| `npm run frontend` | Start only the Vite frontend |
| `npm run test` | Run backend Pytest and frontend Vitest suites |
| `npm run test:backend` | Run backend Pytest suite |
| `npm run test:frontend` | Run frontend Vitest suite |
| `npm run test:e2e` | Run Playwright E2E tests |
| `npm run lint` | Run frontend ESLint and backend flake8 |
| `npm run stop` | Kill local processes on ports 5050 and 5173 |

## Testing

Backend tests live in [backend/tests](backend/tests) and use Pytest with temporary SQLite databases. Frontend unit/component tests live next to components under `frontend/src` and run with Vitest/jsdom. E2E tests live in [frontend/e2e](frontend/e2e) and run with Playwright.

For local E2E testing, run this from the `frontend/` directory if you only have Chromium installed:

```bash
npx playwright test --project=chromium
```

The frontend build command is:

```bash
cd frontend && npm run build
```

That runs TypeScript first, then builds the Vite app.

## Deployment

The [Dockerfile](Dockerfile) uses a multi-stage build:

1. Build the React/Vite app with Node 18.
2. Install Python backend dependencies in a slim Python 3.11 image.
3. Copy the built frontend into `backend/static`.
4. Start Flask with Gunicorn on port `8000`.

Build and push an image for Azure or another container host:

```bash
docker build --platform linux/amd64 -t <registry>/<image>:latest .
docker push <registry>/<image>:latest
```

On Azure App Service, configure the app to expose port `8000`, enable persistent App Service storage, set `MARKLY_DB_PATH=/home/data/markly.db`, set `SQLITE_JOURNAL_MODE=DELETE`, and add the backend environment variables listed above. More deployment notes are in [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).

## Project Structure

```text
markly/
|-- backend/
|   |-- app.py                 # Flask app factory, API registration, SPA serving, profile OG injection
|   |-- config.py              # Environment-driven configuration
|   |-- database.py            # SQLite connection, schema initialization, row serialization
|   |-- routes/                # Auth, bookmarks, folders, search, stats, public, feeds, signal, clusters, cron
|   |-- services/              # Extraction, enrichment, archives, feeds, Signal, clustering, Azure OpenAI
|   |-- scripts/               # One-time/backfill utilities
|   `-- tests/                 # Backend Pytest suite
|-- frontend/
|   |-- src/pages/             # Dashboard, Search, Radar, PublicProfile, Login, BookmarkReader
|   |-- src/components/        # Bookmark cards/rows, folders, modals, layout, topics, feeds, signal
|   |-- src/stores/            # Zustand auth, bookmarks, folders, UI state
|   `-- e2e/                   # Playwright specs
|-- Dockerfile                 # Production container build
|-- DEPLOYMENT_GUIDE.md        # Container and Azure deployment notes
`-- package.json               # Root orchestration scripts
```

## License

[GNU Affero General Public License v3.0](LICENSE)