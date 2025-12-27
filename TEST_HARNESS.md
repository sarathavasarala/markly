# Markly Test Harness

This document outlines the testing infrastructure for Markly and provides instructions on how to run and verify key product scenarios.

## 🚀 Quick Start

| Command | Action |
| --- | --- |
| `npm test` | Run all Backend + Frontend tests |
| `npm run lint` | Run all style checks |
| `npm run test:e2e` | Run Playwright End-to-End tests |

---

## 🏗️ Architecture

We use a three-tier testing strategy:

1.  **Unit Tests (Pytest/Vitest)**: Focus on local logic like content extraction and component rendering.
2.  **Integration Tests (Pytest)**: Verify API routes and database interactions with mocked authentication.
3.  **E2E Tests (Playwright)**: Simulate real user journeys in the browser.

---

## 🛡️ Critical Product Scenarios

To ensure Markly remains robust for all users, we have specific tests for these four key scenarios:

### 1. Data Isolation (RLS)
**Goal**: No user can edit or delete another user's bookmarks.
- **How we handle it**: We use Supabase Row Level Security (RLS) combined with dynamic user-scoped clients in the backend.
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

---

## 🛠️ Developer Workflow

- **Pre-commit**: `lint-staged` runs automatically to keep the code clean.
- **Pre-push**: `husky` runs all backend and frontend tests.
- **CI**: GitHub Actions runs the full suite including E2E on every PR.
