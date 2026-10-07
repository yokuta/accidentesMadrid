PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS study_sessions (
 id TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE, age_range TEXT NOT NULL,
 gender TEXT NOT NULL, urban TEXT NOT NULL, city TEXT, consent_version TEXT NOT NULL,
 study_mode TEXT NOT NULL, catalog_hash TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS study_trials (
 id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES study_sessions(id),
 round INTEGER NOT NULL CHECK(round BETWEEN 1 AND 5), left_id TEXT NOT NULL, right_id TEXT NOT NULL,
 left_snapshot TEXT NOT NULL, right_snapshot TEXT NOT NULL,
 choice TEXT CHECK(choice IN ('left','right','tie','skip')), reasons_json TEXT,
 duration_ms INTEGER CHECK(duration_ms>=0), view_json TEXT, answered_at TEXT,
 UNIQUE(session_id,round), CHECK(left_id<>right_id)
);
CREATE INDEX IF NOT EXISTS idx_trials_answered ON study_trials(answered_at);
CREATE TABLE IF NOT EXISTS study_points (
 id TEXT PRIMARY KEY, label TEXT NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL,
 pano_id TEXT NOT NULL, heading REAL NOT NULL DEFAULT 0, pitch REAL NOT NULL DEFAULT 0,
 cohort TEXT NOT NULL DEFAULT 'unverified' CHECK(cohort IN ('high','control','unverified')),
 active INTEGER NOT NULL DEFAULT 1, metrics_json TEXT, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS study_settings (key TEXT PRIMARY KEY,value TEXT NOT NULL);
