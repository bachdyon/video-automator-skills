-- Asset semantic index schema. Loaded by store.open_db() on every connection.

CREATE TABLE IF NOT EXISTS assets (
  id TEXT PRIMARY KEY,
  file_name TEXT NOT NULL,
  file_path TEXT NOT NULL UNIQUE,
  source_root TEXT,
  job_id TEXT,
  media_type TEXT NOT NULL CHECK (media_type IN ('image','video','audio')),
  size_bytes INTEGER,
  mtime REAL,
  width INTEGER,
  height INTEGER,
  duration_seconds REAL,
  fps REAL,
  has_audio INTEGER,
  style TEXT,
  summary TEXT,
  transcript TEXT,
  audio_role TEXT,
  tags_json TEXT,
  mood_json TEXT,
  scenes_json TEXT,
  raw_json TEXT,
  embed_source TEXT,
  embed_model TEXT,
  indexed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_assets_media ON assets(media_type);
CREATE INDEX IF NOT EXISTS idx_assets_job ON assets(job_id);
CREATE INDEX IF NOT EXISTS idx_assets_source ON assets(source_root);

CREATE VIRTUAL TABLE IF NOT EXISTS assets_vec USING vec0(
  id TEXT PRIMARY KEY,
  embedding FLOAT[1536]
);

CREATE TABLE IF NOT EXISTS process_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_path TEXT,
  content_hash TEXT,
  status TEXT,
  error TEXT,
  ran_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_log_path ON process_log(file_path);
