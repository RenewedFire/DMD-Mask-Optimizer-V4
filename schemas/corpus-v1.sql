PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS project (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS chunks (chunk_id TEXT PRIMARY KEY, filename TEXT UNIQUE NOT NULL, sha256 TEXT NOT NULL, byte_size INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS frames (
  frame_id TEXT PRIMARY KEY, lookup_sha256 TEXT NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL,
  native_shades INTEGER NOT NULL, encoding TEXT NOT NULL, normalization TEXT NOT NULL,
  chunk_id TEXT NOT NULL REFERENCES chunks(chunk_id), offset INTEGER NOT NULL, length INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS frames_lookup ON frames(lookup_sha256);
CREATE TABLE IF NOT EXISTS captures (capture_id TEXT PRIMARY KEY, provenance_json TEXT NOT NULL, complete INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS occurrences (
  capture_id TEXT NOT NULL REFERENCES captures(capture_id), occurrence_index INTEGER NOT NULL,
  frame_id TEXT NOT NULL REFERENCES frames(frame_id), session INTEGER NOT NULL, original_tick INTEGER NOT NULL,
  duration_ticks INTEGER, duration_status TEXT NOT NULL, offset INTEGER NOT NULL, end_offset INTEGER NOT NULL, line INTEGER NOT NULL,
  PRIMARY KEY(capture_id, occurrence_index)
);
CREATE TABLE IF NOT EXISTS revisions (digest TEXT PRIMARY KEY, parent_digest TEXT, complete INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS revision_captures (
  revision_digest TEXT NOT NULL REFERENCES revisions(digest), capture_id TEXT NOT NULL REFERENCES captures(capture_id),
  ordinal INTEGER NOT NULL, PRIMARY KEY(revision_digest, capture_id), UNIQUE(revision_digest, ordinal)
);
