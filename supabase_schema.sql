-- ══════════════════════════════════════════════════════════════════
-- JTVO Supabase Schema
-- DuckDBからPostgreSQLへの移行用スキーマ
-- ══════════════════════════════════════════════════════════════════

-- Issues table
CREATE TABLE IF NOT EXISTS issues (
    key             VARCHAR PRIMARY KEY,
    board_name      VARCHAR,
    sprint_id       INTEGER,
    sprint_name     VARCHAR,
    summary         VARCHAR,
    assignee        VARCHAR,
    reported_sp     DOUBLE PRECISION,
    status          VARCHAR,
    status_category VARCHAR,
    priority        VARCHAR,
    issuetype       VARCHAR DEFAULT '',
    resolution      VARCHAR,
    flagged         BOOLEAN DEFAULT FALSE,
    created         TIMESTAMP WITH TIME ZONE,
    updated         TIMESTAMP WITH TIME ZONE,
    description     TEXT
);

-- Issue comments
CREATE TABLE IF NOT EXISTS issue_comments (
    id          VARCHAR PRIMARY KEY,
    issue_key   VARCHAR REFERENCES issues(key) ON DELETE CASCADE,
    author      VARCHAR,
    body        TEXT,
    created     TIMESTAMP WITH TIME ZONE
);

-- Issue changelog
CREATE TABLE IF NOT EXISTS issue_changelog (
    id          VARCHAR PRIMARY KEY,
    issue_key   VARCHAR REFERENCES issues(key) ON DELETE CASCADE,
    author      VARCHAR,
    field       VARCHAR,
    from_string VARCHAR,
    to_string   VARCHAR,
    created     TIMESTAMP WITH TIME ZONE
);

-- AI scores
CREATE TABLE IF NOT EXISTS ai_scores (
    issue_key               VARCHAR PRIMARY KEY REFERENCES issues(key) ON DELETE CASCADE,
    complexity_reasoning    TEXT,
    clarity_score           DOUBLE PRECISION,
    clarity_notes           TEXT,
    analyzed_at             TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Weekly metrics (aggregated)
CREATE TABLE IF NOT EXISTS weekly_metrics (
    week_start  DATE,
    board_name  VARCHAR,
    assignee    VARCHAR,
    reported_sp DOUBLE PRECISION,
    issue_count INTEGER,
    PRIMARY KEY (week_start, board_name, assignee)
);

-- Sufficiency snapshots
CREATE TABLE IF NOT EXISTS sufficiency_snapshots (
    snapshot_date DATE PRIMARY KEY,
    future_sp     DOUBLE PRECISION,
    avg_velocity  DOUBLE PRECISION,
    sufficiency   DOUBLE PRECISION
);

-- Synced sprints tracking
CREATE TABLE IF NOT EXISTS synced_sprints (
    sprint_id           INTEGER PRIMARY KEY,
    board_name          VARCHAR,
    sprint_name         VARCHAR,
    state               VARCHAR,
    synced_at           TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    planned_sp_snapshot DOUBLE PRECISION,
    snapshot_created_at TIMESTAMP WITH TIME ZONE
);

-- Sprint issues mapping (many-to-many)
CREATE TABLE IF NOT EXISTS sprint_issues (
    sprint_name VARCHAR,
    issue_key   VARCHAR REFERENCES issues(key) ON DELETE CASCADE,
    PRIMARY KEY (sprint_name, issue_key)
);

-- Sprint metadata
CREATE TABLE IF NOT EXISTS sprint_metadata (
    sprint_id   INTEGER PRIMARY KEY,
    sprint_name VARCHAR NOT NULL,
    start_date  VARCHAR,
    end_date    VARCHAR,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════════════
-- Indexes for performance
-- ══════════════════════════════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_issues_board ON issues(board_name);
CREATE INDEX IF NOT EXISTS idx_issues_sprint ON issues(sprint_id);
CREATE INDEX IF NOT EXISTS idx_issues_assignee ON issues(assignee);
CREATE INDEX IF NOT EXISTS idx_issues_status ON issues(status_category);
CREATE INDEX IF NOT EXISTS idx_issues_created ON issues(created);

CREATE INDEX IF NOT EXISTS idx_changelog_issue ON issue_changelog(issue_key);
CREATE INDEX IF NOT EXISTS idx_changelog_field ON issue_changelog(field);
CREATE INDEX IF NOT EXISTS idx_changelog_created ON issue_changelog(created);

CREATE INDEX IF NOT EXISTS idx_comments_issue ON issue_comments(issue_key);

CREATE INDEX IF NOT EXISTS idx_weekly_week ON weekly_metrics(week_start);

-- ══════════════════════════════════════════════════════════════════
-- Row Level Security (optional - enable if needed)
-- ══════════════════════════════════════════════════════════════════

-- For public read access (dashboard)
-- ALTER TABLE issues ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "Allow public read" ON issues FOR SELECT USING (true);
