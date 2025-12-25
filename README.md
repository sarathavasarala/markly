# Markly

Markly is a bookmarks assistant that keeps saved links organized and searchable. It enriches each bookmark with summaries, tags, and metadata using LLMs so you can find content by meaning, not just by title or URL.

## What it does
- Save any link and capture optional notes.
- Extract page content (or use your provided description when scraping is blocked).
- Generate clean titles, summaries, tags, and content type via Azure OpenAI.
- Store bookmarks and embeddings in Supabase for keyword and semantic search.
- Browse a masonry card view with tags and quick actions.
- Search by keyword (ILIKE) or semantic similarity (vector search via RPC).

## Why it helps
Traditional browser bookmarks grow unmanageable and are hard to search. By enriching each bookmark with LLM-generated metadata and embeddings, Markly makes retrieval easier even when you do not remember exact titles or URLs.

## Architecture
- Backend: Flask + Supabase (PostgREST + RPC for vector search), Azure OpenAI for chat/embeddings.
- Frontend: React + Vite + Tailwind.
- Data: Bookmarks stored in Supabase with embeddings; search uses keyword fallback and semantic RPC.

## Setup
### Prerequisites
- Python 3.10+
- Node 18+
- Supabase project with the schema in `backend/schema.sql`
- Azure OpenAI deployments for chat and embeddings

### Environment variables
Create `backend/.env` with:
```
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...
AUTH_SECRET_PHRASE=...
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_DEPLOYMENT_NAME=...       # chat model deployment
AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME=...  # embedding deployment
AZURE_OPENAI_API_VERSION=2024-12-01-preview
AZURE_OPENAI_EMBEDDING_API_VERSION=2024-12-01-preview
JINA_READER_API_KEY=...   # optional; omit if not using
```

### Backend install
```
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app app:create_app run --port 5050
```

### Frontend install
```
cd frontend
npm install
npm run dev -- --port 5173
```

The frontend Vite dev server proxies API requests to `http://localhost:5050` via `vite.config.ts`.

### Supabase
- Apply the schema in `backend/schema.sql` to your Supabase database.
- Ensure the `match_bookmarks` RPC is present for semantic search.
- Store embeddings in the `bookmarks.embedding` column as configured in the schema.

### Running
- Start backend: `flask --app app:create_app run --port 5050`
- Start frontend: `npm run dev -- --port 5173`

### Notes
- The app requires valid Azure OpenAI deployments and Supabase keys to function.
