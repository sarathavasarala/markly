-- Markly Database Schema
-- Run this in Supabase SQL Editor

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ============================================
-- TABLES
-- ============================================

-- Folders table
CREATE TABLE IF NOT EXISTS folders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL DEFAULT auth.uid(),
    name TEXT NOT NULL,
    icon TEXT, -- Emoji or Lucide icon name
    color TEXT, -- Tailwind color class or hex
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, name)
);

-- Bookmarks table
CREATE TABLE IF NOT EXISTS bookmarks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL DEFAULT auth.uid(),
    url TEXT NOT NULL,
    domain TEXT,
    original_title TEXT,
    favicon_url TEXT,
    thumbnail_url TEXT,
    raw_notes TEXT,
    user_description TEXT,
    clean_title TEXT,
    ai_summary TEXT,
    content_extract TEXT,
    key_quotes TEXT[],
    auto_tags TEXT[],
    intent_type TEXT CHECK (intent_type IN ('reference', 'tutorial', 'inspiration', 'deep-dive', 'tool')),
    technical_level TEXT CHECK (technical_level IN ('beginner', 'intermediate', 'advanced', 'general')),
    content_type TEXT CHECK (content_type IN ('article', 'documentation', 'video', 'tool', 'paper', 'other')),
    embedding vector(3072),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_accessed_at TIMESTAMPTZ,
    access_count INTEGER DEFAULT 0,
    enrichment_status TEXT DEFAULT 'pending' CHECK (enrichment_status IN ('pending', 'processing', 'completed', 'failed')),
    enrichment_error TEXT,
    is_public BOOLEAN DEFAULT true,  -- Shared visibility control (default public)
    folder_id UUID REFERENCES folders(id) ON DELETE SET NULL,
    suggested_folder_name TEXT,
    -- Full Text Search
    fts tsvector GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(clean_title, '') || ' ' || coalesce(ai_summary, '') || ' ' || coalesce(original_title, ''))
    ) STORED,
    -- Constraints
    UNIQUE(user_id, url)
);

-- Search history table
CREATE TABLE IF NOT EXISTS search_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL DEFAULT auth.uid(),
    query TEXT NOT NULL,
    results_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Subscribers table (for email subscriptions)
CREATE TABLE IF NOT EXISTS subscribers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    curator_username TEXT NOT NULL,  -- The curator they subscribed to (e.g., 'sarath')
    email TEXT NOT NULL,
    subscribed_at TIMESTAMPTZ DEFAULT NOW(),
    unsubscribed_at TIMESTAMPTZ,  -- NULL if still subscribed
    UNIQUE(curator_username, email)  -- Prevent duplicate subscriptions
);

-- Sessions table (REMOVED: Supabase Auth handles sessions now)
DROP TABLE IF EXISTS sessions;


-- ============================================
-- INDEXES
-- ============================================

-- Bookmarks indexes
CREATE INDEX IF NOT EXISTS idx_bookmarks_user_id ON bookmarks(user_id);
CREATE INDEX IF NOT EXISTS idx_bookmarks_domain ON bookmarks(domain);
CREATE INDEX IF NOT EXISTS idx_bookmarks_created_at ON bookmarks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_bookmarks_compos_user_created ON bookmarks(user_id, created_at DESC); -- Important for dashboard
CREATE INDEX IF NOT EXISTS idx_bookmarks_enrichment_status ON bookmarks(enrichment_status);
CREATE INDEX IF NOT EXISTS idx_bookmarks_auto_tags ON bookmarks USING GIN(auto_tags);
CREATE INDEX IF NOT EXISTS idx_bookmarks_content_type ON bookmarks(content_type);
CREATE INDEX IF NOT EXISTS idx_bookmarks_intent_type ON bookmarks(intent_type);
CREATE INDEX IF NOT EXISTS idx_bookmarks_fts ON bookmarks USING GIN (fts);
CREATE INDEX IF NOT EXISTS idx_bookmarks_public ON bookmarks(user_id, is_public) WHERE is_public = true;
CREATE INDEX IF NOT EXISTS idx_bookmarks_folder_id ON bookmarks(folder_id);

-- Folders indexes
CREATE INDEX IF NOT EXISTS idx_folders_user_id ON folders(user_id);

