"""Export DuckDB data to JSON for static HTML dashboard."""

import json
import sys
from pathlib import Path
from datetime import date, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src import database as db

def export_all():
    """Export all dashboard data to JSON files."""
    output_dir = Path(__file__).parent / "docs" / "data"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Dashboard start date
    DASHBOARD_START = date(2025, 12, 8)

    print("Exporting data...")

    # 1. Velocity by team
    velocity_data = db.get_velocity_by_team(DASHBOARD_START)
    velocity_json = velocity_data.to_dict(orient='records')
    for row in velocity_json:
        if row.get('week_start'):
            row['week_start'] = str(row['week_start'])

    # 2. Team summary
    team_summary = db.get_team_summary(DASHBOARD_START)
    team_summary_json = team_summary.to_dict(orient='records')

    # 3. Recent velocity trend (last 8 weeks)
    recent_trend = db.get_recent_velocity_trend()
    recent_trend_json = recent_trend.to_dict(orient='records')
    for row in recent_trend_json:
        if row.get('week_start'):
            row['week_start'] = str(row['week_start'])

    # 4. Active sprints progress
    sprint_progress = db.get_active_sprints_progress()
    sprint_progress_json = sprint_progress.to_dict(orient='records')

    # 5. Sprint achievement
    sprint_achievement = db.get_sprint_achievement(None)
    sprint_achievement_json = sprint_achievement.to_dict(orient='records')

    # 6. Sprint achievement timeline
    sprint_ach_tl = db.get_sprint_achievement_timeline(None)
    sprint_ach_tl_json = sprint_ach_tl.to_dict(orient='records')
    for row in sprint_ach_tl_json:
        if row.get('week_start'):
            row['week_start'] = str(row['week_start'])

    # 7. Assignee load
    load_data = db.get_assignee_load(None)
    load_data_json = load_data.to_dict(orient='records')

    # 8. Individual leaderboard
    leaderboard = db.get_individual_leaderboard(None, DASHBOARD_START)
    leaderboard_json = leaderboard.to_dict(orient='records')

    # 9. Period-based leaderboards
    leaderboard_periods = db.get_individual_leaderboard_by_period(None)
    leaderboard_periods_json = {
        'last_week': leaderboard_periods['last_week'].to_dict(orient='records'),
        'last_3_weeks': leaderboard_periods['last_3_weeks'].to_dict(orient='records'),
    }

    # 10. Status breakdown
    status_breakdown = db.get_status_breakdown(None, DASHBOARD_START)
    status_breakdown_json = status_breakdown.to_dict(orient='records')

    # 11. Individual velocity
    individual_velocity = db.get_individual_velocity(DASHBOARD_START)
    individual_velocity_json = individual_velocity.to_dict(orient='records')
    for row in individual_velocity_json:
        if row.get('week_start'):
            row['week_start'] = str(row['week_start'])

    # 12. Issues table
    issues_table = db.get_issues_for_table(None, DASHBOARD_START)
    issues_table_json = issues_table.to_dict(orient='records')
    for row in issues_table_json:
        for key in ['created_date', 'completed_date', 'updated']:
            if row.get(key):
                row[key] = str(row[key])

    # 13. Sufficiency alert
    sufficiency = db.get_sufficiency_alert()
    if sufficiency and sufficiency.get('snapshot_date'):
        sufficiency['snapshot_date'] = str(sufficiency['snapshot_date'])

    # Combine all data
    all_data = {
        'exportedAt': str(date.today()),
        'dashboardStart': str(DASHBOARD_START),
        'velocity': velocity_json,
        'teamSummary': team_summary_json,
        'recentTrend': recent_trend_json,
        'sprintProgress': sprint_progress_json,
        'sprintAchievement': sprint_achievement_json,
        'sprintAchievementTimeline': sprint_ach_tl_json,
        'assigneeLoad': load_data_json,
        'leaderboard': leaderboard_json,
        'leaderboardPeriods': leaderboard_periods_json,
        'statusBreakdown': status_breakdown_json,
        'individualVelocity': individual_velocity_json,
        'issues': issues_table_json,
        'sufficiency': sufficiency,
    }

    # Write to JSON file
    output_file = output_dir / "dashboard_data.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    print(f"Exported to {output_file}")
    print(f"  - {len(velocity_json)} velocity records")
    print(f"  - {len(team_summary_json)} team summaries")
    print(f"  - {len(issues_table_json)} issues")
    print(f"  - {len(individual_velocity_json)} individual velocity records")

    return output_file

if __name__ == "__main__":
    db.init_db()
    export_all()
