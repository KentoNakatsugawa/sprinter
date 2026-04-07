"""FastAPI backend for JTVO Dashboard - Supabase + Vercel."""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Optional

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client

# Initialize FastAPI
app = FastAPI(title="JTVO API", version="2.0.0")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase client
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY")

def get_supabase() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# Constants
DASHBOARD_START = date(2025, 12, 8)
DONE_STATUSES = ['完了', 'Done', 'Closed', 'Resolved', 'Completed']


def get_team(board_name: str, sprint_name: str) -> str:
    """Derive team from board/sprint names."""
    if board_name == 'AI/Analytics (NLTCS)':
        return 'AI&Analytics'
    if sprint_name and ('ScrumB' in sprint_name or 'Scrum B' in sprint_name):
        return 'B Scrum'
    return 'A Scrum'


# ══════════════════════════════════════════════════════════════════
# API Endpoints
# ══════════════════════════════════════════════════════════════════

@app.get("/")
def root():
    return {"status": "ok", "message": "JTVO API v2.0.0 (Supabase)"}


@app.get("/api/health")
def health():
    try:
        supabase = get_supabase()
        result = supabase.table("issues").select("key").limit(1).execute()
        return {"status": "healthy", "db": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@app.get("/api/summary")
def get_summary(
    team: Optional[str] = Query(None),
    days: int = Query(0)
):
    """Get overall summary stats."""
    supabase = get_supabase()

    date_from = str(DASHBOARD_START)
    if days > 0:
        date_from = str(max(date.today() - timedelta(days=days), DASHBOARD_START))

    # Fetch issues
    query = supabase.table("issues").select("*").gte("created", date_from)
    result = query.execute()
    issues = result.data

    # Filter by team if specified
    if team and team != "全チーム":
        issues = [i for i in issues if get_team(i.get("board_name", ""), i.get("sprint_name", "")) == team]

    if not issues:
        return {"total_issues": 0, "total_sp": 0, "done_sp": 0, "completion_pct": 0, "member_count": 0}

    total_sp = sum(i.get("reported_sp", 0) or 0 for i in issues)
    done_sp = sum(i.get("reported_sp", 0) or 0 for i in issues if i.get("status_category") == "完了")
    completion_pct = round(done_sp / total_sp * 100, 1) if total_sp > 0 else 0
    assignees = set(i.get("assignee") for i in issues if i.get("assignee"))

    return {
        "total_issues": len(issues),
        "total_sp": round(total_sp, 1),
        "done_sp": round(done_sp, 1),
        "completion_pct": completion_pct,
        "member_count": len(assignees),
    }


@app.get("/api/team-summary")
def get_team_summary(days: int = Query(0)):
    """Get per-team summary."""
    supabase = get_supabase()

    date_from = str(DASHBOARD_START)
    if days > 0:
        date_from = str(max(date.today() - timedelta(days=days), DASHBOARD_START))

    result = supabase.table("issues").select("*").gte("created", date_from).execute()
    issues = result.data

    # Group by team
    teams = {}
    for i in issues:
        team = get_team(i.get("board_name", ""), i.get("sprint_name", ""))
        if team not in teams:
            teams[team] = {"issues": [], "assignees": set()}
        teams[team]["issues"].append(i)
        if i.get("assignee"):
            teams[team]["assignees"].add(i["assignee"])

    summary = []
    for team, data in teams.items():
        issues_list = data["issues"]
        total_sp = sum(i.get("reported_sp", 0) or 0 for i in issues_list)
        done_sp = sum(i.get("reported_sp", 0) or 0 for i in issues_list if i.get("status_category") == "完了")
        summary.append({
            "team": team,
            "total_issues": len(issues_list),
            "total_sp": round(total_sp, 1),
            "done_sp": round(done_sp, 1),
            "completion_pct": round(done_sp / total_sp * 100, 1) if total_sp > 0 else 0,
            "member_count": len(data["assignees"]),
        })

    return sorted(summary, key=lambda x: x["team"])


@app.get("/api/velocity")
def get_velocity(
    team: Optional[str] = Query(None),
    days: int = Query(0)
):
    """Get weekly velocity data based on completion date."""
    supabase = get_supabase()

    date_from = str(DASHBOARD_START)
    if days > 0:
        date_from = str(max(date.today() - timedelta(days=days), DASHBOARD_START))

    # Get changelog for completion dates
    changelog = supabase.table("issue_changelog").select("*").eq("field", "status").execute()
    changelog_data = changelog.data

    # Find first completion date for each issue
    completion_dates = {}
    for cl in changelog_data:
        if cl.get("to_string") in DONE_STATUSES:
            issue_key = cl.get("issue_key")
            created = cl.get("created")
            if created:
                if issue_key not in completion_dates or created < completion_dates[issue_key]:
                    completion_dates[issue_key] = created

    # Get issues
    issues = supabase.table("issues").select("*").execute().data

    # Build velocity data
    from datetime import datetime
    weekly = {}

    for issue in issues:
        key = issue.get("key")
        if key not in completion_dates:
            continue

        completed_str = completion_dates[key]
        try:
            completed = datetime.fromisoformat(completed_str.replace("Z", "+00:00"))
        except:
            continue

        if completed.date() < datetime.fromisoformat(date_from).date():
            continue

        issue_team = get_team(issue.get("board_name", ""), issue.get("sprint_name", ""))
        if team and team != "全チーム" and issue_team != team:
            continue

        # Get week start (Monday)
        week_start = completed.date() - timedelta(days=completed.weekday())
        week_label = f"{week_start.isocalendar()[0]}-W{week_start.isocalendar()[1]:02d}"

        key_tuple = (str(week_start), week_label, issue_team)
        if key_tuple not in weekly:
            weekly[key_tuple] = {"done_sp": 0, "issue_count": 0}

        weekly[key_tuple]["done_sp"] += issue.get("reported_sp", 0) or 0
        weekly[key_tuple]["issue_count"] += 1

    result = [
        {
            "week_start": k[0],
            "week_label": k[1],
            "team": k[2],
            "done_sp": round(v["done_sp"], 1),
            "issue_count": v["issue_count"]
        }
        for k, v in weekly.items()
    ]

    return sorted(result, key=lambda x: x["week_start"])


@app.get("/api/velocity-trend")
def get_velocity_trend():
    """Get recent 8-week velocity trend."""
    velocity = get_velocity(days=60)

    # Get last 8 weeks
    from datetime import datetime
    cutoff = date.today() - timedelta(weeks=8)

    return [v for v in velocity if datetime.fromisoformat(v["week_start"]).date() >= cutoff]


@app.get("/api/sprint-progress")
def get_sprint_progress(team: Optional[str] = Query(None)):
    """Get active sprint progress."""
    supabase = get_supabase()

    # Get active sprints
    sprints = supabase.table("synced_sprints").select("*").in_("state", ["active", "future"]).execute()

    # Get issues for each sprint
    issues = supabase.table("issues").select("*").execute().data
    issues_by_sprint = {}
    for i in issues:
        sid = i.get("sprint_id")
        if sid:
            if sid not in issues_by_sprint:
                issues_by_sprint[sid] = []
            issues_by_sprint[sid].append(i)

    result = []
    for sprint in sprints.data:
        sprint_issues = issues_by_sprint.get(sprint["sprint_id"], [])
        if not sprint_issues:
            continue

        # Determine team from first issue
        first_issue = sprint_issues[0]
        sprint_team = get_team(first_issue.get("board_name", ""), first_issue.get("sprint_name", ""))

        if team and team != "全チーム" and sprint_team != team:
            continue

        total_sp = sum(i.get("reported_sp", 0) or 0 for i in sprint_issues)
        done_sp = sum(i.get("reported_sp", 0) or 0 for i in sprint_issues if i.get("status_category") == "完了")

        result.append({
            "sprint_name": sprint["sprint_name"],
            "team": sprint_team,
            "state": sprint["state"],
            "total_issues": len(sprint_issues),
            "done_issues": sum(1 for i in sprint_issues if i.get("status_category") == "完了"),
            "total_sp": round(total_sp, 1),
            "done_sp": round(done_sp, 1),
        })

    return result


@app.get("/api/leaderboard")
def get_leaderboard(
    period: str = Query("all"),
    team: Optional[str] = Query(None)
):
    """Get individual leaderboard."""
    supabase = get_supabase()

    # Get completion dates
    changelog = supabase.table("issue_changelog").select("*").eq("field", "status").execute()
    completion_dates = {}
    for cl in changelog.data:
        if cl.get("to_string") in DONE_STATUSES:
            issue_key = cl.get("issue_key")
            created = cl.get("created")
            if created:
                if issue_key not in completion_dates or created < completion_dates[issue_key]:
                    completion_dates[issue_key] = created

    # Get issues
    issues = supabase.table("issues").select("*").execute().data

    # Filter by period
    from datetime import datetime
    now = date.today()

    if period == "last_week":
        # Find the most recent week with data
        weeks = set()
        for d in completion_dates.values():
            try:
                dt = datetime.fromisoformat(d.replace("Z", "+00:00")).date()
                week_start = dt - timedelta(days=dt.weekday())
                weeks.add(week_start)
            except:
                pass
        if weeks:
            latest_week = max(weeks)
            date_from = latest_week
        else:
            date_from = now - timedelta(days=7)
    elif period == "last_3_weeks":
        date_from = now - timedelta(weeks=3)
    else:
        date_from = DASHBOARD_START

    # Filter and aggregate
    assignee_stats = {}
    for issue in issues:
        key = issue.get("key")
        assignee = issue.get("assignee")
        if not assignee:
            continue

        # Check completion date
        if key in completion_dates:
            try:
                completed = datetime.fromisoformat(completion_dates[key].replace("Z", "+00:00")).date()
                if completed < date_from:
                    continue
            except:
                if period != "all":
                    continue
        elif period != "all":
            continue

        # Filter by team
        if team and team != "全チーム":
            issue_team = get_team(issue.get("board_name", ""), issue.get("sprint_name", ""))
            board_filter = None
            if team in ["A Scrum", "B Scrum"]:
                board_filter = "ICT開発ボード"
            elif team == "AI&Analytics":
                board_filter = "AI/Analytics (NLTCS)"
            if board_filter and issue.get("board_name") != board_filter:
                continue

        if assignee not in assignee_stats:
            assignee_stats[assignee] = {"issue_count": 0, "total_sp": 0}
        assignee_stats[assignee]["issue_count"] += 1
        assignee_stats[assignee]["total_sp"] += issue.get("reported_sp", 0) or 0

    result = [
        {"assignee": a, "issue_count": s["issue_count"], "total_sp": round(s["total_sp"], 1)}
        for a, s in assignee_stats.items()
    ]

    return sorted(result, key=lambda x: x["total_sp"], reverse=True)


@app.get("/api/status-breakdown")
def get_status_breakdown(team: Optional[str] = Query(None)):
    """Get status category breakdown."""
    supabase = get_supabase()

    issues = supabase.table("issues").select("*").gte("created", str(DASHBOARD_START)).execute().data

    if team and team != "全チーム":
        issues = [i for i in issues if get_team(i.get("board_name", ""), i.get("sprint_name", "")) == team]

    status_stats = {}
    for i in issues:
        cat = i.get("status_category", "Unknown")
        if cat not in status_stats:
            status_stats[cat] = {"count": 0, "sp": 0}
        status_stats[cat]["count"] += 1
        status_stats[cat]["sp"] += i.get("reported_sp", 0) or 0

    return [
        {"status_category": s, "count": d["count"], "sp": round(d["sp"], 1)}
        for s, d in status_stats.items()
    ]


@app.get("/api/assignee-load")
def get_assignee_load(team: Optional[str] = Query(None)):
    """Get per-assignee workload (last 4 weeks)."""
    supabase = get_supabase()

    four_weeks_ago = str(date.today() - timedelta(weeks=4))
    issues = supabase.table("issues").select("*").gte("created", four_weeks_ago).execute().data

    if team and team != "全チーム":
        issues = [i for i in issues if get_team(i.get("board_name", ""), i.get("sprint_name", "")) == team]

    assignee_stats = {}
    for i in issues:
        assignee = i.get("assignee")
        if not assignee:
            continue

        issue_team = get_team(i.get("board_name", ""), i.get("sprint_name", ""))

        key = (assignee, issue_team)
        if key not in assignee_stats:
            assignee_stats[key] = {"issue_count": 0, "total_sp": 0, "done_count": 0, "in_progress_count": 0}

        assignee_stats[key]["issue_count"] += 1
        assignee_stats[key]["total_sp"] += i.get("reported_sp", 0) or 0
        if i.get("status_category") == "完了":
            assignee_stats[key]["done_count"] += 1
        elif i.get("status_category") == "進行中":
            assignee_stats[key]["in_progress_count"] += 1

    return [
        {
            "assignee": k[0],
            "team": k[1],
            "issue_count": s["issue_count"],
            "total_sp": round(s["total_sp"], 1),
            "done_count": s["done_count"],
            "in_progress_count": s["in_progress_count"],
        }
        for k, s in assignee_stats.items()
    ]


@app.get("/api/issues")
def get_issues(
    team: Optional[str] = Query(None),
    limit: int = Query(100)
):
    """Get issues list."""
    supabase = get_supabase()

    # Get completion dates
    changelog = supabase.table("issue_changelog").select("*").eq("field", "status").execute()
    completion_dates = {}
    for cl in changelog.data:
        if cl.get("to_string") in DONE_STATUSES:
            issue_key = cl.get("issue_key")
            created = cl.get("created")
            if created:
                if issue_key not in completion_dates or created < completion_dates[issue_key]:
                    completion_dates[issue_key] = created

    issues = supabase.table("issues").select("*").gte("created", str(DASHBOARD_START)).order("created", desc=True).limit(limit).execute().data

    if team and team != "全チーム":
        issues = [i for i in issues if get_team(i.get("board_name", ""), i.get("sprint_name", "")) == team]

    result = []
    for i in issues:
        created = i.get("created", "")[:10] if i.get("created") else ""
        completed = completion_dates.get(i["key"], "")
        if completed:
            completed = completed[:10]

        result.append({
            "key": i.get("key"),
            "summary": i.get("summary"),
            "status": i.get("status"),
            "status_category": i.get("status_category"),
            "priority": i.get("priority"),
            "assignee": i.get("assignee"),
            "sprint_name": i.get("sprint_name"),
            "team": get_team(i.get("board_name", ""), i.get("sprint_name", "")),
            "reported_sp": i.get("reported_sp"),
            "created_date": created,
            "completed_date": completed,
        })

    return result[:limit]


@app.get("/api/sufficiency")
def get_sufficiency():
    """Get sufficiency alert data."""
    supabase = get_supabase()

    result = supabase.table("sufficiency_snapshots").select("*").order("snapshot_date", desc=True).limit(1).execute()

    if not result.data:
        return None

    row = result.data[0]
    return {
        "snapshot_date": row.get("snapshot_date"),
        "future_sp": row.get("future_sp", 0),
        "avg_velocity": row.get("avg_velocity", 0),
        "sufficiency": row.get("sufficiency", 0),
    }


@app.get("/api/individual-velocity")
def get_individual_velocity(days: int = Query(0)):
    """Get individual velocity per week."""
    supabase = get_supabase()

    date_from = str(DASHBOARD_START)
    if days > 0:
        date_from = str(max(date.today() - timedelta(days=days), DASHBOARD_START))

    # Get completion dates
    changelog = supabase.table("issue_changelog").select("*").eq("field", "status").execute()
    completion_dates = {}
    for cl in changelog.data:
        if cl.get("to_string") in DONE_STATUSES:
            issue_key = cl.get("issue_key")
            created = cl.get("created")
            if created:
                if issue_key not in completion_dates or created < completion_dates[issue_key]:
                    completion_dates[issue_key] = created

    issues = supabase.table("issues").select("*").execute().data

    from datetime import datetime
    weekly = {}

    for issue in issues:
        key = issue.get("key")
        assignee = issue.get("assignee")
        if not assignee or key not in completion_dates:
            continue

        completed_str = completion_dates[key]
        try:
            completed = datetime.fromisoformat(completed_str.replace("Z", "+00:00"))
        except:
            continue

        if completed.date() < datetime.fromisoformat(date_from).date():
            continue

        issue_team = get_team(issue.get("board_name", ""), issue.get("sprint_name", ""))
        week_start = completed.date() - timedelta(days=completed.weekday())
        week_label = f"{week_start.isocalendar()[0]}-W{week_start.isocalendar()[1]:02d}"

        key_tuple = (str(week_start), week_label, assignee, issue_team)
        if key_tuple not in weekly:
            weekly[key_tuple] = {"done_sp": 0, "issue_count": 0}

        weekly[key_tuple]["done_sp"] += issue.get("reported_sp", 0) or 0
        weekly[key_tuple]["issue_count"] += 1

    result = [
        {
            "week_start": k[0],
            "week_label": k[1],
            "assignee": k[2],
            "team": k[3],
            "done_sp": round(v["done_sp"], 1),
            "issue_count": v["issue_count"]
        }
        for k, v in weekly.items()
    ]

    return sorted(result, key=lambda x: (x["week_start"], x["assignee"]))


@app.get("/api/sprint-achievement")
def get_sprint_achievement(team: Optional[str] = Query(None)):
    """Get sprint achievement metrics."""
    supabase = get_supabase()

    # Get sprint issues mapping
    sprint_issues = supabase.table("sprint_issues").select("*").execute().data

    # Get issues
    issues = supabase.table("issues").select("*").execute().data
    issues_by_key = {i["key"]: i for i in issues}

    # Count sprints per issue
    issue_sprint_count = {}
    for si in sprint_issues:
        key = si["issue_key"]
        issue_sprint_count[key] = issue_sprint_count.get(key, 0) + 1

    # Group by sprint
    sprint_data = {}
    for si in sprint_issues:
        sprint_name = si["sprint_name"]
        issue_key = si["issue_key"]
        issue = issues_by_key.get(issue_key)
        if not issue or not issue.get("reported_sp"):
            continue

        issue_team = get_team(issue.get("board_name", ""), issue.get("sprint_name", ""))
        if team and team != "全チーム" and issue_team != team:
            continue

        key = (sprint_name, issue_team)
        if key not in sprint_data:
            sprint_data[key] = {
                "planned_sp": 0, "done_sp": 0, "carryover_sp": 0,
                "total_issues": 0, "carryover_count": 0
            }

        sp = issue.get("reported_sp", 0) or 0
        sprint_data[key]["planned_sp"] += sp
        sprint_data[key]["total_issues"] += 1

        if issue.get("status_category") == "完了":
            sprint_data[key]["done_sp"] += sp
        elif issue_sprint_count.get(issue_key, 0) > 1:
            sprint_data[key]["carryover_sp"] += sp
            sprint_data[key]["carryover_count"] += 1

    return [
        {
            "sprint_name": k[0],
            "team": k[1],
            "total_issues": d["total_issues"],
            "planned_sp": round(d["planned_sp"], 1),
            "done_sp": round(d["done_sp"], 1),
            "carryover_sp": round(d["carryover_sp"], 1),
            "carryover_count": d["carryover_count"],
            "achievement_pct": round(d["done_sp"] / d["planned_sp"] * 100, 1) if d["planned_sp"] > 0 else 0,
        }
        for k, d in sprint_data.items()
    ]
