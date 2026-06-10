import { test, expect } from '@playwright/test';

test.describe('Refresh and Polling Logic', () => {
    let isDeleted = false;

    test.beforeEach(async ({ page }) => {
        page.on('console', msg => console.log('BROWSER LOG:', msg.text()));
        page.on('pageerror', err => console.log('BROWSER ERROR:', err.message));
        isDeleted = false;
        await page.addInitScript(() => {
            window.confirm = () => true;
        });
        await page.route('**/api/auth/me', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    is_authenticated: true,
                    user: {
                        id: 'test-user',
                        email: 'test@example.com',
                        username: 'test',
                        user_metadata: {
                            full_name: 'Test User',
                            name: 'Test User',
                            avatar_url: null,
                            picture: null,
                        },
                    },
                }),
            });
        });

        // Mock the bookmarks API
        await page.route(/\/api\/bookmarks/, async (route) => {
            const method = route.request().method();

            if (method === 'GET') {
                if (isDeleted) {
                    await route.fulfill({
                        status: 200,
                        contentType: 'application/json',
                        body: JSON.stringify({
                            bookmarks: [],
                            total: 0,
                            page: 1,
                            per_page: 40,
                            pages: 0
                        })
                    });
                } else {
                    await route.fulfill({
                        status: 200,
                        contentType: 'application/json',
                        body: JSON.stringify({
                            bookmarks: [
                                {
                                    id: 'bookmark-1',
                                    url: 'https://example.com',
                                    domain: 'example.com',
                                    original_title: 'Example Bookmark',
                                    clean_title: 'Example Bookmark',
                                    ai_summary: 'A test bookmark.',
                                    auto_tags: ['test'],
                                    created_at: new Date().toISOString(),
                                    enrichment_status: 'completed',
                                    is_public: true,
                                    folder_id: null
                                }
                            ],
                            total: 1,
                            page: 1,
                            per_page: 40,
                            pages: 1
                        })
                    });
                }
            } else if (method === 'POST') {
                // Mock create bookmark
                await route.fulfill({
                    status: 201,
                    contentType: 'application/json',
                    body: JSON.stringify({
                        id: 'new-bookmark',
                        url: 'https://new.com',
                        domain: 'new.com',
                        original_title: 'New Bookmark',
                        clean_title: 'New Bookmark',
                        ai_summary: 'A newly added bookmark.',
                        auto_tags: ['new'],
                        created_at: new Date().toISOString(),
                        enrichment_status: 'completed',
                        is_public: true,
                        folder_id: null
                    })
                });
            } else if (method === 'DELETE') {
                isDeleted = true;
                await route.fulfill({
                    status: 200,
                    contentType: 'application/json',
                    body: JSON.stringify({ message: 'Deleted' })
                });
            }
        });

        // Mock folders and tags
        await page.route('**/api/folders', async (route) => {
            await route.fulfill({ status: 200, body: JSON.stringify([]) });
        });
        await page.route('**/api/stats/tags*', async (route) => {
            await route.fulfill({ status: 200, body: JSON.stringify({ tags: [] }) });
        });

        // Mock the feeds refresh API
        await page.route('**/api/feeds/refresh', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    feeds_checked: 0,
                    feeds_skipped: 0,
                    feeds_failed: 0,
                    feeds_unchanged: 0,
                    items_added: 0
                })
            });
        });
    });

    test('adding a bookmark updates the list and count', async ({ page }) => {
        await page.goto('/bookmarks');

        // Verify initial count
        await expect(page.getByText('Your bookmarks (1)')).toBeVisible();
        await expect(page.getByText('Example Bookmark')).toBeVisible();

        // Click Add button (Layout.tsx line 145)
        await page.getByRole('button', { name: 'Add' }).click();

        // Fill AddBookmarkModal
        await page.getByPlaceholder('https://…').fill('https://new.com');

        // Mock analyze response
        await page.route('**/api/bookmarks/analyze', async (route) => {
            await route.fulfill({
                status: 200,
                body: JSON.stringify({
                    url: 'https://new.com',
                    clean_title: 'New Bookmark',
                    ai_summary: 'A newly added bookmark.',
                    auto_tags: ['new'],
                    scrape_success: true
                })
            });
        });

        await page.getByRole('button', { name: 'Analyze Link' }).click();

        // Wait for Curate state and Click Add to Collection
        await expect(page.getByRole('heading', { name: 'Review' })).toBeVisible();

        // Before clicking, update the GET mock to return TWO bookmarks
        await page.route(/\/api\/bookmarks/, async (route) => {
            if (route.request().method() === 'GET') {
                await route.fulfill({
                    status: 200,
                    body: JSON.stringify({
                        bookmarks: [
                            { id: 'new-bookmark', url: 'https://new.com', original_title: 'New Bookmark', enrichment_status: 'completed' },
                            { id: 'bookmark-1', url: 'https://example.com', original_title: 'Example Bookmark', enrichment_status: 'completed' }
                        ],
                        total: 2, page: 1, per_page: 40, pages: 1
                    })
                });
            } else {
                await route.fallback();
            }
        });

        await page.getByRole('button', { name: 'Save to library' }).click();

        // Modal should close and list should refresh
        await expect(page.getByText('Your bookmarks (2)')).toBeVisible({ timeout: 10000 });
        await expect(page.getByText('New Bookmark')).toBeVisible();
    });

    test('deleting a bookmark updates the list and count', async ({ page }) => {
        await page.goto('/bookmarks');

        await expect(page.getByText('Your bookmarks (1)')).toBeVisible();

        // Click Delete on the bookmark card
        // We need to trigger the menu first by dispatching a click on Bookmark actions
        await page.getByLabel('Bookmark actions').dispatchEvent('click');

        // Wait for the Delete button to appear in the DOM
        await expect(page.getByRole('button', { name: 'Delete' })).toBeVisible();

        await page.getByRole('button', { name: 'Delete' }).click();

        // Should remove the card from the UI
        await expect(page.getByText('Example Bookmark')).not.toBeVisible();
    });
});
