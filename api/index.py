"""FastAPI backend for JTVO Dashboard - Vercel Serverless Functions."""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import duckdb
import pandas as pd

# Initialize FastAPI
app = FastAPI(title="JTVO API", version="1.0.0")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database path - use /tmp for Vercel serverless, local for dev
from pathlib import Path
_LOCAL_DB = Path(__file__).resolve().parent.parent / "data" / "jtvo.duckdb"
DB_PATH = os.environ.get("DB_PATH", str(_LOCAL_DB) if _LOCAL_DB.exists() else "/tmp/jtvo.duckdb")

# Team SQL expression
def _team_sql(alias: str = "i") -> str:
    return f"""CASE
        WHEN {alias}.board_name = 'AI/Analytics (NLTCS)' THEN 'AI&Analytics'
        WHEN {alias}.sprint_name LIKE '%ScrumB%' OR {alias}.sprint_name LIKE '%Scrum B%' THEN 'B Scrum'
        ELSE 'A Scrum'
    END"""

TEAM_SQL = _team_sql("i")
DONE_STATUSES_SQL = "('完了', 'Done', 'Closed', 'Resolved', 'Completed')"
DASHBOARD_START = date(2025, 12, 8)


def _connect() -> duckdb.DuckDBPyConnection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return duckdb.connect(DB_PATH)


def df_to_dict(df: pd.DataFrame) -> list[dict]:
    """Convert DataFrame to list of dicts for JSON response."""
    return df.to_dict(orient="records")


# ══════════════════════════════════════════════════════════════════
# API Endpoints
# ══════════════════════════════════════════════════════════════════

@app.get("/")
def root():
    return {"status": "ok", "message": "JTVO API v1.0.0"}


@app.get("/api/health")
def health():
    return {"status": "healthy"}


@app.get("/api/summary")
def get_summary(
    team: Optional[str] = Query(None, description="Filter by team"),
    days: int = Query(0, description="Filter by days (0 = all)")
):
    """Get overall summary stats."""
    con = _connect()
    date_from = DASHBOARD_START
    if days > 0:
        date_from = max(date.today() - timedelta(days=days), DASHBOARD_START)

    date_filter = f"WHERE i.created >= '{date_from}'"
    team_filter = ""
    if team and team != "全チーム":
        team_filter = f"AND ({TEAM_SQL}) = '{team}'"

    result = con.execute(f"""
        SELECT
            COUNT(*) AS total_issues,
            ROUND(SUM(i.reported_sp), 1) AS total_sp,
            ROUND(SUM(CASE WHEN i.status_category = '完了' THEN i.reported_sp ELSE 0 END), 1) AS done_sp,
            ROUND(
                SUM(CASE WHEN i.status_category = '完了' THEN i.reported_sp ELSE 0 END)
                / NULLIF(SUM(i.reported_sp), 0) * 100, 1
            ) AS completion_pct,
            COUNT(DISTINCT i.assignee) AS member_count
        FROM issues i
        {date_filter} {team_filter}
    """).fetchdf()
    con.close()

    if result.empty:
        return {"total_issues": 0, "total_sp": 0, "done_sp": 0, "completion_pct": 0, "member_count": 0}

    row = result.iloc[0]
    return {
        "total_issues": int(row["total_issues"]) if pd.notna(row["total_issues"]) else 0,
        "total_sp": float(row["total_sp"]) if pd.notna(row["total_sp"]) else 0,
        "done_sp": float(row["done_sp"]) if pd.notna(row["done_sp"]) else 0,
        "completion_pct": float(row["completion_pct"]) if pd.notna(row["completion_pct"]) else 0,
        "member_count": int(row["member_count"]) if pd.notna(row["member_count"]) else 0,
    }


