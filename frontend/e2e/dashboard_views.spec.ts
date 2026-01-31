import { test, expect } from '@playwright/test';

test.describe('Dashboard Views', () => {
    test.beforeEach(async ({ page }) => {
        // Mock the bookmarks API
        await page.route('**/api/bookmarks*', async (route) => {
            const url = route.request().url();
            // Check if this is an unfiled bookmarks request
            if (url.includes('folder_id=unfiled')) {
                await route.fulfill({
                    status: 200,
                    contentType: 'application/json',
                    body: JSON.stringify({
                        bookmarks: [
                            {
                                id: 'unfiled-1',
                                url: 'https://unfiled-example.com',
                                domain: 'unfiled-example.com',
                                original_title: 'Unfiled Bookmark',
                                clean_title: 'Unfiled Bookmark',
                                ai_summary: 'An unfiled bookmark for testing.',
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
                                auto_tags: ['test', 'mock'],
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
        });

        // Mock the folders API
        await page.route('**/api/folders', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify([
                    {
                        id: 'folder-1',
                        user_id: 'test-user',
                        name: 'Learning',
                        icon: null,
                        color: null,
                        created_at: new Date().toISOString(),
                        updated_at: new Date().toISOString(),
                        bookmark_count: 5
                    },
                    {
                        id: 'folder-2',
                        user_id: 'test-user',
                        name: 'Work',
                        icon: null,
                        color: null,
                        created_at: new Date().toISOString(),
                        updated_at: new Date().toISOString(),
                        bookmark_count: 3
                    }
                ])
            });
        });

        // Mock the tags API
        await page.route('**/api/stats/tags*', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    tags: [
                        { tag: 'test', count: 2 },
                        { tag: 'mock', count: 1 }
                    ]
                })
            });
        });

        // Mock auth token
        await page.addInitScript(() => {
            localStorage.setItem('markly_token', 'test-token');
            localStorage.setItem('markly_expires', String(Date.now() + 3600000));
        });
    });

    test('folders toggle button is visible', async ({ page }) => {
        await page.goto('/');

        const foldersToggle = page.getByTitle('Folders view');
        await expect(foldersToggle).toBeVisible();
    });

    test('clicking folders toggle shows folder cards', async ({ page }) => {
        await page.goto('/');

        // Click the folders toggle
        const foldersToggle = page.getByTitle('Folders view');
        await foldersToggle.click();

        // Wait for folders to load
        await page.waitForTimeout(500);

        // Check that folder cards are visible
        await expect(page.getByText('Learning')).toBeVisible();
        await expect(page.getByText('Work')).toBeVisible();

        // Check that bookmark counts are shown
        await expect(page.getByText('5 bookmarks')).toBeVisible();
        await expect(page.getByText('3 bookmarks')).toBeVisible();
    });

    test('clicking a folder card navigates to folder contents', async ({ page }) => {
        await page.goto('/');

        // Click the folders toggle
        const foldersToggle = page.getByTitle('Folders view');
        await foldersToggle.click();

        // Wait for folders to load
        await page.waitForTimeout(500);

        // Click on the Learning folder
        await page.getByText('Learning').click();

        // The grid view should be active now (not folders view)
        const gridToggle = page.getByTitle('Grid view');
        await expect(gridToggle).toHaveClass(/text-primary-600/);
    });

    test('view preference persists after reload', async ({ page }) => {
        await page.goto('/');

        // Click the folders toggle
        const foldersToggle = page.getByTitle('Folders view');
        await foldersToggle.click();

        // Wait a moment
        await page.waitForTimeout(300);

        // Reload the page
        await page.reload();

        // The folders toggle should still be active
        const foldersToggleAfter = page.getByTitle('Folders view');
        await expect(foldersToggleAfter).toHaveClass(/text-primary-600/);
    });

    test('header shows "Folders" title in folders view', async ({ page }) => {
        await page.goto('/');

        // Initially should show "Your bookmarks"
        await expect(page.getByRole('heading', { level: 1 })).toContainText('Your bookmarks');

        // Click the folders toggle
        const foldersToggle = page.getByTitle('Folders view');
        await foldersToggle.click();

        // Should now show "Folders"
        await expect(page.getByRole('heading', { level: 1 })).toContainText('Folders');
    });
});

test.describe('Dashboard Views - Dark Mode', () => {
    test.beforeEach(async ({ page }) => {
        // Set up mocks same as above
        await page.route('**/api/bookmarks*', async (route) => {
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
        });

        await page.route('**/api/folders', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify([
                    {
                        id: 'folder-1',
                        user_id: 'test-user',
                        name: 'Dark Mode Test',
                        bookmark_count: 2
                    }
                ])
            });
        });

        await page.route('**/api/stats/tags*', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ tags: [] })
            });
        });

        // Set dark mode and auth
        await page.addInitScript(() => {
            localStorage.setItem('markly_theme', 'dark');
            localStorage.setItem('markly_token', 'test-token');
            localStorage.setItem('markly_expires', String(Date.now() + 3600000));
        });
    });

    test('folder cards have proper dark mode styling', async ({ page }) => {
        await page.goto('/');

        // Click the folders toggle
        const foldersToggle = page.getByTitle('Folders view');
        await foldersToggle.click();

        // Wait for folders to load
        await page.waitForTimeout(500);

        // Check that the folder card is visible
        await expect(page.getByText('Dark Mode Test')).toBeVisible();

        // Check that dark class is applied to the document
        const htmlElement = page.locator('html');
        await expect(htmlElement).toHaveClass(/dark/);
    });
});
