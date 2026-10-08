-- ⚡ gpt-load schema
CREATE TABLE runs(id INTEGER PRIMARY KEY, scenario TEXT, endpoint TEXT, model TEXT, status TEXT DEFAULT 'running', concurrency INTEGER DEFAULT 20, duration INTEGER DEFAULT 60, started_at DATETIME, finished_at DATETIME, summary_json TEXT DEFAULT '{}');
CREATE TABLE samples(id INTEGER PRIMARY KEY, run_id INTEGER REFERENCES runs(id), ts REAL, latency_ms REAL, status INTEGER DEFAULT 0, status_code INTEGER DEFAULT 0, tokens_in INTEGER DEFAULT 0, tokens_out INTEGER DEFAULT 0);
