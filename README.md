# markly

AI-powered bookmark manager with semantic search. Saves links, extracts content, generates summaries and tags via LLM, and stores embeddings for meaning-based retrieval.

## Features
- Save bookmarks with optional notes.
- Auto-extract page content with Jina Reader fallback.
- LLM-generated titles, summaries, tags, and classification.
- Keyword and semantic search via pgvector.
- Masonry card layout with tag filtering.
- Public profiles (`/@username`) with shareable bookmark collections.
- Email subscriptions for public profile updates.
- Google OAuth via Supabase.
- Per-user data isolation with Row Level Security (RLS).

## Architecture
- **Backend**: Flask, Supabase (PostgREST + RPC), Azure OpenAI.
- **Frontend**: React, Vite, Tailwind, Zustand.
- **Auth**: Supabase Auth (Google OAuth), JWT validation.
- **Database**: PostgreSQL with pgvector and RLS.
- **Testing**: Vitest, Playwright (E2E), Pytest.
- **CI/CD**: GitHub Actions, Docker, Azure Container Registry.

## Prerequisites
- Python 3.10+
- Node 20+
- Supabase project.
- Azure OpenAI resource (gpt-4o and text-embedding-3-large).

## Setup

### 1. Supabase
- Enable pgvector extension.
- Run `backend/schema.sql` and migrations in `backend/migrations/`.
- Configure Google OAuth in Authentication > Providers.
- Add app URL to Redirect URLs.

### 2. Environment Variables

markly uses `.env` files for configuration. By default, it looks for a `.env` file in both `frontend/` and `backend/` directories.

1.  **Frontend**: Copy `frontend/.env.example` to `frontend/.env` and fill in your Supabase keys.
2.  **Backend**: Copy `backend/.env.example` to `backend/.env` and fill in your Supabase and Azure OpenAI keys.

> [!NOTE]
> For testing, the app looks for `.env.test`. You can copy the same templates to `.env.test` and point them to your test project.

#### Backend Key Variables (`backend/.env`)
- `SUPABASE_URL`: Your project URL.
- `SUPABASE_SERVICE_KEY`: Service role key (required for backend bypass of RLS).
- `AZURE_OPENAI_API_KEY`: Required for AI features.

#### Frontend Key Variables (`frontend/.env`)
- `VITE_SUPABASE_URL`: Your project URL.
- `VITE_SUPABASE_ANON_KEY`: Public anon key.

## Installation

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Frontend
```bash
cd frontend
npm install
```

## Running

### Backend (Port 5050)
```bash
cd backend
flask run --port 5050
```

### Frontend (Port 5173)
```bash
cd frontend
npm run dev
```

## Testing
- **Backend**: `cd backend && pytest`
- **Frontend Unit**: `cd frontend && npm run test`
- **E2E**: `cd frontend && npm run test:e2e`

## Project Structure
```
markly/
├── backend/
│   ├── migrations/         # SQL schema updates
│   ├── routes/             # API endpoints (bookmarks, public, search, stats)
│   ├── services/           # AI, scrubbing, enrichment logic
│   ├── tests/              # Pytest suite
│   ├── app.py              # Flask entry point
│   └── database.py         # Supabase client
├── frontend/
│   ├── src/
│   │   ├── components/     # UI elements
│   │   ├── pages/          # Page views (Dashboard, PublicProfile, Reader)
│   │   ├── stores/         # Zustand state
│   │   └── lib/            # API and Supabase clients
│   ├── e2e/                # Playwright tests
│   └── src/test/           # Vitest setup
├── Dockerfile              # Production container
└── README.md
```
