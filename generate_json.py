"""Generate JSON data files from DuckDB for static hosting."""

import json
import os
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pandas as pd

# Paths
DUCKDB_PATH = Path(__file__).parent.parent / "jtvo-final" / "data" / "jtvo.duckdb"
OUTPUT_DIR = Path(__file__).parent / "public" / "data"

DASHBOARD_START = date(2025, 12, 8)
DONE_STATUSES_SQL = "('完了', 'Done', 'Closed', 'Resolved', 'Completed')"

def _team_sql(alias: str = "i") -> str:
    return f"""CASE
        WHEN {alias}.board_name = 'AI/Analytics (NLTCS)' THEN 'AI&Analytics'
        WHEN {alias}.sprint_name LIKE '%ScrumB%' OR {alias}.sprint_name LIKE '%Scrum B%' THEN 'B Scrum'
        ELSE 'A Scrum'
    END"""

TEAM_SQL = _team_sql("i")


def connect():
    return duckdb.connect(str(DUCKDB_PATH), read_only=True)


def df_to_json(df: pd.DataFrame) -> list:
    """Convert DataFrame to JSON-serializable list."""
    # Convert timestamps to strings
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].apply(lambda x: x.isoformat() if pd.notna(x) else None)
        elif df[col].dtype == 'object':
            df[col] = df[col].apply(lambda x: str(x) if pd.notna(x) and x is not None else None)

    # Handle NaN values
    df = df.where(pd.notna(df), None)
    return df.to_dict(orient='records')


def generate_summary(con) -> dict:
    """Generate summary stats."""
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
        WHERE i.created >= '{DASHBOARD_START}'
    """).fetchdf()

    row = result.iloc[0]
    return {
        "total_issues": int(row["total_issues"]) if pd.notna(row["total_issues"]) else 0,
        "total_sp": float(row["total_sp"]) if pd.notna(row["total_sp"]) else 0,
        "done_sp": float(row["done_sp"]) if pd.notna(row["done_sp"]) else 0,
        "completion_pct": float(row["completion_pct"]) if pd.notna(row["completion_pct"]) else 0,
        "member_count": int(row["member_count"]) if pd.notna(row["member_count"]) else 0,
    }


def generate_team_summary(con) -> list:
    """Generate per-team summary."""
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
        WHERE i.created >= '{DASHBOARD_START}'
        GROUP BY team
        ORDER BY team
    """).fetchdf()
    return df_to_json(result)


def generate_velocity(con) -> list:
    """Generate weekly velocity data."""
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
            ROUND(SUM(i.reported_sp), 1) AS done_sp,
            COUNT(*) AS issue_count
        FROM issues i
        JOIN completed c ON c.issue_key = i.key
        WHERE i.assignee IS NOT NULL
          AND i.reported_sp > 0
          AND c.completed_date >= '{DASHBOARD_START}'
        GROUP BY week_start, week_label, team
        ORDER BY week_start
    """).fetchdf()

    result['week_start'] = result['week_start'].astype(str)
    return df_to_json(result)


def generate_sprint_progress(con) -> list:
    """Generate active sprint progress."""
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
    return df_to_json(result)


def generate_leaderboard(con, period: str = "all") -> list:
    """Generate leaderboard data."""
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
            GROUP BY i.assignee
            ORDER BY total_sp DESC
        """).fetchdf()

    return df_to_json(result)


def generate_status_breakdown(con) -> list:
    """Generate status breakdown."""
    result = con.execute(f"""
        SELECT
            status_category,
            COUNT(*) AS count,
            ROUND(SUM(reported_sp), 1) AS sp
        FROM issues i
        WHERE i.created >= '{DASHBOARD_START}'
        GROUP BY status_category
        ORDER BY count DESC
    """).fetchdf()
    return df_to_json(result)


def generate_issues(con, limit: int = 200) -> list:
    """Generate issues list."""
    result = con.execute(f"""
        SELECT
            i.key, i.summary, i.status, i.status_category,
            i.priority, i.assignee, i.sprint_name,
            {TEAM_SQL} AS team,
            i.reported_sp,
            i.created::DATE AS created_date,
            (SELECT MAX(cl.created)::DATE FROM issue_changelog cl
             WHERE cl.issue_key = i.key AND cl.field = 'status'
               AND cl.to_string IN {DONE_STATUSES_SQL}
            ) AS completed_date
        FROM issues i
        WHERE i.created >= '{DASHBOARD_START}'
        ORDER BY i.created DESC
        LIMIT {limit}
    """).fetchdf()

    result['created_date'] = result['created_date'].astype(str)
    result['completed_date'] = result['completed_date'].apply(lambda x: str(x) if pd.notna(x) else None)
    return df_to_json(result)


def generate_individual_velocity(con) -> list:
    """Generate individual velocity data."""
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
            ROUND(SUM(i.reported_sp), 1) AS done_sp,
            COUNT(*) AS issue_count
        FROM issues i
        JOIN completed c ON c.issue_key = i.key
        WHERE i.assignee IS NOT NULL
          AND i.reported_sp > 0
          AND c.completed_date >= '{DASHBOARD_START}'
        GROUP BY week_start, week_label, i.assignee, team
        ORDER BY week_start, i.assignee, team
    """).fetchdf()

    result['week_start'] = result['week_start'].astype(str)
    return df_to_json(result)


def generate_sufficiency(con) -> dict:
    """Generate sufficiency data."""
    result = con.execute("""
        SELECT * FROM sufficiency_snapshots
        ORDER BY snapshot_date DESC LIMIT 1
    """).fetchdf()

    if result.empty:
        return None

    row = result.iloc[0]
    return {
        "snapshot_date": str(row["snapshot_date"]),
        "future_sp": float(row["future_sp"]) if pd.notna(row["future_sp"]) else 0,
        "avg_velocity": float(row["avg_velocity"]) if pd.notna(row["avg_velocity"]) else 0,
        "sufficiency": float(row["sufficiency"]) if pd.notna(row["sufficiency"]) else 0,
    }


def main():
    print("=" * 60)
    print("JTVO JSON Data Generator")
    print("=" * 60)

    if not DUCKDB_PATH.exists():
        print(f"Error: DuckDB not found at {DUCKDB_PATH}")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    con = connect()

    data = {
        "summary": generate_summary(con),
        "team_summary": generate_team_summary(con),
        "velocity": generate_velocity(con),
        "sprint_progress": generate_sprint_progress(con),
        "leaderboard_all": generate_leaderboard(con, "all"),
        "leaderboard_last_week": generate_leaderboard(con, "last_week"),
        "leaderboard_last_3_weeks": generate_leaderboard(con, "last_3_weeks"),
        "status_breakdown": generate_status_breakdown(con),
        "issues": generate_issues(con),
        "individual_velocity": generate_individual_velocity(con),
        "sufficiency": generate_sufficiency(con),
        "generated_at": date.today().isoformat(),
    }

    con.close()

    # Write single combined JSON
    output_file = OUTPUT_DIR / "dashboard.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Generated: {output_file}")
    print(f"Summary: {data['summary']['total_issues']} issues, {data['summary']['total_sp']} SP")
    print(f"Velocity: {len(data['velocity'])} weeks")
    print(f"Issues: {len(data['issues'])} records")
    print("Done!")


if __name__ == "__main__":
    main()
