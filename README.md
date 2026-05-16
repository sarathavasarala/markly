# markly

**A smarter way to save links.**

markly is a personal bookmark library that turns saved links into searchable, organized reading lists. Paste a URL, optionally add your own notes or description, and markly extracts page metadata, enriches it with Azure OpenAI, suggests tags and folders, and keeps everything in a private SQLite-backed library that can also power a public profile.

**Live app:** [markly.azurewebsites.net](https://markly.azurewebsites.net)

**Example public profile:** [@sarathavasarala](https://markly.azurewebsites.net/@sarathavasarala)

## What It Does

**AI bookmark enrichment.** markly extracts titles, domains, favicons, thumbnails, readable page content, summaries, key quotes, tags, content type, intent, technical level, and suggested folders. Jina Reader can be enabled for stronger extraction, with BeautifulSoup as the built-in fallback.

**Fast search and filtering.** Search currently defaults to keyword/SQLite FTS5 and records recent search history. Embeddings can still be generated and stored for future semantic search by enabling the feature flags.

**Folder and topic organization.** Bookmarks can be grouped into folders, viewed as folder cards, grid cards, or list rows, and filtered by top tags globally or within a folder.

**Public reading lists.** Each user gets a public `/@username` profile with public/private bookmark visibility, topic filters, subscriber capture, subscriber management for the owner, and social sharing metadata injected server-side for profile URLs.

**Save from other profiles.** Authenticated visitors can save a public bookmark from someone else's profile into their own collection.

## Tech Stack

| Layer | Stack |
| --- | --- |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Zustand, React Router, Axios, Lucide icons |
| Backend | Python Flask 3, Flask-CORS, Flask-Compress, Gunicorn |
| Database | SQLite owned by the Flask backend, including FTS5 for keyword search |
| AI and extraction | Azure OpenAI, optional stored embeddings, optional Jina Reader API, BeautifulSoup/newspaper/lxml fallback extraction |
| Auth | Google OAuth with Flask cookie sessions and optional email allowlist |
| Testing | Pytest, Vitest, React Testing Library, Playwright |
| Deployment | Multi-stage Docker image deployed to Azure App Service |

## Architecture

The production container builds the Vite frontend first, then copies `frontend/dist` into `backend/static`. Flask serves both the `/api/*` routes and the built single-page app from the same origin, so production uses relative `/api` requests and does not need a separate frontend host.

The backend initializes or migrates the SQLite schema at startup using `MARKLY_DB_PATH`. Local development defaults to `backend/markly.db`; Azure App Service should use persistent storage such as `/home/data/markly.db`.

Main API areas:

- `/api/auth` handles Google login, callback, logout, and current session state.
- `/api/bookmarks` handles analyze, create, list, update, delete, access tracking, retry enrichment, and save-public flows.
- `/api/folders` handles folder CRUD.
- `/api/search` handles FTS keyword search, optional semantic mode, and search history.
- `/api/stats` returns top tags.
- `/api/public` powers public profiles, public bookmarks, subscriptions, visibility changes, and account deletion.

## Running Locally

### Prerequisites

- Node.js 18+ for root scripts and frontend tooling.
- Python 3.10+ for local development. The Docker runtime uses Python 3.11.
- Azure OpenAI endpoint/key for real AI enrichment.
- Google OAuth credentials for login.

### Setup

```bash
git clone https://github.com/yourusername/markly.git
cd markly

npm run setup

cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Update `backend/.env` with Azure OpenAI, Google OAuth, and auth settings. For local development, keep `frontend/.env` pointed at the Flask API:

```bash
VITE_API_URL=http://localhost:5050/api
```

Start both dev servers:

```bash
npm start
```

The Flask API runs on `http://localhost:5050` and Vite runs on `http://localhost:5173`. Vite also proxies `/api` to Flask during development.

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

## Environment Variables

The checked-in examples are [backend/.env.example](backend/.env.example) and [frontend/.env.example](frontend/.env.example). Do not commit real `.env` files.

### Backend

```bash
MARKLY_DB_PATH=./markly.db
SQLITE_JOURNAL_MODE=DELETE

AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_NANO_DEPLOYMENT_NAME=
AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME=text-embedding-3-large
AZURE_OPENAI_API_VERSION=2024-08-01-preview
AZURE_OPENAI_EMBEDDING_API_VERSION=2024-12-01-preview

ENABLE_EMBEDDINGS=true
ENABLE_SEMANTIC_SEARCH=false

GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
OAUTH_REDIRECT_BASE_URL=http://localhost:5173
ALLOWED_EMAILS=you@example.com,friend@example.com

JINA_READER_API_KEY=

FLASK_DEBUG=true
FLASK_SECRET_KEY=generate-a-random-secret-key
```

`ALLOWED_EMAILS` is optional. When unset, any Google-authenticated user can sign in; when set, only those comma-separated emails are allowed.

### Frontend

```bash
VITE_API_URL=http://localhost:5050/api
```

In production, the frontend is served by Flask from the same origin and falls back to `/api`, so a frontend env file is usually only needed for local Vite development.

## Database

SQLite is the source of truth, and the app creates the required tables and indexes automatically when Flask starts.

The database includes users, folders, bookmarks, FTS search rows, search history, and public-profile subscribers. Bookmark JSON-like fields such as `auto_tags`, `key_quotes`, and embeddings are serialized into SQLite text columns and converted back into API JSON responses.

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
| `npm run test:e2e` | Run Playwright E2E tests from the frontend workspace |
| `npm run lint` | Run frontend ESLint and backend flake8 |
| `npm run stop` | Kill local processes on ports 5050 and 5173 |

## Testing

Backend tests live in [backend/tests](backend/tests) and use Pytest with temporary SQLite databases. Frontend unit/component tests live next to components under `frontend/src` and run with Vitest/jsdom. E2E tests live in [frontend/e2e](frontend/e2e) and run with Playwright.

CI runs backend lint/tests, frontend lint/tests/build, and Playwright E2E against a temporary SQLite database.

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

On Azure App Service, configure the app to expose port `8000`, enable persistent App Service storage, set `MARKLY_DB_PATH=/home/data/markly.db`, and add the same backend environment variables listed above. More deployment notes are in [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).

## Project Structure

```text
markly/
|-- backend/
|   |-- app.py                 # Flask app factory, API registration, SPA serving, profile OG injection
|   |-- config.py              # Environment-driven configuration
|   |-- database.py            # SQLite connection, schema initialization, row serialization
|   |-- routes/                # Auth, bookmarks, folders, search, stats, public profiles
|   |-- services/              # Content extraction, enrichment, Azure OpenAI integration
|   |-- scripts/               # One-time migration utilities
|   `-- tests/                 # Backend Pytest suite
|-- frontend/
|   |-- src/pages/             # Dashboard, Search, PublicProfile, Login
|   |-- src/components/        # Bookmark cards/rows, folders, modals, layout, topics
|   |-- src/stores/            # Zustand auth, bookmarks, folders, UI state
|   `-- e2e/                   # Playwright specs
|-- Dockerfile                 # Production container build
|-- DEPLOYMENT_GUIDE.md        # Container and Azure deployment notes
`-- package.json               # Root orchestration scripts
```

## License

[GNU Affero General Public License v3.0](LICENSE)