-- Search history index
CREATE INDEX IF NOT EXISTS idx_search_history_created ON search_history(created_at DESC);

-- Subscribers indexes
CREATE INDEX IF NOT EXISTS idx_subscribers_curator ON subscribers(curator_username);
CREATE INDEX IF NOT EXISTS idx_subscribers_email ON subscribers(email);

-- ============================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================

-- Enable RLS
ALTER TABLE bookmarks ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscribers ENABLE ROW LEVEL SECURITY;
ALTER TABLE folders ENABLE ROW LEVEL SECURITY;

-- Policies for Bookmarks
CREATE POLICY "Users can only see their own bookmarks" 
ON bookmarks FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own bookmarks" 
ON bookmarks FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own bookmarks" 
ON bookmarks FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own bookmarks" 
ON bookmarks FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY "Anyone can view public bookmarks" 
ON bookmarks FOR SELECT USING (is_public = true);

-- Policies for Search History
CREATE POLICY "Users can see own search history" 
ON search_history FOR ALL USING (auth.uid() = user_id);

-- Policies for Folders
CREATE POLICY "Users can only see their own folders" 
ON folders FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own folders" 
ON folders FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own folders" 
ON folders FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own folders" 
ON folders FOR DELETE USING (auth.uid() = user_id);

-- Policies for Subscribers
CREATE POLICY "Anyone can subscribe" 
ON subscribers FOR INSERT WITH CHECK (true);

CREATE POLICY "Anyone can count subscribers" 
ON subscribers FOR SELECT USING (true);


-- ============================================
-- FUNCTIONS
-- ============================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
DROP TRIGGER IF EXISTS update_bookmarks_updated_at ON bookmarks;
CREATE TRIGGER update_bookmarks_updated_at
    BEFORE UPDATE ON bookmarks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_folders_updated_at ON folders;
CREATE TRIGGER update_folders_updated_at
    BEFORE UPDATE ON folders
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function for semantic search using cosine similarity
-- Security: Filters by auth.uid() to respect user isolation
CREATE OR REPLACE FUNCTION match_bookmarks(
    query_embedding vector(3072),
    match_threshold float DEFAULT 0.5,
    match_count int DEFAULT 20
)
RETURNS TABLE (
    id UUID,
    url TEXT,
    domain TEXT,
    clean_title TEXT,
    ai_summary TEXT,
    auto_tags TEXT[],
    favicon_url TEXT,
    thumbnail_url TEXT,
    similarity float
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        b.id,
        b.url,
        b.domain,
        b.clean_title,
        b.ai_summary,
        b.auto_tags,
        b.favicon_url,
        b.thumbnail_url,
        1 - (b.embedding <=> query_embedding) AS similarity
    FROM bookmarks b
    WHERE b.user_id = auth.uid()
      AND b.embedding IS NOT NULL
      AND b.enrichment_status = 'completed'
      AND 1 - (b.embedding <=> query_embedding) > match_threshold
    ORDER BY b.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- RPC for single-query dashboard stats
-- Security: Filters by auth.uid() to respect user isolation
CREATE OR REPLACE FUNCTION get_dashboard_stats()
RETURNS TABLE (
    total_bookmarks BIGINT,
    this_week BIGINT,
    this_month BIGINT,
    completed BIGINT,
    pending BIGINT,
    failed BIGINT
) LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    current_user_id UUID := auth.uid();
BEGIN
    RETURN QUERY SELECT
        (SELECT count(*) FROM bookmarks WHERE user_id = current_user_id) as total_bookmarks,
        (SELECT count(*) FROM bookmarks WHERE user_id = current_user_id AND created_at >= NOW() - INTERVAL '7 days') as this_week,
        (SELECT count(*) FROM bookmarks WHERE user_id = current_user_id AND created_at >= NOW() - INTERVAL '30 days') as this_month,
        (SELECT count(*) FROM bookmarks WHERE user_id = current_user_id AND enrichment_status = 'completed') as completed,
        (SELECT count(*) FROM bookmarks WHERE user_id = current_user_id AND enrichment_status IN ('pending', 'processing')) as pending,
        (SELECT count(*) FROM bookmarks WHERE user_id = current_user_id AND enrichment_status = 'failed') as failed;
END;
$$;
