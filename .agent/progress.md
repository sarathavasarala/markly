# Markly Session Handoff & Progress Log

This log tracks active context, recent achievements, design decisions, and future roadmap items. It acts as the shared long-term memory for you and any AI development assistants.

---

## 📌 Current Context & Handoff State
* **Active Goal**: Implementing Harness Engineering best practices (hierarchical documentation, architecture mapping, and test runner corrections).
* **Current Status**: Sub-rules and Architecture guides are in place. Preparing to align the test harness and fix GitHub Action CI deprecations.

---

## 🚀 Completed Milestones (Reverse Chronological)

### June 2026: Harness Engineering Upgrades
* **Hierarchical Rules**: Refactored `.agent/rules.md` to be an index and created folder-specific `.agent/rules/backend.md` and `.agent/rules/frontend.md` rules.
* **Architecture Mapping**: Created [ARCHITECTURE.md](file:///Users/sarathavasarala/Desktop/Projects/markly/ARCHITECTURE.md) documenting database entities, Mermaid flowcharts for authentication, Jina enrichment pipeline, and Signal SSE streaming generator.

---

## 🪵 Key Design & Architecture Decisions (ADR)
* **ADR-001: Isolated E2E Mocking**: Frontend E2E specs mock backend JSON responses directly rather than seeding/running a live Flask SQLite database. This improves CI speed and isolates client-side behavioral testing.
* **ADR-002: Procedural DB Schema**: SQLite schemas are procedurally updated and migrated at boot time in [database.py](file:///Users/sarathavasarala/Desktop/Projects/markly/backend/database.py). Raw sql schema files (`schema.sql`) are kept purely for reference.

---

## 📋 Next Up (Checklist)
* [ ] Fix local E2E run documentation in `TEST_HARNESS.md` (pointing to Chromium specifically).
* [ ] Modify `.github/workflows/ci.yml` and `deploy.yml` to set `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` to resolve GitHub Action runner warnings.
* [ ] Establish a unified `npm run verify` checker that runs lint checks, backend pytest, and frontend vitest sequentially for fast developer feedback.