@app.get("/api/team-summary")
def get_team_summary(days: int = Query(0)):
    """Get per-team summary."""
    con = _connect()
    date_from = DASHBOARD_START
    if days > 0:
        date_from = max(date.today() - timedelta(days=days), DASHBOARD_START)

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
        WHERE i.created >= '{date_from}'
        GROUP BY team
        ORDER BY team
    """).fetchdf()
    con.close()
    return df_to_dict(result)


@app.get("/api/velocity")
def get_velocity(
    team: Optional[str] = Query(None),
    days: int = Query(0)
):
    """Get weekly velocity data."""
    con = _connect()
    date_from = DASHBOARD_START
    if days > 0:
        date_from = max(date.today() - timedelta(days=days), DASHBOARD_START)

    date_filter = f"AND c.completed_date >= '{date_from}'"
    team_filter = ""
    if team and team != "全チーム":
        team_filter = f"AND ({TEAM_SQL}) = '{team}'"

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
        WHERE i.assignee IS NOT NULL AND i.reported_sp > 0 {date_filter} {team_filter}
        GROUP BY week_start, week_label, team
        ORDER BY week_start
    """).fetchdf()
    con.close()

    # Convert dates to string for JSON
    result["week_start"] = result["week_start"].astype(str)
    return df_to_dict(result)


@app.get("/api/velocity-trend")
def get_velocity_trend():
    """Get recent 8-week velocity trend for each team."""
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
    result["week_start"] = result["week_start"].astype(str)
    return df_to_dict(result)


@app.get("/api/sprint-progress")
def get_sprint_progress(team: Optional[str] = Query(None)):
    """Get active sprint progress."""
    con = _connect()
    team_filter = ""
    if team and team != "全チーム":
        team_filter = f"AND ({TEAM_SQL}) = '{team}'"

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
        WHERE 1=1 {team_filter}
        GROUP BY a.sprint_name, team, a.state
        ORDER BY team, a.state DESC
    """).fetchdf()
    con.close()
    return df_to_dict(result)


@app.get("/api/leaderboard")
def get_leaderboard(
    period: str = Query("all", description="all, last_week, last_3_weeks"),
    team: Optional[str] = Query(None)
):
    """Get individual leaderboard."""
    con = _connect()

    board_filter = ""
    if team == "A Scrum" or team == "B Scrum":
        board_filter = "AND i.board_name = 'ICT開発ボード'"
    elif team == "AI&Analytics":
        board_filter = "AND i.board_name = 'AI/Analytics (NLTCS)'"

    if period == "last_week":
        result = con.execute(f"""
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
        """).fetchdf()
    elif period == "last_3_weeks":
        result = con.execute(f"""
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
        """).fetchdf()
    else:
        result = con.execute(f"""
            SELECT
                i.assignee,
                COUNT(*) AS issue_count,
                ROUND(SUM(i.reported_sp), 1) AS total_sp
            FROM issues i
            WHERE i.assignee IS NOT NULL
              AND i.created >= '{DASHBOARD_START}'
              {board_filter}
            GROUP BY i.assignee
            ORDER BY total_sp DESC
        """).fetchdf()

    con.close()
    return df_to_dict(result)


@app.get("/api/status-breakdown")
def get_status_breakdown(team: Optional[str] = Query(None)):
    """Get status category breakdown."""
    con = _connect()
    team_filter = ""
    if team and team != "全チーム":
        team_filter = f"AND ({TEAM_SQL}) = '{team}'"

    result = con.execute(f"""
        SELECT
            status_category,
            COUNT(*) AS count,
            ROUND(SUM(reported_sp), 1) AS sp
        FROM issues i
        WHERE i.created >= '{DASHBOARD_START}' {team_filter}
        GROUP BY status_category
        ORDER BY count DESC
    """).fetchdf()
    con.close()
    return df_to_dict(result)


@app.get("/api/assignee-load")
def get_assignee_load(team: Optional[str] = Query(None)):
    """Get per-assignee workload."""
    con = _connect()
    team_filter = ""
    if team and team != "全チーム":
        team_filter = f"AND ({TEAM_SQL}) = '{team}'"

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
          {team_filter}
        GROUP BY i.assignee, team
        ORDER BY total_sp DESC
    """).fetchdf()
    con.close()
    return df_to_dict(result)


