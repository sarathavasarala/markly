# Markly Agent Instructions

Welcome to Markly. This is the shared entry point for AI coding agents working in this repository.

Before making changes, read and follow the specific guidance for the area you are working in:

- General architecture and data flows: [ARCHITECTURE.md](ARCHITECTURE.md)
- Backend Flask, Python, SQLite: [.github/instructions/backend.instructions.md](.github/instructions/backend.instructions.md)
- Frontend React, Vite, Zustand, Tailwind: [.github/instructions/frontend.instructions.md](.github/instructions/frontend.instructions.md)
- Azure operations and production DB workflows: [.github/instructions/azure.instructions.md](.github/instructions/azure.instructions.md)
- Testing harness and scenarios: [TEST_HARNESS.md](TEST_HARNESS.md)

## Commands

| Action | Command |
| --- | --- |
| Local full stack | `npm start` |
| Backend dev | `cd backend && FLASK_APP=app:create_app ../.venv/bin/flask run --port 5050` |
| Frontend dev | `cd frontend && npm run dev` |
| All tests | `npm run test` |
| Backend tests | `npm run test:backend` |
| Frontend tests | `npm run test:frontend` |
| E2E tests | `cd frontend && npx playwright test --project=chromium` |
| Linters | `npm run lint` |

## Guardrails

- Treat implementation code as the source of truth when docs and code disagree. Verify behavior in the relevant source files before relying on architecture docs.
- Update relevant docs in the same change when modifying architecture, data flow, auth, persistence, deployment, public API contracts, or test strategy.
- Before handing off changes, check whether [ARCHITECTURE.md](ARCHITECTURE.md), [TEST_HARNESS.md](TEST_HARNESS.md), [README.md](README.md), or instruction files need updates.
- Always run relevant tests before handing off code changes when feasible.
- Follow conventional commits if asked to commit: `feat:`, `fix:`, `test:`, `docs:`, `refactor:`, or `chore:`.
- Mock network APIs in tests, including Azure OpenAI and Jina Reader.
- Ask first before database schema changes, core dependency additions, CI/CD workflow edits, production database writes, deploys, or restarts.
- Never commit secrets or `.env` files.
- Local tests must use in-memory or temporary SQLite database paths.
- Do not edit files under `.venv/` or `node_modules/`.
