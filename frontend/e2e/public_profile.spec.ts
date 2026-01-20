import { test, expect } from '@playwright/test';

// NOTE: These tests are skipped in CI because they require a running backend
// with actual test data. The /@testuser route needs a real user to exist.
// To run these locally, ensure the backend is running with test fixtures.

test.skip('public profile loads bookmarks', async ({ page }) => {
    // Use a known username or mock the response
    // For now, we'll just check if the page loads and has the expected structure
    await page.goto('/@testuser');

    // Check title contains markly
    await expect(page).toHaveTitle(/markly/i);

    // Check for some key elements
    const profileHeader = page.locator('h1');
    await expect(profileHeader).toBeVisible();

    // Check for the viral loop "Save to Collection" button if bookmarks exist
    // Note: This assumes some data exists or we are mocking the API
});

test.skip('viral loop subscribe section is present', async ({ page }) => {
    await page.goto('/@testuser');

    const subscribeInput = page.getByPlaceholder(/enter email to join the list/i);
    await expect(subscribeInput).toBeVisible();

    const subscribeButton = page.getByRole('button', { name: /keep me updated/i });
    await expect(subscribeButton).toBeVisible();
});
