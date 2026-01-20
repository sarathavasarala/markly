import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
    // Mock the bookmarks API
    await page.route('**/api/public/@testuser/bookmarks', async (route) => {
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
                bookmarks: [
                    {
                        id: '1',
                        url: 'https://example.com',
                        domain: 'example.com',
                        original_title: 'Example Bookmark',
                        clean_title: 'Example Bookmark',
                        ai_summary: 'A summary of the example bookmark.',
                        auto_tags: ['test', 'mock'],
                        created_at: new Date().toISOString(),
                        enrichment_status: 'completed',
                        is_public: true
                    }
                ],
                profile: {
                    full_name: 'Test User',
                    avatar_url: null
                },
                total_count: 1,
                is_owner: false
            })
        });
    });

    // Mock the tags API
    await page.route('**/api/public/@testuser/tags*', async (route) => {
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
                tags: [
                    { tag: 'test', count: 1 },
                    { tag: 'mock', count: 1 }
                ]
            })
        });
    });

    // Mock the subscriber count API
    await page.route('**/api/public/@testuser/subscribers/count', async (route) => {
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({ count: 10 })
        });
    });
});

test('public profile loads bookmarks', async ({ page }) => {
    await page.goto('/@testuser');

    // Check title contains Test's Reading List
    await expect(page).toHaveTitle(/Test's Reading List/i);

    // Check for profile title in h1
    const profileHeader = page.locator('h1');
    await expect(profileHeader).toContainText(/Reading List/i);

    // Check for curator name
    const curatorName = page.getByText(/Curated by/i);
    await expect(curatorName).toContainText(/Test User/i);

    // Check that one bookmark is visible
    const bookmarkTitle = page.getByRole('link', { name: 'Example Bookmark' });
    await expect(bookmarkTitle).toBeVisible();

    // Verify subscriber count is NOT visible for non-owner (from previous change)
    const subscriberCount = page.getByText(/10/);
    await expect(subscriberCount).not.toBeVisible();
});

test('viral loop subscribe section is present', async ({ page }) => {
    await page.goto('/@testuser');

    const subscribeInput = page.getByPlaceholder(/enter email to join the list/i);
    await expect(subscribeInput).toBeVisible();

    const subscribeButton = page.getByRole('button', { name: /keep me updated/i });
    await expect(subscribeButton).toBeVisible();
});
