-- Add indexes to improve query performance

-- Frequent filtering by domain
CREATE INDEX IF NOT EXISTS idx_bookmarks_domain ON bookmarks (domain);

-- Sorting by date (default view)
CREATE INDEX IF NOT EXISTS idx_bookmarks_created_at ON bookmarks (created_at DESC);

-- Filtering by array tags (GIN index)
CREATE INDEX IF NOT EXISTS idx_bookmarks_tags ON bookmarks USING GIN (auto_tags);

-- Ensure URL lookup is fast (for duplication checks)
-- Note: 'url' might already have a unique constraint/index, but ensuring it here.
CREATE INDEX IF NOT EXISTS idx_bookmarks_url ON bookmarks (url);
