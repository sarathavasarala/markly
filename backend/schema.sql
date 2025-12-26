-- Markly Database Schema
-- Run this in Supabase SQL Editor

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ============================================
-- TABLES
-- ============================================

-- Import jobs table (tracks bulk imports and enrichment progress)
CREATE TABLE IF NOT EXISTS import_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL DEFAULT auth.uid(),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'canceled')),
    total INTEGER NOT NULL DEFAULT 0,
    imported_count INTEGER NOT NULL DEFAULT 0,
    skipped_count INTEGER NOT NULL DEFAULT 0,
    enqueue_enrich_count INTEGER NOT NULL DEFAULT 0,
    enrich_completed INTEGER NOT NULL DEFAULT 0,
    enrich_failed INTEGER NOT NULL DEFAULT 0,
    use_nano_model BOOLEAN NOT NULL DEFAULT FALSE,
    current_item_id UUID,
    last_error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Import job items table for per-item tracking
CREATE TABLE IF NOT EXISTS import_job_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID REFERENCES import_jobs(id) ON DELETE CASCADE,
    user_id UUID NOT NULL DEFAULT auth.uid(),
    url TEXT NOT NULL,
    title TEXT,
    tags TEXT[],
    bookmark_id UUID,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'skipped', 'canceled')),
    error TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
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
    import_job_id UUID,  -- Circular ref handled below
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

-- Sessions table (REMOVED: Supabase Auth handles sessions now)
-- We drop it if it exists to clean up
DROP TABLE IF EXISTS sessions;

-- Fix circular reference (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_bookmarks_import_job'
    ) THEN
        ALTER TABLE bookmarks 
        ADD CONSTRAINT fk_bookmarks_import_job 
        FOREIGN KEY (import_job_id) REFERENCES import_jobs(id);
    END IF;
END
$$;


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
CREATE INDEX IF NOT EXISTS idx_bookmarks_import_job ON bookmarks(import_job_id);
CREATE INDEX IF NOT EXISTS idx_bookmarks_fts ON bookmarks USING GIN (fts);

-- Import job indexes
CREATE INDEX IF NOT EXISTS idx_import_job_items_job ON import_job_items(job_id);
CREATE INDEX IF NOT EXISTS idx_import_job_items_status ON import_job_items(status);
CREATE INDEX IF NOT EXISTS idx_import_jobs_created ON import_jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_import_job_items_created ON import_job_items(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_import_jobs_user ON import_jobs(user_id);

-- Vector similarity search index (IVFFlat for approximate nearest neighbors)
-- Note: Create this after you have some data for better index quality
-- CREATE INDEX IF NOT EXISTS idx_bookmarks_embedding ON bookmarks 
-- USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Search history index
CREATE INDEX IF NOT EXISTS idx_search_history_created ON search_history(created_at DESC);

-- ============================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================

-- Enable RLS
ALTER TABLE bookmarks ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE import_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE import_job_items ENABLE ROW LEVEL SECURITY;

-- Policies for Bookmarks
CREATE POLICY "Users can only see their own bookmarks" 
ON bookmarks FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own bookmarks" 
ON bookmarks FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own bookmarks" 
ON bookmarks FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own bookmarks" 
ON bookmarks FOR DELETE USING (auth.uid() = user_id);

-- Policies for Search History
CREATE POLICY "Users can see own search history" 
ON search_history FOR ALL USING (auth.uid() = user_id);

-- Policies for Import Jobs
CREATE POLICY "Users can manage own import jobs" 
ON import_jobs FOR ALL USING (auth.uid() = user_id);

-- Policies for Import Job Items
CREATE POLICY "Users can manage own import job items" 
ON import_job_items FOR ALL USING (auth.uid() = user_id);


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

DROP TRIGGER IF EXISTS update_import_jobs_updated_at ON import_jobs;
CREATE TRIGGER update_import_jobs_updated_at
    BEFORE UPDATE ON import_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_import_job_items_updated_at ON import_job_items;
CREATE TRIGGER update_import_job_items_updated_at
    BEFORE UPDATE ON import_job_items
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

