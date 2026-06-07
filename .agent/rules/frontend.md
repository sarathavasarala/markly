# Markly Frontend Rules & Boundaries

This document contains rules and conventions to guide any AI or human developing code in `frontend/`.

## Stack & Environment
* **Core**: React 18, TypeScript, Vite.
* **Styling**: Tailwind CSS.
* **State**: Zustand stores (`src/stores/`).
* **Icons**: Lucide React.
* **Testing**: Vitest (Unit/Components), Playwright (E2E).

## Styling & Layout Rules
* ✅ **Mobile-First Responsive Design**: Always use Tailwind's responsive prefixes (`sm:`, `md:`, `lg:`) starting from a mobile-first layout.
* ✅ **Semantic Theme Colors**: Support dark mode natively using Tailwind `dark:` variants. E.g., use `text-gray-900 dark:text-white`.
* 🚫 **Custom Hardcoding**: Never write inline `style={{ color: '#fff' }}` or custom hex codes. Keep strictly to standard Tailwind class utility sets.

## State Management (Zustand)
* ✅ **Separation of Concerns**: UI local state (toggles, modals) should live in components or `useUIStore`. Domain data (bookmarks, folders, user auth) lives in their respective Zustand stores.
* 🚫 **Mutations**: Never mutate store state directly. Always trigger defined actions to update stores.

## Testing & Mocking (Vitest)
* ✅ **Location**: Unit/Component tests live in `__tests__/` next to their components.
* ✅ **Icon Mocking**: Always mock `lucide-react` to prevent Vitest rendering errors:
  ```typescript
  vi.mock('lucide-react', () => ({
    IconName: () => <div data-testid="icon-name" />
  }))
  ```
* ✅ **Zustand Mocking**: Mock Zustand store behaviors in components to ensure pure visual/behavioral assertions:
  ```typescript
  vi.mock('../../stores/bookmarksStore', () => ({
    useBookmarksStore: () => ({
      bookmarks: [],
      loading: false,
      fetchBookmarks: vi.fn(),
    })
  }))
  ```

## E2E Testing (Playwright)
* ✅ **API Route Mocking**: In E2E tests (`frontend/e2e/`), use `page.route` to mock all backend HTTP calls (`/api/*`). E2E tests run isolated from the real Flask backend.
* ✅ **Command**: Local E2E verification must run on the Chromium project specifically:
  ```bash
  npx playwright test --project=chromium
  ```
