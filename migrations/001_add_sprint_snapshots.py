"""
Migration 001: Add Sprint Snapshot Functionality

This migration:
1. Adds sprint_metadata table for storing Jira sprint dates
2. Adds planned_sp_snapshot and snapshot_created_at columns to synced_sprints
3. Backfills sprint metadata from Jira API
4. Creates snapshots for existing active/closed sprints (best-effort)

Run with: python migrations/001_add_sprint_snapshots.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from src import database as db
from src import jira_client as jira


def migrate_schema():
    """Phase 1: Apply schema changes"""
    print("=" * 60)
    print("Phase 1: Applying schema changes...")
    print("=" * 60)

    # init_db() will create sprint_metadata and add columns to synced_sprints
    db.init_db()

    print("✓ sprint_metadata table created")
    print("✓ synced_sprints.planned_sp_snapshot column added")
    print("✓ synced_sprints.snapshot_created_at column added")
    print()


def backfill_sprint_data():
    """Phase 2: Backfill sprint metadata and create snapshots"""
    print("=" * 60)
    print("Phase 2: Backfilling sprint data from Jira...")
    print("=" * 60)

    # Get all synced sprints from database
    con = db._connect()
    synced_sprints = con.execute("""
        SELECT sprint_id, board_name, sprint_name, state
        FROM synced_sprints
        ORDER BY sprint_id
    """).fetchdf()
    con.close()

    if synced_sprints.empty:
        print("⚠ No synced sprints found in database. Run sync first.")
        return

    print(f"Found {len(synced_sprints)} synced sprints")
    print()

    metadata_count = 0
    snapshot_count = 0
    errors = 0

    for _, row in synced_sprints.iterrows():
        sprint_id = row["sprint_id"]
        sprint_name = row["sprint_name"]
        state = row["state"]

        try:
            # Fetch full sprint details from Jira
            sprint_data = jira.get_sprint_details(sprint_id)

            # Extract dates
            start_date = sprint_data.get("startDate")
            end_date = sprint_data.get("endDate")

            # Upsert sprint_metadata
            db.upsert_sprint_metadata(
                sprint_id=sprint_id,
                sprint_name=sprint_name,
                start_date=start_date[:10] if start_date else None,
                end_date=end_date[:10] if end_date else None,
            )
            metadata_count += 1

            # Create snapshot for active/closed sprints if not already exists
            if state in ("active", "closed"):
                existing_snapshot = db.get_sprint_snapshot(sprint_id)
                if existing_snapshot is None:
                    # Calculate current SP sum as best-effort snapshot
                    current_sp = db.calculate_sprint_total_sp(sprint_name)
                    snapshot_date = start_date if start_date else datetime.now().isoformat()
                    db.create_sprint_snapshot(
                        sprint_id=sprint_id,
                        planned_sp=current_sp,
                        snapshot_date=snapshot_date,
                    )
                    snapshot_count += 1
                    print(f"  ✓ {sprint_name}: {current_sp:.1f} SP (backfill snapshot)")

        except Exception as e:
            print(f"  ✗ Error processing sprint {sprint_id} ({sprint_name}): {e}")
            errors += 1

    print()
    print(f"✓ Metadata updated for {metadata_count} sprints")
    print(f"✓ Created {snapshot_count} backfill snapshots")
    if errors > 0:
        print(f"⚠ {errors} errors occurred")
    print()


def verify_migration():
    """Phase 3: Verify migration success"""
    print("=" * 60)
    print("Phase 3: Verifying migration...")
    print("=" * 60)

    con = db._connect()

    # Check sprint_metadata
    metadata_count = con.execute("""
        SELECT COUNT(*) AS count FROM sprint_metadata
    """).fetchdf().iloc[0]["count"]

    # Check snapshots
    snapshot_count = con.execute("""
        SELECT COUNT(*) AS count
        FROM synced_sprints
        WHERE planned_sp_snapshot IS NOT NULL
    """).fetchdf().iloc[0]["count"]

    # Check active/closed sprints
    active_closed_count = con.execute("""
        SELECT COUNT(*) AS count
        FROM synced_sprints
        WHERE state IN ('active', 'closed')
    """).fetchdf().iloc[0]["count"]

    con.close()

    print(f"Sprint metadata records: {metadata_count}")
    print(f"Snapshots created: {snapshot_count}")
    print(f"Active/closed sprints: {active_closed_count}")
    print()

    if snapshot_count == active_closed_count:
        print("✓ All active/closed sprints have snapshots")
    else:
        print(f"⚠ {active_closed_count - snapshot_count} active/closed sprints missing snapshots")

    print()


def main():
    """Run the full migration"""
    print()
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "JTVO Migration 001: Sprint Snapshots" + " " * 12 + "║")
    print("╚" + "=" * 58 + "╝")
    print()

    # Step 1: Schema migration
    migrate_schema()

    # Step 2: Data backfill
    backfill_sprint_data()

    # Step 3: Verification
    verify_migration()

    print("=" * 60)
    print("Migration complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Run sync.py to sync new sprints with snapshot functionality")
    print("2. Check the dashboard to verify planned SP calculations")
    print()


if __name__ == "__main__":
    main()
