-- Migration: import job items and current item tracking

-- 1) import_job_items table
CREATE TABLE IF NOT EXISTS import_job_items (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  job_id UUID REFERENCES import_jobs(id) ON DELETE CASCADE,
  url TEXT NOT NULL,
  title TEXT,
  tags TEXT[],
  bookmark_id UUID,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','processing','completed','failed','skipped','canceled')),
  error TEXT,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_import_job_items_job ON import_job_items(job_id);
CREATE INDEX IF NOT EXISTS idx_import_job_items_status ON import_job_items(status);

-- 2) current_item_id on import_jobs
ALTER TABLE import_jobs ADD COLUMN IF NOT EXISTS current_item_id UUID REFERENCES import_job_items(id);

-- 3) updated_at trigger already exists; reuse update_updated_at_column
DROP TRIGGER IF EXISTS update_import_job_items_updated_at ON import_job_items;
CREATE TRIGGER update_import_job_items_updated_at
  BEFORE UPDATE ON import_job_items
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();
