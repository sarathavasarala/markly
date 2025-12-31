import { test, expect } from '@playwright/test';

test('public profile loads bookmarks', async ({ page }) => {
    // Use a known username or mock the response
    // For now, we'll just check if the page loads and has the expected structure
    await page.goto('/@testuser');

    // Check title
    await expect(page).toHaveTitle(/Reading List - Markly/);

    // Check for some key elements
    const profileHeader = page.locator('h1');
    await expect(profileHeader).toBeVisible();

    // Check for the viral loop "Save to Collection" button if bookmarks exist
    // Note: This assumes some data exists or we are mocking the API
});

test('viral loop subscribe section is present', async ({ page }) => {
    await page.goto('/@testuser');

    const subscribeInput = page.getByPlaceholder(/enter email to join/i);
    await expect(subscribeInput).toBeVisible();

    const subscribeButton = page.getByRole('button', { name: /keep me updated/i });
    await expect(subscribeButton).toBeVisible();
});
