-- SQLite schema for BCA Resume Analyzer
CREATE TABLE IF NOT EXISTS users(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 username TEXT UNIQUE NOT NULL,
 password TEXT NOT NULL,
 email TEXT,
 created_at TEXT
);
CREATE TABLE IF NOT EXISTS analyses(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER,
 overall REAL,
 verdict TEXT,
 keyword_score REAL,
 semantic REAL,
 skill_coverage REAL,
 cv_skills TEXT,
 jd_skills TEXT,
 missing_skills TEXT,
 cv_text TEXT,
 jd_text TEXT,
 result_json TEXT,
 created_at TEXT,
 FOREIGN KEY(user_id) REFERENCES users(id)
);
-- Default admin (password in plain for BCA demo - use hash in prod)
INSERT OR IGNORE INTO users(username,password,email,created_at) VALUES('admin','admin123','admin@college.edu', datetime('now'));
