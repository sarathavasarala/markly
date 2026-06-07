# markly Test Harness

This document outlines the testing infrastructure for markly and provides instructions on how to run and verify key product scenarios.

## 🚀 Quick Start

| Command | Action |
| --- | --- |
| `npm test` | Run all Backend + Frontend tests |
| `npm run lint` | Run all style checks |
| `cd frontend && npx playwright test --project=chromium` | Run Playwright End-to-End tests (local Chromium) |

---

## 🏗️ Architecture

We use a three-tier testing strategy:

1.  **Unit Tests (Pytest/Vitest)**: Focus on local logic like content extraction and component rendering.
2.  **Integration Tests (Pytest)**: Verify API routes and database interactions with mocked authentication.
3.  **E2E Tests (Playwright)**: Simulate real user journeys in the browser. 
    *   *Note*: The frontend E2E tests are fully isolated and mock backend API routes using Playwright's `page.route` network interception. This means they run quickly and do not require a local Flask backend to be active.
    *   *Note*: Local runs should use the `--project=chromium` flag, since the default config attempts to run Chromium, Firefox, and Webkit, which might not be installed in your local developer environment.

---

## 🛡️ Critical Product Scenarios

To ensure markly remains robust for all users, we have specific tests for these four key scenarios:

### 1. Data Isolation
**Goal**: No user can edit or delete another user's bookmarks.
- **How we handle it**: Backend-owned SQLite queries explicitly filter protected operations by the authenticated `user_id`.
- **Verification**: `backend/tests/test_bookmarks.py` contains tests that attempt to access or modify data without a valid user token, verifying a `401` or `404` response.

### 2. Selective Saving from Public Profiles
**Goal**: When "Save to Collection" is clicked, only that specific bookmark is copied.
- **How we handle it**: The `/api/bookmarks/save-public` route takes a specific `bookmark_id`, fetches its metadata using an admin client, and inserts a *new* record for the current user.
- **Verification**: Integration tests verify that only the targeted bookmark is duplicated and no other data is leaked.

### 3. Version Independence
**Goal**: Editing a saved bookmark does not affect the original user's version.
- **How we handle it**: "Saving" a bookmark creates a completely new row in the database with a new unique ID. There is no shared reference between the two records after the initial copy.
- **Verification**: Tests perform an update on a "copied" bookmark and verify the original record remains unchanged.

### 4. Visibility Controls
**Goal**: Public/Private toggles work reliably.
- **How we handle it**: The `is_public` boolean in the database determines visibility. Public profile routes strictly filter by `is_public=True`.
- **Verification**: Tests verify that private bookmarks never appear in the `/api/public` responses, even if the username is correct.

### 5. Local Saved Copy Archiving and Reader View
**Goal**: Ensure articles are fetched, cleaned, parsed into text/markdown, and securely served in a readable layout.
- **How we handle it**: A background async worker triggers the `ContentExtractor` (Jina Reader API with a BeautifulSoup/newspaper3k fallback), tracks archiving status, and updates the SQLite DB. The custom reader route `/bookmarks/:id/read` is restricted to the bookmark owner.
- **Verification**: `backend/tests/test_archive.py` tests column additions, extraction fallback logic, endpoint privacy, FTS indexing, and retry routes.

---

## 🛠️ Developer Workflow

- **Pre-commit**: `lint-staged` runs automatically to keep the code clean.
- **Pre-push**: `husky` runs all backend and frontend tests.
- **CI**: GitHub Actions runs the full suite including E2E on every PR.
