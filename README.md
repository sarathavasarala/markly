# markly

**A smarter way to save links.**

Ever bookmark something, then completely forget why? markly fixes that. Paste a link, and it extracts the content, summarizes it, and auto-tags it so you actually find it again.

**Try it live:** [markly.azurewebsites.net](https://markly.azurewebsites.net)

**See an example profile:** [@sarathavasarala](https://markly.azurewebsites.net/@sarathavasarala)

---

## What it does

**AI-powered enrichment.** When you save a link, markly scrapes the page, generates a summary, and suggests tags. You can edit everything before saving.

**Semantic search.** Find that article about "startup growth strategies" even if you saved it as "interesting read." The search understands meaning, not just keywords.

**Public profiles.** Share your curated collection with a clean public page. Visitors can browse your bookmarks by topic and subscribe for updates.

**Folder organization.** Group bookmarks into folders. Filter by topic tags within each folder.

---

## Tech stack

**Frontend:** React + TypeScript + Vite  
**Backend:** Python Flask  
**Database:** SQLite owned by the Flask backend  
**AI:** Azure OpenAI for summaries, tags, and optional stored embeddings  
**Deployment:** Docker + Azure Web App

---

## Running locally

### Prerequisites

- Node.js 18+
- Python 3.10+
- Azure OpenAI access (for AI features)
- Google OAuth credentials

### Setup

```bash
# Clone the repo
git clone https://github.com/yourusername/markly.git
cd markly

# Install dependencies
npm run setup

# Configure environment
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
# Add your Azure OpenAI and Google OAuth settings

# Start development servers
npm start
```

This runs the backend on port 5050 and frontend on port 5173.

### Database

The Flask backend creates the SQLite schema automatically at `MARKLY_DB_PATH`.
For local development this defaults to `backend/markly.db`. In Azure App
Service, set it to a persistent path such as `/home/data/markly.db`.

To migrate existing Supabase data once, set `SUPABASE_URL`,
`SUPABASE_SERVICE_KEY`, and `MARKLY_DB_PATH`, then run:

```bash
cd backend
../.venv/bin/python scripts/migrate_supabase_to_sqlite.py
```

---

## Available commands

| Command | What it does |
|---------|--------------|
| `npm start` | Start both servers |
| `npm run setup` | Install all dependencies |
| `npm run test` | Run backend and frontend tests |
| `npm run lint` | Run linters |
| `npm run test:e2e` | Run Playwright E2E tests |

---

## Project structure

```
markly/
├── backend/           # Flask API
│   ├── routes/        # API endpoints
│   ├── services/      # AI enrichment, content extraction
│   └── database.py    # SQLite schema and helpers
├── frontend/          # React app
│   ├── src/pages/     # Dashboard, Search, PublicProfile, Login
│   └── src/components/# UI components
└── package.json       # Root scripts
```

---

## Environment variables

### Backend (`backend/.env`)

```
MARKLY_DB_PATH=./markly.db
AZURE_OPENAI_ENDPOINT=your_endpoint
AZURE_OPENAI_API_KEY=your_key
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
ALLOWED_EMAILS=you@example.com,friend@example.com
ENABLE_EMBEDDINGS=true
ENABLE_SEMANTIC_SEARCH=false
```

### Frontend (`frontend/.env`)

```
VITE_API_URL=http://localhost:5050/api
```

---

## License

[GNU Affero General Public License v3.0](LICENSE)
