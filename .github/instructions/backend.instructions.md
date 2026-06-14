---
applyTo: "backend/**"
description: "Use when working on Markly backend Flask, Python, SQLite, authentication, routes, services, database code, scripts, or backend tests."
---

# Markly Backend Rules & Boundaries

This document contains rules and conventions to guide any AI or human developing code in `backend/`.

## Stack & Environment
* **Language/Runtime**: Python 3.10+ (Docker uses 3.11).
* **Framework**: Flask 3.x.
* **Database**: SQLite.
* **Testing**: Pytest.

## Database & Model Rules
* **Initialization**: The schema is procedurally initialized at startup in `backend/database.py`. Do not modify database structure without updating the runtime setup in `database.py`.
* **Connections**:
  * Use `get_db()` within route contexts (ensures a thread-local connection handled by Flask).
  * Use `with db_session() as conn:` for scripts or background worker tasks outside Flask HTTP threads.
* **Formatting/Serialization**: Bookmark tables serialize JSON fields (e.g., `auto_tags`, `key_quotes`, `embeddings`) as string text. Use serialization helpers in `backend/database.py` to parse them into Python types.
* **Parameters**: Never interpolate variables directly into SQL. Always use placeholders (`?`) to prevent SQL injection.

## Route Design
* **Thin Wrappers**: Blueprints in `backend/routes/` should be relatively thin, delegating core business logic to `backend/services/` (e.g., parsing, Jina reader extraction, LLM synthesis).
* **Authorization**: Decorate protected routes with `@require_auth`. This populates `g.user` with the current authenticated user's details.
* **Error Logging**: Use standard logger `logger = logging.getLogger(__name__)`. Always catch external service failures (Azure OpenAI/Jina) and return structured JSON error responses with appropriate HTTP codes.
* **Telemetry logging**: Markly logs failed stream/generation stages into the `telemetry_logs` database table. The backend exposes `/api/signal/telemetry` for authenticated users to retrieve recent generation errors.
  * **Troubleshooting errors**: If a user reports an issue or error, inspect the `telemetry_logs` table locally in `markly.db` using sqlite3, or instruct the user to visit `/api/signal/telemetry` in production and paste the output.

## Pytest Mocking & Execution Rules
* **Isolated Scope**: Tests live in `backend/tests/` and run with `npm run test:backend`. They must run in isolation without writing to production `markly.db`.
* **Auth Mocking**: Mock the `require_auth` middleware or use the test client's cookie handler to simulate logged-in users.
* **Service Mocking**:
  * Always mock Azure OpenAI network calls (summarization, FTS/embedding vectors).
  * Mock Jina Reader / BeautifulSoup HTTP queries when testing the `ContentExtractor` pipeline.