@app.get("/api/issues")
def get_issues(
    team: Optional[str] = Query(None),
    limit: int = Query(100)
):
    """Get issues list."""
    con = _connect()
    team_filter = ""
    if team and team != "全チーム":
        team_filter = f"AND ({TEAM_SQL}) = '{team}'"

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
        WHERE i.created >= '{DASHBOARD_START}' {team_filter}
        ORDER BY i.created DESC
        LIMIT {limit}
    """).fetchdf()
    con.close()

    # Convert dates to string
    for col in ["created_date", "completed_date", "updated"]:
        if col in result.columns:
            result[col] = result[col].astype(str)

    return df_to_dict(result)


@app.get("/api/sprint-achievement")
def get_sprint_achievement(team: Optional[str] = Query(None)):
    """Get sprint achievement metrics."""
    con = _connect()
    team_filter = ""
    if team and team != "全チーム":
        team_filter = f"AND ({_team_sql('i')}) = '{team}'"

    result = con.execute(f"""
        WITH sprint_data AS (
            SELECT
                si.sprint_name,
                {_team_sql('i')} AS team,
                i.key,
                i.reported_sp,
                i.status_category,
                (SELECT COUNT(*) FROM sprint_issues si2
                 WHERE si2.issue_key = si.issue_key
                   AND si2.sprint_name != si.sprint_name) AS other_sprint_count
            FROM sprint_issues si
            JOIN issues i ON si.issue_key = i.key
            WHERE i.reported_sp > 0
              {team_filter}
        )
        SELECT
            sprint_name,
            team,
            COUNT(*) AS total_issues,
            ROUND(SUM(reported_sp), 1) AS planned_sp,
            ROUND(SUM(CASE WHEN status_category = '完了' THEN reported_sp ELSE 0 END), 1) AS done_sp,
            ROUND(SUM(CASE WHEN other_sprint_count > 0 AND status_category != '完了'
                       THEN reported_sp ELSE 0 END), 1) AS carryover_sp,
            SUM(CASE WHEN other_sprint_count > 0 AND status_category != '完了'
                THEN 1 ELSE 0 END) AS carryover_count,
            ROUND(
                SUM(CASE WHEN status_category = '完了' THEN reported_sp ELSE 0 END)
                / NULLIF(SUM(reported_sp), 0) * 100, 1
            ) AS achievement_pct
        FROM sprint_data
        GROUP BY sprint_name, team
        HAVING SUM(reported_sp) > 0
        ORDER BY sprint_name
    """).fetchdf()
    con.close()
    return df_to_dict(result)


@app.get("/api/sufficiency")
def get_sufficiency():
    """Get sufficiency alert data."""
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
        "snapshot_date": str(row["snapshot_date"]),
        "future_sp": float(row["future_sp"]) if pd.notna(row["future_sp"]) else 0,
        "avg_velocity": float(row["avg_velocity"]) if pd.notna(row["avg_velocity"]) else 0,
        "sufficiency": float(row["sufficiency"]) if pd.notna(row["sufficiency"]) else 0,
    }


@app.get("/api/individual-velocity")
def get_individual_velocity(days: int = Query(0)):
    """Get individual velocity per week."""
    con = _connect()
    date_from = DASHBOARD_START
    if days > 0:
        date_from = max(date.today() - timedelta(days=days), DASHBOARD_START)

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
        WHERE i.assignee IS NOT NULL AND i.reported_sp > 0
          AND c.completed_date >= '{date_from}'
        GROUP BY week_start, week_label, i.assignee, team
        ORDER BY week_start, i.assignee, team
    """).fetchdf()
    con.close()

    result["week_start"] = result["week_start"].astype(str)
    return df_to_dict(result)
