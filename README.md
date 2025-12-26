# Markly

AI-powered bookmark manager with semantic search. Saves links, extracts content, generates summaries/tags via LLM, and stores embeddings for meaning-based retrieval.

## Features
- Save bookmarks with optional notes
- Auto-extract page content (falls back to user description when scraping fails)
- LLM-generated titles, summaries, tags, and content classification
- Keyword search (ILIKE) + semantic search (vector similarity via pgvector)
- Masonry card layout with tag filtering
- Zen Reader mode for distraction-free reading
- Google OAuth via Supabase Auth
- Per-user data isolation with Row Level Security (RLS)

## Architecture
- **Backend**: Flask + Supabase (PostgREST + RPC for vector search) + Azure OpenAI
- **Frontend**: React + Vite + Tailwind + Zustand
- **Auth**: Supabase Auth (Google OAuth), JWT validation on backend
- **Database**: PostgreSQL with pgvector extension, RLS-enabled tables

## Prerequisites
- Python 3.10+
- Node 18+
- Supabase project
- Azure OpenAI resource with chat and embedding deployments

## Supabase Setup

1. Create a new Supabase project at [supabase.com](https://supabase.com)

2. Enable pgvector extension:
   - Go to Database > Extensions > Search "vector" > Enable

3. Run the schema:
   - Go to SQL Editor > New Query
   - Paste contents of `backend/schema.sql`
   - Execute

4. Enable Google OAuth:
   - Go to Authentication > Providers > Google
   - Enable and configure with your Google Cloud OAuth credentials
   - Add your app URL to "Redirect URLs" (e.g., `http://localhost:5173`)

5. Get your keys:
   - Project Settings > API
   - Copy `Project URL` (SUPABASE_URL)
   - Copy `anon public` key (VITE_SUPABASE_ANON_KEY)
   - Copy `service_role secret` key (SUPABASE_SERVICE_KEY)

## Azure OpenAI Setup

1. Create an Azure OpenAI resource in Azure Portal

2. Deploy two models:
   - Chat model (e.g., `gpt-4o`)
   - Embedding model (e.g., `text-embedding-3-large`)

3. Note down:
   - Endpoint URL
   - API Key
   - Deployment names for both models

## Environment Variables

### Backend (`backend/.env`)
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key

AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME=text-embedding-3-large
AZURE_OPENAI_API_VERSION=2024-08-01-preview

# Optional: Jina Reader API for better content extraction
JINA_READER_API_KEY=

FLASK_ENV=development
FLASK_DEBUG=true
```

### Frontend (`frontend/.env`)
```
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-public-key
```

## Installation

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Frontend
```bash
cd frontend
npm install
```

## Running

### Start backend (port 5050)
```bash
cd backend
source .venv/bin/activate
flask --app app:create_app run --port 5050
```

### Start frontend (port 5173)
```bash
cd frontend
npm run dev
```

Frontend dev server proxies `/api/*` requests to `http://localhost:5050` via `vite.config.ts`.

Open http://localhost:5173 and sign in with Google.

## Database Schema Notes

The schema in `backend/schema.sql` includes:
- `bookmarks` table with `user_id` column and RLS policies
- `search_history`, `import_jobs`, `import_job_items` tables with RLS
- `match_bookmarks` RPC function for semantic search
- Indexes for performance (user_id, created_at, domain, tags, FTS)
- Unique constraint on (user_id, url) to prevent duplicate bookmarks per user

## Project Structure
```
markly/
├── backend/
│   ├── app.py              # Flask app factory
│   ├── database.py         # Supabase client initialization
│   ├── config.py           # Environment config
│   ├── schema.sql          # Database schema + RLS policies
│   ├── middleware/
│   │   └── auth.py         # JWT validation middleware
│   ├── routes/
│   │   ├── bookmarks.py    # CRUD + enrichment
│   │   ├── search.py       # Keyword + semantic search
│   │   └── stats.py        # Dashboard stats
│   └── services/
│       ├── ai_service.py   # Azure OpenAI integration
│       └── scraper.py      # Content extraction
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/     # Reusable UI components
│   │   ├── pages/          # Route pages
│   │   ├── stores/         # Zustand stores
│   │   └── lib/
│   │       ├── api.ts      # API client
│   │       └── supabase.ts # Supabase client
│   └── vite.config.ts
└── README.md
```
