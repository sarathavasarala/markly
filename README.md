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
**Database:** Supabase (PostgreSQL + pgvector)  
**AI:** Azure OpenAI for embeddings and summaries  
**Deployment:** Docker + Azure Web App

---

## Running locally

### Prerequisites

- Node.js 18+
- Python 3.10+
- Supabase project (for database)
- Azure OpenAI access (for AI features)

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
# Add your Supabase and Azure OpenAI keys

# Start development servers
npm start
```

This runs the backend on port 5050 and frontend on port 5173.

### Database

Run `backend/schema.sql` in your Supabase SQL editor to create the tables.

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
│   └── schema.sql     # Database schema
├── frontend/          # React app
│   ├── src/pages/     # Dashboard, Search, PublicProfile, Login
│   └── src/components/# UI components
└── package.json       # Root scripts
```

---

## Environment variables

### Backend (`backend/.env`)

```
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_KEY=your_service_key
AZURE_OPENAI_ENDPOINT=your_endpoint
AZURE_OPENAI_KEY=your_key
```

### Frontend (`frontend/.env`)

```
VITE_SUPABASE_URL=your_supabase_url
VITE_SUPABASE_ANON_KEY=your_anon_key
VITE_API_URL=http://localhost:5050/api
```

---

## License

[GNU Affero General Public License v3.0](LICENSE)
