-- Migration: Public Profiles Feature
-- To UNDO: Run the DROP/ALTER statements at the bottom of this file

-- ============================================
-- PART 1: Subscribers table (for email subscriptions)
-- ============================================

-- Create subscribers table
CREATE TABLE IF NOT EXISTS subscribers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    curator_username TEXT NOT NULL,  -- The curator they subscribed to (e.g., 'sarath')
    email TEXT NOT NULL,
    subscribed_at TIMESTAMPTZ DEFAULT NOW(),
    unsubscribed_at TIMESTAMPTZ,  -- NULL if still subscribed
    UNIQUE(curator_username, email)  -- Prevent duplicate subscriptions
);

-- Create index for fast lookups
CREATE INDEX IF NOT EXISTS idx_subscribers_curator ON subscribers(curator_username);
CREATE INDEX IF NOT EXISTS idx_subscribers_email ON subscribers(email);

-- Enable RLS
ALTER TABLE subscribers ENABLE ROW LEVEL SECURITY;

-- Allow anyone to insert (subscribe) - no auth required for public profiles
CREATE POLICY "Anyone can subscribe" ON subscribers
    FOR INSERT
    WITH CHECK (true);

-- Allow anyone to read subscriber count (for display)
CREATE POLICY "Anyone can count subscribers" ON subscribers
    FOR SELECT
    USING (true);

-- ============================================
-- PART 2: Add is_public column to bookmarks
-- ============================================

-- Add is_public column (default true = all bookmarks public by default)
ALTER TABLE bookmarks ADD COLUMN IF NOT EXISTS is_public BOOLEAN DEFAULT true;

-- Create index for public bookmark queries
CREATE INDEX IF NOT EXISTS idx_bookmarks_public ON bookmarks(user_id, is_public) WHERE is_public = true;

-- Allow anyone to read PUBLIC bookmarks (for public profiles)
CREATE POLICY "Anyone can view public bookmarks" ON bookmarks
    FOR SELECT
    USING (is_public = true);

-- ============================================
-- UNDO / ROLLBACK COMMANDS (run these to undo)
-- ============================================
-- DROP POLICY IF EXISTS "Anyone can subscribe" ON subscribers;
-- DROP POLICY IF EXISTS "Anyone can count subscribers" ON subscribers;
-- DROP INDEX IF EXISTS idx_subscribers_curator;
-- DROP INDEX IF EXISTS idx_subscribers_email;
-- DROP TABLE IF EXISTS subscribers;

-- DROP POLICY IF EXISTS "Anyone can view public bookmarks" ON bookmarks;
-- DROP INDEX IF EXISTS idx_bookmarks_public;
-- ALTER TABLE bookmarks DROP COLUMN IF EXISTS is_public;
