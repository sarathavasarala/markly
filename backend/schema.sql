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
    url TEXT NOT NULL UNIQUE,
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
    import_job_id UUID REFERENCES import_jobs(id),
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
    -- Full Text Search column (Generated)
    fts tsvector GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(clean_title, '') || ' ' || coalesce(ai_summary, '') || ' ' || coalesce(original_title, ''))
    ) STORED
);

-- Search history table
CREATE TABLE IF NOT EXISTS search_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query TEXT NOT NULL,
    results_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Sessions table for auth
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_token TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

-- ============================================

-- INDEXES
-- ============================================

-- Bookmarks indexes
CREATE INDEX IF NOT EXISTS idx_bookmarks_domain ON bookmarks(domain);
CREATE INDEX IF NOT EXISTS idx_bookmarks_created_at ON bookmarks(created_at DESC);
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

-- Vector similarity search index (IVFFlat for approximate nearest neighbors)
-- Note: Create this after you have some data for better index quality
-- CREATE INDEX IF NOT EXISTS idx_bookmarks_embedding ON bookmarks 
-- USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Sessions indexes
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);

-- Search history index
CREATE INDEX IF NOT EXISTS idx_search_history_created ON search_history(created_at DESC);

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
    WHERE b.embedding IS NOT NULL
      AND b.enrichment_status = 'completed'
      AND 1 - (b.embedding <=> query_embedding) > match_threshold
    ORDER BY b.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- RPC for single-query dashboard stats
CREATE OR REPLACE FUNCTION get_dashboard_stats()
RETURNS TABLE (
    total_bookmarks BIGINT,
    this_week BIGINT,
    this_month BIGINT,
    completed BIGINT,
    pending BIGINT,
    failed BIGINT
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY SELECT
        (SELECT count(*) FROM bookmarks) as total_bookmarks,
        (SELECT count(*) FROM bookmarks WHERE created_at >= NOW() - INTERVAL '7 days') as this_week,
        (SELECT count(*) FROM bookmarks WHERE created_at >= NOW() - INTERVAL '30 days') as this_month,
        (SELECT count(*) FROM bookmarks WHERE enrichment_status = 'completed') as completed,
        (SELECT count(*) FROM bookmarks WHERE enrichment_status IN ('pending', 'processing')) as pending,
        (SELECT count(*) FROM bookmarks WHERE enrichment_status = 'failed') as failed;
END;
$$;

