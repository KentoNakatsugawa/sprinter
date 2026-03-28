"""Standalone sync script for JTVO — run via cron or launchd."""

from __future__ import annotations

import sys
import logging
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

from src import database as db
from src import jira_client as jira

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).resolve().parent / "data" / "sync.log"),
    ],
)
log = logging.getLogger("jtvo-sync")

TARGET_BOARDS = [
    {"id": 2, "name": "ICT開発ボード"},
    {"id": 135, "name": "AI/Analytics (NLTCS)"},
]


def run_sync():
    """Incremental sync: skip already-synced closed sprints."""
    log.info("=== JTVO Sync started ===")
    db.init_db()

    already_synced = db.get_closed_sprint_ids()
    total_issues = 0
    total_comments = 0
    skipped = 0
    errors = 0

    for board in TARGET_BOARDS:
        log.info(f"Board: {board['name']}")
        try:
            sprints = jira.get_sprints(board["id"])
        except Exception as e:
            log.error(f"  Failed to get sprints: {e}")
            errors += 1
            continue

        for s in sprints:
            sid = s["id"]
            state = s["state"]

            if state == "closed" and sid in already_synced:
                skipped += 1
                continue
            if state not in ("active", "future", "closed"):
                continue

            log.info(f"  {s['name']} ({state})")
            try:
                # Fetch detailed sprint info (including dates)
                sprint_details = jira.get_sprint_details(sid)
                start_date = sprint_details.get("startDate")
                end_date = sprint_details.get("endDate")

                # Upsert sprint metadata
                db.upsert_sprint_metadata(
                    sprint_id=sid,
                    sprint_name=s["name"],
                    start_date=start_date[:10] if start_date else None,
                    end_date=end_date[:10] if end_date else None,
                )

                # Check state transition for snapshot trigger
                previous_state = db.get_sprint_state(sid)
                new_state = state

                # Extract and sync issues
                i_df, c_df, cl_df = jira.extract_sprint_data(
                    board["name"], sid, s["name"],
                )
                db.upsert_issues(i_df)
                db.upsert_comments(c_df)
                db.upsert_changelog(cl_df)

                # Snapshot logic: Create snapshot if transitioning to active
                should_snapshot = (
                    new_state == "active" and
                    previous_state != "active" and
                    db.get_sprint_snapshot(sid) is None
                )

                if should_snapshot:
                    # Rebuild sprint_issues to ensure accurate calculation
                    db.rebuild_sprint_issues()
                    planned_sp = db.calculate_sprint_total_sp(s["name"])
                    snapshot_date = start_date if start_date else datetime.now().isoformat()
                    db.create_sprint_snapshot(sid, planned_sp, snapshot_date)
                    log.info(f"    ✓ Created snapshot: {planned_sp:.1f} SP")

                # Update synced_sprints with new state
                db.mark_sprint_synced(sid, board["name"], s["name"], state)

                total_issues += len(i_df)
                total_comments += len(c_df)
                log.info(f"    {len(i_df)} issues, {len(c_df)} comments")
            except Exception as e:
                log.error(f"    Error: {e}")
                errors += 1

    log.info("Rebuilding sprint_issues and weekly metrics...")
    db.rebuild_sprint_issues()
    db.rebuild_weekly_metrics()

    future_sp = 0.0
    for board in TARGET_BOARDS:
        try:
            future_sp += jira.extract_future_sprint_sp(board["id"])
        except Exception:
            pass
    suf = db.calculate_sufficiency(future_sp)

    log.info(
        f"=== Sync complete: {total_issues} issues, {total_comments} comments, "
        f"{skipped} skipped, {errors} errors, sufficiency={suf['sufficiency']}% ==="
    )


if __name__ == "__main__":
    run_sync()
