# Project Spec & Agent Instructions: Markly

Welcome! This is the core entry point for developers and AI agents working on `markly`.

## 📌 Rules Directory Hierarchy
Before making any changes, you **must** read and follow the specific guidelines for the area you are working in:
*   📁 **General Architecture & Data Flows**: [ARCHITECTURE.md](file:///Users/sarathavasarala/Desktop/Projects/markly/ARCHITECTURE.md)
*   📁 **Backend (Flask, Python, SQLite)**: [.agent/rules/backend.md](file:///Users/sarathavasarala/Desktop/Projects/markly/.agent/rules/backend.md)
*   📁 **Frontend (React, Vite, Zustand, Tailwind)**: [.agent/rules/frontend.md](file:///Users/sarathavasarala/Desktop/Projects/markly/.agent/rules/frontend.md)
*   📁 **Azure Ops & Connection (deploy, prod DB pull/push)**: [.agent/rules/azure.md](file:///Users/sarathavasarala/Desktop/Projects/markly/.agent/rules/azure.md)
*   📁 **Testing Harness & Scenarios**: [TEST_HARNESS.md](file:///Users/sarathavasarala/Desktop/Projects/markly/TEST_HARNESS.md)
*   📁 **Session Handoff & Changelog**: [.agent/progress.md](file:///Users/sarathavasarala/Desktop/Projects/markly/.agent/progress.md)

---

## 🛠️ Commands Reference

| Action | Command |
| --- | --- |
| **Local Full Stack** | `npm start` (backend: 5050, frontend: 5173) |
| **Backend Dev** | `cd backend && FLASK_APP=app:create_app ../.venv/bin/flask run --port 5050` |
| **Frontend Dev** | `cd frontend && npm run dev` |
| **All Tests** | `npm run test` (Runs backend pytest + frontend vitest) |
| **Backend Tests** | `npm run test:backend` |
| **Frontend Tests** | `npm run test:frontend` |
| **E2E Tests** | `cd frontend && npx playwright test --project=chromium` |
| **Linters** | `npm run lint` (ESLint on frontend, Flake8 on backend) |

---

## 🛡️ Core Boundaries & Guardrails
*   ✅ **Always**: Run tests before committing code.
*   ✅ **Always**: Follow conventional commits (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`).
*   ✅ **Always**: Mock network APIs (Azure OpenAI, Jina Reader) in tests.
*   ⚠️ **Ask first**: Database schema changes, adding core dependencies, modifying CI/CD workflows.
*   🚫 **Never**: Commit secrets or `.env` files. Local tests must use memory or temporary SQLite DB paths.
*   🚫 **Never**: Hardcode visual styles, custom colors, or edit files under `.venv/` or `node_modules/`.
