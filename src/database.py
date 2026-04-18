"""DuckDB data layer for JTVO."""

from __future__ import annotations

import os
from pathlib import Path

import duckdb
import pandas as pd

DB_PATH = str(Path(__file__).resolve().parent.parent / "data" / "jtvo.duckdb")

def _team_sql(alias: str = "i") -> str:
    """SQL CASE expression to derive team name. `alias` is the table alias for issues.

    Returns A Scrum, B Scrum, and AI&Analytics separately.
    """
    return f"""CASE
        WHEN {alias}.board_name = 'AI/Analytics (NLTCS)' THEN 'AI&Analytics'
        WHEN {alias}.sprint_name LIKE '%ScrumB%' OR {alias}.sprint_name LIKE '%Scrum B%' THEN 'B Scrum'
        ELSE 'A Scrum'
    END"""

# Default team SQL - returns A Scrum and B Scrum separately
TEAM_SQL = _team_sql("i")

# Statuses treated as "completed" across all boards
# Statuses that represent final completion (not intermediate like 開発完了)
DONE_STATUSES_SQL = "('完了', 'Done', 'Closed', 'Resolved', 'Completed')"


def _connect() -> duckdb.DuckDBPyConnection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return duckdb.connect(DB_PATH)


def init_db() -> None:
    """Create all tables if they don't exist."""
    con = _connect()
    con.execute("""
        CREATE TABLE IF NOT EXISTS issues (
            key             VARCHAR PRIMARY KEY,
            board_name      VARCHAR,
            sprint_id       INTEGER,
            sprint_name     VARCHAR,
            summary         VARCHAR,
            assignee        VARCHAR,
            reported_sp     DOUBLE,
            status          VARCHAR,
            status_category VARCHAR,
            priority        VARCHAR,
            issuetype       VARCHAR DEFAULT '',
            resolution      VARCHAR,
            flagged         BOOLEAN DEFAULT FALSE,
            created         TIMESTAMP,
            updated         TIMESTAMP,
            description     TEXT
        )
    """)
    # Migration: add issuetype column if missing (existing DBs)
    try:
        con.execute("SELECT issuetype FROM issues LIMIT 0")
    except duckdb.BinderException:
        con.execute("ALTER TABLE issues ADD COLUMN issuetype VARCHAR DEFAULT ''")

    con.execute("""
        CREATE TABLE IF NOT EXISTS issue_comments (
            id          VARCHAR PRIMARY KEY,
            issue_key   VARCHAR,
            author      VARCHAR,
            body        TEXT,
            created     TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS issue_changelog (
            id          VARCHAR PRIMARY KEY,
            issue_key   VARCHAR,
            author      VARCHAR,
            field       VARCHAR,
            from_string VARCHAR,
            to_string   VARCHAR,
            created     TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS ai_scores (
            issue_key               VARCHAR PRIMARY KEY,
            complexity_reasoning    TEXT,
            clarity_score           DOUBLE,
            clarity_notes           TEXT,
            analyzed_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS weekly_metrics (
            week_start  DATE,
            board_name  VARCHAR,
            assignee    VARCHAR,
            reported_sp DOUBLE,
            issue_count INTEGER,
            PRIMARY KEY (week_start, board_name, assignee)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS sufficiency_snapshots (
            snapshot_date DATE PRIMARY KEY,
            future_sp     DOUBLE,
            avg_velocity  DOUBLE,
            sufficiency   DOUBLE
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS synced_sprints (
            sprint_id   INTEGER PRIMARY KEY,
            board_name  VARCHAR,
            sprint_name VARCHAR,
            state       VARCHAR,
            synced_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS sprint_issues (
            sprint_name VARCHAR,
            issue_key   VARCHAR,
            PRIMARY KEY (sprint_name, issue_key)
        )
    """)
    # Sprint metadata table (stores Jira-provided dates)
    con.execute("""
        CREATE TABLE IF NOT EXISTS sprint_metadata (
            sprint_id INTEGER PRIMARY KEY,
            sprint_name VARCHAR NOT NULL,
            start_date VARCHAR,
            end_date VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Add snapshot columns to synced_sprints if missing
    try:
        con.execute("SELECT planned_sp_snapshot FROM synced_sprints LIMIT 0")
    except duckdb.BinderException:
        con.execute("ALTER TABLE synced_sprints ADD COLUMN planned_sp_snapshot DOUBLE DEFAULT NULL")
    try:
        con.execute("SELECT snapshot_created_at FROM synced_sprints LIMIT 0")
    except duckdb.BinderException:
        con.execute("ALTER TABLE synced_sprints ADD COLUMN snapshot_created_at TIMESTAMP DEFAULT NULL")
    con.close()


# ── Upsert helpers ──────────────────────────────────────────────

def upsert_issues(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    con = _connect()
    con.execute("DELETE FROM issues WHERE key IN (SELECT key FROM df)")
    con.execute("INSERT INTO issues SELECT * FROM df")
    count = len(df)
    con.close()
    return count


def upsert_comments(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    con = _connect()
    con.execute("DELETE FROM issue_comments WHERE id IN (SELECT id FROM df)")
    con.execute("INSERT INTO issue_comments SELECT * FROM df")
    count = len(df)
    con.close()
    return count


def upsert_changelog(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    con = _connect()
    con.execute("DELETE FROM issue_changelog WHERE id IN (SELECT id FROM df)")
    con.execute("INSERT INTO issue_changelog SELECT * FROM df")
    count = len(df)
    con.close()
    return count


def upsert_ai_scores(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    con = _connect()
    con.execute("DELETE FROM ai_scores WHERE issue_key IN (SELECT issue_key FROM df)")
    con.execute("INSERT INTO ai_scores SELECT * FROM df")
    count = len(df)
    con.close()
    return count


# ── Query helpers ───────────────────────────────────────────────

def get_all_issues() -> pd.DataFrame:
    """Return all issues."""
    con = _connect()
    result = con.execute("SELECT * FROM issues ORDER BY created DESC").fetchdf()
    con.close()
    return result


def get_all_issues_with_scores() -> pd.DataFrame:
    """All issues joined with AI scores."""
    con = _connect()
    result = con.execute("""
        SELECT i.*,
               a.complexity_reasoning, a.clarity_score, a.clarity_notes
        FROM issues i
        LEFT JOIN ai_scores a ON i.key = a.issue_key
        ORDER BY i.created DESC
    """).fetchdf()
    con.close()
    return result


def get_individual_leaderboard(board_name: str | None = None,
                               date_from=None) -> pd.DataFrame:
    """Per-assignee ranking, optionally filtered by board and date."""
    con = _connect()
    where = "WHERE i.assignee IS NOT NULL"
    params = []
    if board_name:
        where += " AND i.board_name = ?"
        params.append(board_name)
    if date_from:
        where += " AND i.created >= ?"
        params.append(str(date_from))
    result = con.execute(f"""
        SELECT
            i.assignee,
            COUNT(*)                              AS issue_count,
            ROUND(SUM(i.reported_sp), 1)          AS total_sp
        FROM issues i
        {where}
        GROUP BY i.assignee
        ORDER BY total_sp DESC
    """, params).fetchdf()
    con.close()
    return result


def get_individual_leaderboard_by_period(board_name: str | None = None) -> dict:
    """Per-assignee ranking for different time periods (last week, last 3 weeks).

    Returns dict with keys: 'last_week', 'last_3_weeks'
    Each contains DataFrame with columns: assignee, issue_count, total_sp
    """
    con = _connect()

    # Base filter
    board_filter = ""
    params_board = []
    if board_name:
        board_filter = "AND i.board_name = ?"
        params_board.append(board_name)

    # Last week ranking (based on completion date)
    last_week = con.execute(f"""
        WITH completed AS (
            SELECT cl.issue_key,
                   MIN(cl.created)::DATE AS completed_date
            FROM issue_changelog cl
            WHERE cl.field = 'status'
              AND cl.to_string IN {DONE_STATUSES_SQL}
            GROUP BY cl.issue_key
        ),
        last_week_start AS (
            SELECT MAX(DATE_TRUNC('week', completed_date))::DATE AS week_start
            FROM completed
        )
        SELECT
            i.assignee,
            COUNT(*) AS issue_count,
            ROUND(SUM(i.reported_sp), 1) AS total_sp
        FROM issues i
        JOIN completed c ON c.issue_key = i.key
        CROSS JOIN last_week_start lw
        WHERE i.assignee IS NOT NULL
          AND c.completed_date >= lw.week_start
          {board_filter}
        GROUP BY i.assignee
        ORDER BY total_sp DESC
    """, params_board).fetchdf()

    # Last 3 weeks ranking (based on completion date)
    last_3_weeks = con.execute(f"""
        WITH completed AS (
            SELECT cl.issue_key,
                   MIN(cl.created)::DATE AS completed_date
            FROM issue_changelog cl
            WHERE cl.field = 'status'
              AND cl.to_string IN {DONE_STATUSES_SQL}
            GROUP BY cl.issue_key
        ),
        three_weeks_start AS (
            SELECT MAX(DATE_TRUNC('week', completed_date))::DATE - INTERVAL '2 weeks' AS week_start
            FROM completed
        )
        SELECT
            i.assignee,
            COUNT(*) AS issue_count,
            ROUND(SUM(i.reported_sp), 1) AS total_sp
        FROM issues i
        JOIN completed c ON c.issue_key = i.key
        CROSS JOIN three_weeks_start tw
        WHERE i.assignee IS NOT NULL
          AND c.completed_date >= tw.week_start
          {board_filter}
        GROUP BY i.assignee
        ORDER BY total_sp DESC
    """, params_board).fetchdf()

    con.close()

    return {
        'last_week': last_week,
        'last_3_weeks': last_3_weeks
    }


def get_weekly_board_metrics() -> pd.DataFrame:
    """Weekly reported SP per board — the main time-series view."""
    con = _connect()
    result = con.execute("""
        SELECT week_start, board_name,
               SUM(reported_sp)  AS reported_sp,
               SUM(issue_count)  AS issue_count
        FROM weekly_metrics
        GROUP BY week_start, board_name
        ORDER BY week_start
    """).fetchdf()
    con.close()
    return result


def get_weekly_assignee_metrics(board_name: str | None = None) -> pd.DataFrame:
    """Weekly metrics per assignee, optionally filtered by board."""
    con = _connect()
    where = ""
    params = []
    if board_name:
        where = "WHERE board_name = ?"
        params.append(board_name)
    result = con.execute(f"""
        SELECT week_start, assignee,
               SUM(reported_sp)  AS reported_sp,
               SUM(issue_count)  AS issue_count
        FROM weekly_metrics
        {where}
        GROUP BY week_start, assignee
        ORDER BY week_start
    """, params).fetchdf()
    con.close()
    return result


def get_weekly_total() -> pd.DataFrame:
    """Weekly total across all boards."""
    con = _connect()
    result = con.execute("""
        SELECT week_start,
               SUM(reported_sp)  AS reported_sp,
               SUM(issue_count)  AS issue_count
        FROM weekly_metrics
        GROUP BY week_start
        ORDER BY week_start
    """).fetchdf()
    con.close()
    return result


def get_sufficiency_alert() -> dict | None:
    con = _connect()
    result = con.execute("""
        SELECT * FROM sufficiency_snapshots
        ORDER BY snapshot_date DESC LIMIT 1
    """).fetchdf()
    con.close()
    if result.empty:
        return None
    row = result.iloc[0]
    return {
        "snapshot_date": row["snapshot_date"],
        "future_sp": row["future_sp"],
        "avg_velocity": row["avg_velocity"],
        "sufficiency": row["sufficiency"],
    }


def rebuild_weekly_metrics() -> None:
    """Rebuild weekly_metrics from issues + ai_scores."""
    con = _connect()
    con.execute("DELETE FROM weekly_metrics")
    con.execute("""
        INSERT INTO weekly_metrics
        SELECT
            DATE_TRUNC('week', i.created)::DATE           AS week_start,
            i.board_name,
            i.assignee,
            SUM(i.reported_sp)                             AS reported_sp,
            COUNT(*)                                       AS issue_count
        FROM issues i
        WHERE i.assignee IS NOT NULL
        GROUP BY DATE_TRUNC('week', i.created)::DATE, i.board_name, i.assignee
    """)
    con.close()


def calculate_sufficiency(future_sp: float) -> dict:
    con = _connect()
    vel = con.execute("""
        SELECT AVG(total_sp) AS avg_vel
        FROM (
            SELECT week_start, SUM(reported_sp) AS total_sp
            FROM weekly_metrics
            GROUP BY week_start
            ORDER BY week_start DESC
            LIMIT 3
        )
    """).fetchone()
    avg_velocity = vel[0] if vel and vel[0] else 0.0
    sufficiency = (future_sp / avg_velocity * 100) if avg_velocity > 0 else 0.0

    con.execute("""
        INSERT OR REPLACE INTO sufficiency_snapshots
        VALUES (CURRENT_DATE, ?, ?, ?)
    """, [future_sp, avg_velocity, sufficiency])
    con.close()
    return {
        "future_sp": future_sp,
        "avg_velocity": avg_velocity,
        "sufficiency": round(sufficiency, 1),
    }


def get_issue_count() -> int:
    """Total issues in DB."""
    con = _connect()
    result = con.execute("SELECT COUNT(*) FROM issues").fetchone()
    con.close()
    return result[0] if result else 0


# ── Sprint sync tracking ───────────────────────────────────────

def get_closed_sprint_ids() -> set[int]:
    """Return set of sprint IDs already synced as closed."""
    con = _connect()
    result = con.execute(
        "SELECT sprint_id FROM synced_sprints WHERE state = 'closed'"
    ).fetchall()
    con.close()
    return {r[0] for r in result}


def mark_sprint_synced(sprint_id: int, board_name: str,
                       sprint_name: str, state: str) -> None:
    """Record that a sprint has been synced."""
    con = _connect()
    con.execute("""
        INSERT OR REPLACE INTO synced_sprints
        (sprint_id, board_name, sprint_name, state, synced_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, [sprint_id, board_name, sprint_name, state])
    con.close()


# ── Team-based queries for redesigned dashboard ──────────────

def get_velocity_by_team(date_from=None) -> pd.DataFrame:
    """Weekly velocity (completed SP) per derived team, grouped by completion date."""
    con = _connect()
    date_filter = ""
    params = []
    if date_from:
        date_filter = "AND c.completed_date >= ?"
        params.append(str(date_from))
    result = con.execute(f"""
        WITH completed AS (
            SELECT cl.issue_key,
                   MIN(cl.created)::DATE AS completed_date
            FROM issue_changelog cl
            WHERE cl.field = 'status'
              AND cl.to_string IN {DONE_STATUSES_SQL}
            GROUP BY cl.issue_key
        )
        SELECT
            DATE_TRUNC('week', c.completed_date)::DATE AS week_start,
            EXTRACT(ISOYEAR FROM c.completed_date)::INT || '-W'
                || LPAD(EXTRACT(WEEK FROM c.completed_date)::INT::VARCHAR, 2, '0') AS week_label,
            {TEAM_SQL} AS team,
            SUM(i.reported_sp) AS done_sp,
            COUNT(*) AS issue_count
        FROM issues i
        JOIN completed c ON c.issue_key = i.key
        WHERE i.assignee IS NOT NULL AND i.reported_sp > 0 {date_filter}
        GROUP BY week_start, week_label, team
        ORDER BY week_start
    """, params).fetchdf()
    con.close()
    return result


def get_individual_velocity(date_from=None) -> pd.DataFrame:
    """Weekly velocity per assignee per team based on actual work done.

    Team assignment logic:
    - Each assignee's work is broken down by the team (derived from board/sprint) where it was done
    - If an assignee works on multiple teams, they appear as separate rows for each team
    - Uses completion date (first transition to done status) for velocity calculation
    - Returns weekly velocity grouped by assignee, team (based on actual issue team)
    """
    con = _connect()
    date_filter = ""
    params = []
    if date_from:
        date_filter = "AND c.completed_date >= ?"
        params.append(str(date_from))

    result = con.execute(f"""
        WITH completed AS (
            SELECT cl.issue_key,
                   MIN(cl.created)::DATE AS completed_date
            FROM issue_changelog cl
            WHERE cl.field = 'status'
              AND cl.to_string IN {DONE_STATUSES_SQL}
            GROUP BY cl.issue_key
        )
        SELECT
            DATE_TRUNC('week', c.completed_date)::DATE AS week_start,
            EXTRACT(ISOYEAR FROM c.completed_date)::INT || '-W'
                || LPAD(EXTRACT(WEEK FROM c.completed_date)::INT::VARCHAR, 2, '0') AS week_label,
            i.assignee,
            {TEAM_SQL} AS team,
            SUM(i.reported_sp) AS done_sp,
            COUNT(*) AS issue_count
        FROM issues i
        JOIN completed c ON c.issue_key = i.key
        WHERE i.assignee IS NOT NULL AND i.reported_sp > 0 {date_filter}
        GROUP BY week_start, week_label, i.assignee, team
        ORDER BY week_start, i.assignee, team
    """, params).fetchdf()
    con.close()
    return result


def get_team_summary(date_from=None) -> pd.DataFrame:
    """Per-team summary: total SP, issue count, avg velocity, done ratio."""
    con = _connect()
    date_filter = ""
    params = []
    if date_from:
        date_filter = "WHERE i.created >= ?"
        params.append(str(date_from))
    result = con.execute(f"""
        SELECT
            {TEAM_SQL} AS team,
            COUNT(*) AS total_issues,
            ROUND(SUM(i.reported_sp), 1) AS total_sp,
            ROUND(SUM(CASE WHEN i.status_category = '完了' THEN i.reported_sp ELSE 0 END), 1) AS done_sp,
            ROUND(
                SUM(CASE WHEN i.status_category = '完了' THEN i.reported_sp ELSE 0 END)
                / NULLIF(SUM(i.reported_sp), 0) * 100, 1
            ) AS completion_pct,
            COUNT(DISTINCT i.assignee) AS member_count
        FROM issues i
        {date_filter}
        GROUP BY team
        ORDER BY team
    """, params).fetchdf()
    con.close()
    return result


def get_recent_velocity_trend() -> pd.DataFrame:
    """Last 8 weeks velocity per team for trend analysis (completion-date based)."""
    con = _connect()
    result = con.execute(f"""
        WITH completed AS (
            SELECT cl.issue_key,
                   MIN(cl.created)::DATE AS completed_date
            FROM issue_changelog cl
            WHERE cl.field = 'status'
              AND cl.to_string IN {DONE_STATUSES_SQL}
            GROUP BY cl.issue_key
        ),
        weekly AS (
            SELECT
                DATE_TRUNC('week', c.completed_date)::DATE AS week_start,
                {TEAM_SQL} AS team,
                SUM(i.reported_sp) AS done_sp
            FROM issues i
            JOIN completed c ON c.issue_key = i.key
            WHERE i.assignee IS NOT NULL AND i.reported_sp > 0
            GROUP BY week_start, team
        )
        SELECT * FROM weekly
        WHERE week_start >= (SELECT MAX(week_start) - INTERVAL '8 weeks' FROM weekly)
        ORDER BY week_start
    """).fetchdf()
    con.close()
    return result


def get_active_sprints_progress() -> pd.DataFrame:
    """Progress of active/recent sprints per team."""
    con = _connect()
    result = con.execute(f"""
        WITH active AS (
            SELECT sprint_id, sprint_name, board_name, state
            FROM synced_sprints
            WHERE state IN ('active', 'future')
        )
        SELECT
            a.sprint_name,
            {TEAM_SQL} AS team,
            a.state,
            COUNT(*) AS total_issues,
            SUM(CASE WHEN i.status_category = '完了' THEN 1 ELSE 0 END) AS done_issues,
            ROUND(SUM(i.reported_sp), 1) AS total_sp,
            ROUND(SUM(CASE WHEN i.status_category = '完了' THEN i.reported_sp ELSE 0 END), 1) AS done_sp
        FROM active a
        JOIN issues i ON i.sprint_id = a.sprint_id
        GROUP BY a.sprint_name, team, a.state
        ORDER BY team, a.state DESC
    """).fetchdf()
    con.close()
    return result


def get_assignee_load(team: str | None = None) -> pd.DataFrame:
    """Per-assignee workload in the most recent 4 weeks."""
    con = _connect()
    extra_where = ""
    params = []
    if team:
        extra_where = f"AND ({TEAM_SQL}) = ?"
        params.append(team)
    result = con.execute(f"""
        SELECT
            i.assignee,
            {TEAM_SQL} AS team,
            COUNT(*) AS issue_count,
            ROUND(SUM(i.reported_sp), 1) AS total_sp,
            SUM(CASE WHEN i.status_category = '完了' THEN 1 ELSE 0 END) AS done_count,
            SUM(CASE WHEN i.status_category = '進行中' THEN 1 ELSE 0 END) AS in_progress_count
        FROM issues i
        WHERE i.assignee IS NOT NULL
          AND i.created >= (SELECT MAX(created) - INTERVAL '4 weeks' FROM issues)
          {extra_where}
        GROUP BY i.assignee, team
        ORDER BY total_sp DESC
    """, params).fetchdf()
    con.close()
    return result


def get_status_breakdown(team: str | None = None,
                         date_from=None) -> pd.DataFrame:
    """Status category breakdown, optionally by team and date."""
    con = _connect()
    conditions = []
    params = []
    if team:
        conditions.append(f"({TEAM_SQL}) = ?")
        params.append(team)
    if date_from:
        conditions.append("i.created >= ?")
        params.append(str(date_from))
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    result = con.execute(f"""
        SELECT
            status_category,
            COUNT(*) AS count,
            ROUND(SUM(reported_sp), 1) AS sp
        FROM issues i
        {where}
        GROUP BY status_category
        ORDER BY count DESC
    """, params).fetchdf()
    con.close()
    return result


def get_priority_breakdown(team: str | None = None,
                           date_from=None) -> pd.DataFrame:
    """Priority breakdown for critical issues view."""
    con = _connect()
    conditions = []
    params = []
    if team:
        conditions.append(f"({TEAM_SQL}) = ?")
        params.append(team)
    if date_from:
        conditions.append("i.created >= ?")
        params.append(str(date_from))
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    result = con.execute(f"""
        SELECT
            priority,
            COUNT(*) AS count,
            ROUND(SUM(reported_sp), 1) AS sp
        FROM issues i
        {where}
        GROUP BY priority
        ORDER BY
            CASE priority
                WHEN 'Highest' THEN 1
                WHEN 'High' THEN 2
                WHEN 'Medium' THEN 3
                WHEN 'Low' THEN 4
                WHEN 'Lowest' THEN 5
                ELSE 6
            END
    """, params).fetchdf()
    con.close()
    return result


def get_issues_for_table(team: str | None = None,
                         date_from=None) -> pd.DataFrame:
    """All issues with team and AI scores for the raw data table."""
    con = _connect()
    conditions = []
    params = []
    if team and team != "全チーム":
        conditions.append(f"({TEAM_SQL}) = ?")
        params.append(team)
    if date_from:
        conditions.append("i.created >= ?")
        params.append(str(date_from))
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    result = con.execute(f"""
        SELECT
            i.key, i.summary, i.status, i.status_category,
            i.priority, i.assignee, i.sprint_name,
            {TEAM_SQL} AS team,
            i.reported_sp,
            i.created::DATE AS created_date,
            EXTRACT(ISOYEAR FROM i.created)::INT || '-W' || LPAD(EXTRACT(WEEK FROM i.created)::INT::VARCHAR, 2, '0') AS week_label,
            (SELECT MAX(cl.created)::DATE FROM issue_changelog cl
             WHERE cl.issue_key = i.key AND cl.field = 'status'
               AND cl.to_string IN {DONE_STATUSES_SQL}
            ) AS completed_date,
            i.updated
        FROM issues i
        {where}
        ORDER BY i.created DESC
    """, params).fetchdf()
    con.close()
    return result


def recalculate_priorities() -> int:
    """Re-derive priority based on custom rules.

    Rules (applied in order, first match wins):
      1. summary contains '優先' or '緊急' → 'High'
      2. issuetype is 'Bug' / 'バグ' or summary contains bug-related keywords → 'High'
      3. Otherwise keep the original Jira priority as-is.

    Returns the number of rows updated.
    """
    con = _connect()
    cur = con.execute("""
        UPDATE issues
        SET priority = 'High'
        WHERE priority != 'High' AND priority != 'Highest'
          AND (
            summary LIKE '%優先%'
            OR summary LIKE '%緊急%'
            OR LOWER(issuetype) IN ('bug', 'バグ')
            OR LOWER(summary) LIKE '%bug%'
            OR summary LIKE '%バグ%'
            OR summary LIKE '%不具合%'
            OR summary LIKE '%障害%'
          )
    """)
    changed = cur.fetchone()
    con.close()
    return changed[0] if changed else 0


# ── Sprint membership & carryover ─────────────────────────────

def _parse_sprint_names(text: str) -> list[str]:
    """Parse comma-separated sprint names from changelog from/to string.

    Handles full-width commas inside parentheses (e.g. 「コウ、ジョン」)
    by splitting only on ', ' (half-width comma + space).
    """
    if not text or not text.strip():
        return []
    return [s.strip() for s in text.split(", ") if s.strip()]


def rebuild_sprint_issues() -> int:
    """Rebuild sprint_issues from current issues + changelog history."""
    con = _connect()
    con.execute("DELETE FROM sprint_issues")

    # 1) Current sprint assignments
    con.execute("""
        INSERT OR IGNORE INTO sprint_issues (sprint_name, issue_key)
        SELECT sprint_name, key FROM issues
        WHERE sprint_name IS NOT NULL AND sprint_name != ''
    """)

    # 2) Historical assignments from changelog
    rows = con.execute("""
        SELECT issue_key, from_string, to_string
        FROM issue_changelog
        WHERE field = 'Sprint'
    """).fetchall()

    pairs: set[tuple[str, str]] = set()
    for issue_key, from_str, to_str in rows:
        for sn in _parse_sprint_names(from_str or ""):
            pairs.add((sn, issue_key))
        for sn in _parse_sprint_names(to_str or ""):
            pairs.add((sn, issue_key))

    if pairs:
        insert_df = pd.DataFrame(list(pairs), columns=["sprint_name", "issue_key"])
        con.execute("""
            INSERT OR IGNORE INTO sprint_issues
            SELECT sprint_name, issue_key FROM insert_df
        """)

    count = con.execute("SELECT COUNT(*) FROM sprint_issues").fetchone()[0]
    con.close()
    return count


def get_sprint_achievement_timeline(team: str | None = None) -> pd.DataFrame:
    """Sprint achievement rate mapped to weekly timeline for chart overlay.

    Groups sprint achievements by the week of their latest issue,
    so they align with the velocity chart x-axis.
    """
    con = _connect()
    team_filter = ""
    params = []
    if team:
        team_filter = f"AND ({_team_sql('i')}) = ?"
        params.append(team)

    result = con.execute(f"""
        WITH per_sprint AS (
            SELECT
                si.sprint_name,
                {_team_sql('i')} AS team,
                DATE_TRUNC('week', MAX(i.created))::DATE AS week_start,
                SUM(i.reported_sp) AS planned_sp,
                SUM(CASE WHEN i.status_category = '完了' THEN i.reported_sp ELSE 0 END) AS done_sp,
                SUM(CASE WHEN i.status_category != '完了'
                         AND (SELECT COUNT(*) FROM sprint_issues si2
                              WHERE si2.issue_key = si.issue_key
                                AND si2.sprint_name != si.sprint_name) > 0
                    THEN i.reported_sp ELSE 0 END) AS carryover_sp
            FROM sprint_issues si
            JOIN issues i ON si.issue_key = i.key
            WHERE i.reported_sp > 0 {team_filter}
            GROUP BY si.sprint_name, team
        )
        SELECT
            week_start,
            team,
            SUM(planned_sp) AS planned_sp,
            SUM(done_sp) AS done_sp,
            SUM(carryover_sp) AS carryover_sp,
            ROUND(SUM(done_sp) / NULLIF(SUM(planned_sp), 0) * 100, 1) AS achievement_pct
        FROM per_sprint
        WHERE planned_sp > 0
        GROUP BY week_start, team
        ORDER BY week_start
    """, params).fetchdf()
    con.close()
    return result


def get_sprint_achievement(team: str | None = None) -> pd.DataFrame:
    """Per-sprint achievement metrics with carryover detection.

    For each sprint:
      - planned_sp: Snapshot SP if exists, otherwise current total (for backward compatibility)
      - done_sp: SP of issues with status_category = '完了'
      - carryover_sp: SP of issues that also appear in a later sprint
      - achievement_pct: done_sp / planned_sp * 100
      - carryover_count: number of carried-over issues
    """
    con = _connect()
    team_filter = ""
    params = []
    if team:
        team_filter = f"AND ({_team_sql('i')}) = ?"
        params.append(team)

    result = con.execute(f"""
        WITH sprint_data AS (
            SELECT
                si.sprint_name,
                {_team_sql('i')} AS team,
                i.key,
                i.reported_sp,
                i.status_category,
                -- Check if this issue also appears in another sprint
                (SELECT COUNT(*) FROM sprint_issues si2
                 WHERE si2.issue_key = si.issue_key
                   AND si2.sprint_name != si.sprint_name) AS other_sprint_count
            FROM sprint_issues si
            JOIN issues i ON si.issue_key = i.key
            WHERE i.reported_sp > 0
              {team_filter}
        ),
        current_totals AS (
            SELECT
                sprint_name,
                team,
                COUNT(*) AS total_issues,
                ROUND(SUM(reported_sp), 1) AS current_total_sp,
                ROUND(SUM(CASE WHEN status_category = '完了' THEN reported_sp ELSE 0 END), 1) AS done_sp,
                ROUND(SUM(CASE WHEN other_sprint_count > 0 AND status_category != '完了'
                           THEN reported_sp ELSE 0 END), 1) AS carryover_sp,
                SUM(CASE WHEN other_sprint_count > 0 AND status_category != '完了'
                    THEN 1 ELSE 0 END) AS carryover_count
            FROM sprint_data
            GROUP BY sprint_name, team
            HAVING SUM(reported_sp) > 0
        )
        SELECT
            ct.sprint_name,
            ct.team,
            ct.total_issues,
            -- Use snapshot if exists, otherwise use current total
            COALESCE(ss.planned_sp_snapshot, ct.current_total_sp) AS planned_sp,
            ct.done_sp,
            ct.carryover_sp,
            ct.carryover_count,
            ROUND(
                ct.done_sp / NULLIF(COALESCE(ss.planned_sp_snapshot, ct.current_total_sp), 0) * 100, 1
            ) AS achievement_pct
        FROM current_totals ct
        LEFT JOIN synced_sprints ss ON ct.sprint_name = ss.sprint_name
        ORDER BY ct.sprint_name
    """, params).fetchdf()
    con.close()
    return result


# ── Sprint Metadata & Snapshot Management ──────────────────────────

def upsert_sprint_metadata(sprint_id: int, sprint_name: str,
                          start_date: str | None, end_date: str | None) -> None:
    """
    Insert or update sprint metadata (dates from Jira).

    Args:
        sprint_id: Jira sprint ID
        sprint_name: Sprint name
        start_date: ISO date string (YYYY-MM-DD) or None
        end_date: ISO date string (YYYY-MM-DD) or None
    """
    con = _connect()
    con.execute("""
        INSERT OR REPLACE INTO sprint_metadata
            (sprint_id, sprint_name, start_date, end_date, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (sprint_id, sprint_name, start_date, end_date))
    con.close()


def get_sprint_metadata(sprint_id: int) -> dict | None:
    """
    Retrieve sprint metadata including dates.

    Returns:
        Dict with keys: sprint_id, sprint_name, start_date, end_date, created_at, updated_at
        or None if not found
    """
    con = _connect()
    result = con.execute("""
        SELECT sprint_id, sprint_name, start_date, end_date, created_at, updated_at
        FROM sprint_metadata
        WHERE sprint_id = ?
    """, (sprint_id,)).fetchdf()
    con.close()

    if result.empty:
        return None

    row = result.iloc[0]
    return {
        "sprint_id": row["sprint_id"],
        "sprint_name": row["sprint_name"],
        "start_date": row["start_date"],
        "end_date": row["end_date"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def create_sprint_snapshot(sprint_id: int, planned_sp: float,
                          snapshot_date: str | None = None) -> None:
    """
    Create a planned SP snapshot for a sprint (one-time operation).

    Args:
        sprint_id: Sprint ID
        planned_sp: Total planned story points at sprint start
        snapshot_date: ISO timestamp string (defaults to now)

    Raises:
        ValueError: If snapshot already exists for this sprint
    """
    # Check if snapshot already exists
    existing = get_sprint_snapshot(sprint_id)
    if existing is not None:
        raise ValueError(f"Snapshot already exists for sprint {sprint_id}")

    con = _connect()
    if snapshot_date:
        con.execute("""
            UPDATE synced_sprints
            SET planned_sp_snapshot = ?,
                snapshot_created_at = ?
            WHERE sprint_id = ?
        """, (planned_sp, snapshot_date, sprint_id))
    else:
        con.execute("""
            UPDATE synced_sprints
            SET planned_sp_snapshot = ?,
                snapshot_created_at = CURRENT_TIMESTAMP
            WHERE sprint_id = ?
        """, (planned_sp, sprint_id))
    con.close()


def get_sprint_snapshot(sprint_id: int) -> float | None:
    """
    Get the planned SP snapshot for a sprint.

    Returns:
        Planned SP (float) or None if no snapshot exists
    """
    con = _connect()
    result = con.execute("""
        SELECT planned_sp_snapshot
        FROM synced_sprints
        WHERE sprint_id = ?
    """, (sprint_id,)).fetchdf()
    con.close()

    if result.empty or pd.isna(result.iloc[0]["planned_sp_snapshot"]):
        return None
    return float(result.iloc[0]["planned_sp_snapshot"])


def get_sprint_state(sprint_id: int) -> str | None:
    """
    Get current state of a sprint from database.

    Returns:
        'future', 'active', 'closed', or None if sprint not found
    """
    con = _connect()
    result = con.execute("""
        SELECT state FROM synced_sprints WHERE sprint_id = ?
    """, (sprint_id,)).fetchdf()
    con.close()

    if result.empty:
        return None
    return result.iloc[0]["state"]


def calculate_sprint_total_sp(sprint_name: str) -> float:
    """
    Calculate total SP for all issues in a sprint (current state).

    Used for creating snapshots and backfill operations.

    Args:
        sprint_name: Sprint name

    Returns:
        Total SP sum
    """
    con = _connect()
    result = con.execute("""
        SELECT COALESCE(SUM(i.reported_sp), 0) AS total_sp
        FROM issues i
        JOIN sprint_issues si ON i.key = si.issue_key
        WHERE si.sprint_name = ?
    """, (sprint_name,)).fetchdf()
    con.close()

    return float(result.iloc[0]["total_sp"])


# ── Current Sprint Analysis ────────────────────────────────────

def get_active_sprint_details() -> pd.DataFrame:
    """Get detailed info for active sprints including dates and daily progress."""
    con = _connect()
    result = con.execute(f"""
        WITH active AS (
            SELECT ss.sprint_id, ss.sprint_name, ss.board_name, ss.state,
                   sm.start_date, sm.end_date
            FROM synced_sprints ss
            LEFT JOIN sprint_metadata sm ON ss.sprint_id = sm.sprint_id
            WHERE ss.state = 'active'
        )
        SELECT
            a.sprint_id,
            a.sprint_name,
            {TEAM_SQL} AS team,
            a.state,
            a.start_date,
            a.end_date,
            COUNT(*) AS total_issues,
            SUM(CASE WHEN i.status_category = '完了' THEN 1 ELSE 0 END) AS done_issues,
            SUM(CASE WHEN i.status_category = '進行中' THEN 1 ELSE 0 END) AS in_progress_issues,
            SUM(CASE WHEN i.status_category = 'To Do' THEN 1 ELSE 0 END) AS todo_issues,
            ROUND(SUM(i.reported_sp), 1) AS total_sp,
            ROUND(SUM(CASE WHEN i.status_category = '完了' THEN i.reported_sp ELSE 0 END), 1) AS done_sp,
            ROUND(SUM(CASE WHEN i.status_category = '進行中' THEN i.reported_sp ELSE 0 END), 1) AS in_progress_sp,
            ROUND(SUM(CASE WHEN i.status_category = 'To Do' THEN i.reported_sp ELSE 0 END), 1) AS todo_sp
        FROM active a
        JOIN issues i ON i.sprint_id = a.sprint_id
        GROUP BY a.sprint_id, a.sprint_name, team, a.state, a.start_date, a.end_date
        ORDER BY team
    """).fetchdf()
    con.close()
    return result


def get_active_sprint_issues() -> pd.DataFrame:
    """Get all issues in active sprints with detailed status."""
    con = _connect()
    result = con.execute(f"""
        WITH active AS (
            SELECT sprint_id, sprint_name
            FROM synced_sprints
            WHERE state = 'active'
        )
        SELECT
            i.key,
            i.summary,
            i.status,
            i.status_category,
            i.priority,
            i.assignee,
            a.sprint_name,
            {TEAM_SQL} AS team,
            i.reported_sp,
            i.flagged,
            i.created::DATE AS created_date,
            i.updated::DATE AS updated_date,
            -- Days since last update
            (CURRENT_DATE - i.updated::DATE) AS days_since_update,
            -- Check if high priority keywords
            CASE WHEN i.summary LIKE '%優先%' OR i.summary LIKE '%緊急%'
                      OR i.summary LIKE '%hotfix%' OR i.summary LIKE '%Hotfix%'
                      OR i.summary LIKE '%HOTFIX%' OR i.summary LIKE '%ホットフィックス%'
                      OR i.priority IN ('Highest', 'High')
                 THEN TRUE ELSE FALSE END AS is_high_priority,
            -- Completion date if done
            (SELECT MIN(cl.created)::DATE FROM issue_changelog cl
             WHERE cl.issue_key = i.key AND cl.field = 'status'
               AND cl.to_string IN {DONE_STATUSES_SQL}
            ) AS completed_date
        FROM active a
        JOIN issues i ON i.sprint_id = a.sprint_id
        ORDER BY
            CASE WHEN i.priority = 'Highest' THEN 1
                 WHEN i.priority = 'High' THEN 2
                 WHEN i.summary LIKE '%優先%' OR i.summary LIKE '%緊急%' THEN 2
                 ELSE 3 END,
            i.reported_sp DESC
    """).fetchdf()
    con.close()
    return result


def get_sprint_daily_burndown() -> pd.DataFrame:
    """Get daily completion data for burndown chart of active sprints."""
    con = _connect()
    result = con.execute(f"""
        WITH active AS (
            SELECT sprint_id, sprint_name
            FROM synced_sprints
            WHERE state = 'active'
        ),
        completions AS (
            SELECT
                a.sprint_name,
                {_team_sql('i')} AS team,
                cl.created::DATE AS completion_date,
                SUM(i.reported_sp) AS completed_sp,
                COUNT(*) AS completed_count
            FROM active a
            JOIN issues i ON i.sprint_id = a.sprint_id
            JOIN issue_changelog cl ON cl.issue_key = i.key
            WHERE cl.field = 'status'
              AND cl.to_string IN {DONE_STATUSES_SQL}
            GROUP BY a.sprint_name, team, completion_date
        )
        SELECT * FROM completions
        ORDER BY sprint_name, completion_date
    """).fetchdf()
    con.close()
    return result


def get_sprint_member_workload() -> pd.DataFrame:
    """Get per-member workload for active sprints."""
    con = _connect()
    result = con.execute(f"""
        WITH active AS (
            SELECT sprint_id, sprint_name
            FROM synced_sprints
            WHERE state = 'active'
        )
        SELECT
            a.sprint_name,
            {TEAM_SQL} AS team,
            i.assignee,
            COUNT(*) AS total_issues,
            SUM(CASE WHEN i.status_category = '完了' THEN 1 ELSE 0 END) AS done_issues,
            SUM(CASE WHEN i.status_category = '進行中' THEN 1 ELSE 0 END) AS in_progress_issues,
            SUM(CASE WHEN i.status_category = 'To Do' THEN 1 ELSE 0 END) AS todo_issues,
            ROUND(SUM(i.reported_sp), 1) AS total_sp,
            ROUND(SUM(CASE WHEN i.status_category = '完了' THEN i.reported_sp ELSE 0 END), 1) AS done_sp,
            ROUND(SUM(CASE WHEN i.status_category = '進行中' THEN i.reported_sp ELSE 0 END), 1) AS in_progress_sp,
            ROUND(SUM(CASE WHEN i.status_category = 'To Do' THEN i.reported_sp ELSE 0 END), 1) AS todo_sp
        FROM active a
        JOIN issues i ON i.sprint_id = a.sprint_id
        WHERE i.assignee IS NOT NULL
        GROUP BY a.sprint_name, team, i.assignee
        ORDER BY team, total_sp DESC
    """).fetchdf()
    con.close()
    return result


def get_high_priority_issues() -> pd.DataFrame:
    """Get high priority issues in active sprints that need attention."""
    con = _connect()
    result = con.execute(f"""
        WITH active AS (
            SELECT sprint_id, sprint_name
            FROM synced_sprints
            WHERE state = 'active'
        )
        SELECT
            i.key,
            i.summary,
            i.status,
            i.status_category,
            i.priority,
            i.assignee,
            a.sprint_name,
            {TEAM_SQL} AS team,
            i.reported_sp,
            i.flagged,
            i.updated::DATE AS updated_date,
            (CURRENT_DATE - i.updated::DATE) AS days_since_update
        FROM active a
        JOIN issues i ON i.sprint_id = a.sprint_id
        WHERE i.status_category != '完了'
          AND (
            i.priority IN ('Highest', 'High')
            OR i.summary LIKE '%優先%'
            OR i.summary LIKE '%緊急%'
            OR i.summary LIKE '%hotfix%'
            OR i.summary LIKE '%Hotfix%'
            OR i.summary LIKE '%HOTFIX%'
            OR i.summary LIKE '%ホットフィックス%'
            OR i.summary LIKE '%バグ%'
            OR i.summary LIKE '%bug%'
            OR i.summary LIKE '%Bug%'
            OR i.summary LIKE '%不具合%'
            OR i.summary LIKE '%障害%'
            OR i.flagged = TRUE
          )
        ORDER BY
            CASE WHEN i.priority = 'Highest' THEN 1
                 WHEN i.priority = 'High' THEN 2
                 ELSE 3 END,
            days_since_update DESC
    """).fetchdf()
    con.close()
    return result


def get_stalled_issues(days_threshold: int = 3) -> pd.DataFrame:
    """Get issues in active sprints that haven't been updated for X days."""
    con = _connect()
    result = con.execute(f"""
        WITH active AS (
            SELECT sprint_id, sprint_name
            FROM synced_sprints
            WHERE state = 'active'
        )
        SELECT
            i.key,
            i.summary,
            i.status,
            i.status_category,
            i.priority,
            i.assignee,
            a.sprint_name,
            {TEAM_SQL} AS team,
            i.reported_sp,
            i.updated::DATE AS updated_date,
            (CURRENT_DATE - i.updated::DATE) AS days_since_update
        FROM active a
        JOIN issues i ON i.sprint_id = a.sprint_id
        WHERE i.status_category != '完了'
          AND (CURRENT_DATE - i.updated::DATE) >= ?
        ORDER BY days_since_update DESC, i.reported_sp DESC
    """, [days_threshold]).fetchdf()
    con.close()
    return result
