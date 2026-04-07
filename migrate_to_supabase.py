"""Migrate data from DuckDB to Supabase PostgreSQL."""

import os
from pathlib import Path

import duckdb
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Configuration
DUCKDB_PATH = Path(__file__).parent.parent / "jtvo-final" / "data" / "jtvo.duckdb"
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")  # Use service key for migration

def get_duckdb_connection():
    return duckdb.connect(str(DUCKDB_PATH), read_only=True)

def get_supabase_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def migrate_table(con, supabase: Client, table_name: str, batch_size: int = 500):
    """Migrate a single table from DuckDB to Supabase."""
    print(f"Migrating {table_name}...")

    try:
        df = con.execute(f"SELECT * FROM {table_name}").fetchdf()
    except Exception as e:
        print(f"  Error reading {table_name}: {e}")
        return 0

    if df.empty:
        print(f"  No data in {table_name}")
        return 0

    # Convert timestamps to ISO format strings
    for col in df.columns:
        if df[col].dtype == 'datetime64[ns]' or 'timestamp' in str(df[col].dtype).lower():
            df[col] = df[col].apply(lambda x: x.isoformat() if pd.notna(x) else None)

    # Convert to list of dicts
    records = df.to_dict(orient='records')

    # Clean up None values and NaN
    import math
    for record in records:
        for key, value in list(record.items()):
            if value is None:
                pass  # Keep None
            elif isinstance(value, float) and math.isnan(value):
                record[key] = None

    # Insert in batches
    total = 0
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        try:
            supabase.table(table_name).upsert(batch).execute()
            total += len(batch)
            print(f"  Inserted {total}/{len(records)} records")
        except Exception as e:
            print(f"  Error inserting batch: {e}")
            # Try one by one
            for record in batch:
                try:
                    supabase.table(table_name).upsert(record).execute()
                    total += 1
                except Exception as e2:
                    print(f"    Failed record {record.get('key', record.get('id', '?'))}: {e2}")

    print(f"  Done: {total} records migrated")
    return total

def main():
    import pandas as pd

    print("=" * 60)
    print("JTVO DuckDB → Supabase Migration")
    print("=" * 60)

    # Check DuckDB file
    if not DUCKDB_PATH.exists():
        print(f"Error: DuckDB file not found at {DUCKDB_PATH}")
        return

    print(f"Source: {DUCKDB_PATH}")
    print(f"Target: {SUPABASE_URL}")
    print()

    con = get_duckdb_connection()
    supabase = get_supabase_client()

    # Tables in order (respecting foreign keys)
    tables = [
        "issues",
        "issue_comments",
        "issue_changelog",
        "ai_scores",
        "weekly_metrics",
        "sufficiency_snapshots",
        "synced_sprints",
        "sprint_issues",
        "sprint_metadata",
    ]

    results = {}
    for table in tables:
        try:
            count = migrate_table(con, supabase, table)
            results[table] = count
        except Exception as e:
            print(f"Error migrating {table}: {e}")
            results[table] = -1

    con.close()

    print()
    print("=" * 60)
    print("Migration Summary")
    print("=" * 60)
    for table, count in results.items():
        status = f"{count} records" if count >= 0 else "FAILED"
        print(f"  {table}: {status}")

if __name__ == "__main__":
    main()
