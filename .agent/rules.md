# Project Spec: Markly

## Objective
- AI-powered bookmark manager with semantic search, content extraction, and LLM-generated summaries/tags. Features include masonry layout and public profiles.

## Tech Stack
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Zustand, Lucide React, Vitest
- **Backend**: Flask (Python), PostgreSQL (Supabase + pgvector), Azure OpenAI, Jina Reader
- **Infra**: Docker (linux/amd64), Azure Web App for Containers, Azure Container Registry

## Commands
- **Local Development**:
  - Frontend: `cd frontend && npm run dev` (Port 5173)
  - Backend: `cd backend && flask run --port 5050`
- **Testing**:
  - Frontend Unit: `cd frontend && npm test`
  - Frontend E2E: `cd frontend && npm run test:e2e`
  - Backend: `cd backend && pytest`
- **Quality**:
  - Lint Frontend: `cd frontend && npm run lint`
- **Deployment**:
  - **Quick Push** (No rollback): `docker build --platform linux/amd64 -t marklyregistry.azurecr.io/markly-app:latest . && docker push marklyregistry.azurecr.io/markly-app:latest && az webapp restart --name markly --resource-group <resource-group>`
  - Build & Tag (with rollback): `docker build --platform linux/amd64 -t marklyregistry.azurecr.io/markly-app:latest -t marklyregistry.azurecr.io/markly-app:$(git rev-parse --short HEAD) .`
  - Push All Tags: `docker push --all-tags marklyregistry.azurecr.io/markly-app`
  - Restart Azure: `az webapp restart --name markly --resource-group <resource-group>`

## Project Structure
- `frontend/src/components/` – UI components and `__tests__/`
- `frontend/src/stores/` – Zustand state management
- `backend/routes/` – API endpoints (bookmarks, search, stats)
- `backend/services/` – AI enrichment, content extraction, scrubbing
- `backend/migrations/` – PostgreSQL schema and RLS updates

## Boundaries
- ✅ **Always**: Run tests before commits, follow conventional commits (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`).
- ✅ **Always**: Mock Zustand stores (`useBookmarksStore`, `useUIStore`, `useAuthStore`) and `lucide-react` icons in tests.
- ✅ **Always**: Use mobile-first responsive design and semantic colors (e.g., `text-gray-900 dark:text-white`).
- ⚠️ **Ask first**: Database schema changes, adding core dependencies, modifying CI/CD configs.
- 🚫 **Never**: Commit secrets or `.env` files (use `.env.test` for testing, Azure Settings for production).
- 🚫 **Never**: Hardcode colors or edit `node_modules/` / `.venv/`.

---

## Detailed Reference

### Testing Requirements (Frontend)
All new components must have render tests in `frontend/src/components/__tests__/`.
```typescript
vi.mock('../../stores/yourStore', () => ({ useYourStore: () => ({ /* mocks */ }) }))
vi.mock('lucide-react', () => ({ IconName: () => <div data-testid="icon-name" /> }))
```

### Deployment & Rollback
- **Latest**: `markly-app:latest` points to current production.
- **Git SHA**: Use `markly-app:<short-sha>` for stable production deployments and emergency rollbacks.
- **Rollback**: `az webapp config container set ... --docker-custom-image-name marklyregistry.azurecr.io/markly-app:<previous-sha>`

### Environment Variables
- **Backend**: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `AZURE_OPENAI_API_KEY`, `JINA_API_KEY`, `FLASK_ENV`.
- **Frontend**: `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`.
