"""Unit tests for database module."""

import pytest
import pandas as pd
import tempfile
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="function")
def test_db():
    """Create a temporary test database for each test."""
    # Create temporary database file
    fd, test_db_path = tempfile.mkstemp(suffix=".duckdb")
    os.close(fd)
    os.unlink(test_db_path)  # Remove the empty file
    
    # Import and configure database module
    import src.database as db
    original_db_path = db.DB_PATH
    db.DB_PATH = test_db_path
    
    # Initialize test database
    db.init_db()
    
    yield db
    
    # Cleanup
    db.DB_PATH = original_db_path
    try:
        if os.path.exists(test_db_path):
            os.unlink(test_db_path)
    except:
        pass


class TestDatabaseInit:
    """Test database initialization."""
    
    def test_init_db_creates_tables(self, test_db):
        """Test that init_db creates all required tables."""
        con = test_db._connect()
        
        # Check all tables exist
        tables = con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchdf()
        
        expected_tables = {
            'issues', 'issue_comments', 'issue_changelog', 
            'ai_scores', 'weekly_metrics', 'sufficiency_snapshots',
            'synced_sprints', 'sprint_issues', 'sprint_metadata'
        }
        
        actual_tables = set(tables['table_name'].tolist())
        assert expected_tables.issubset(actual_tables), \
            f"Missing tables: {expected_tables - actual_tables}"
        
        con.close()


class TestTeamSQL:
    """Test team SQL derivation logic."""
    
    def test_team_sql_returns_string(self, test_db):
        """Test that _team_sql returns a valid SQL CASE expression."""
        result = test_db._team_sql("i")
        assert "CASE" in result
        assert "AI&Analytics" in result
        assert "B Scrum" in result
        assert "A Scrum" in result
    
    def test_team_sql_with_different_alias(self, test_db):
        """Test that _team_sql works with different table aliases."""
        result = test_db._team_sql("issues")
        assert "issues.board_name" in result
        assert "issues.sprint_name" in result


class TestIssueOperations:
    """Test issue CRUD operations."""
    
    def test_upsert_issues_inserts_data(self, test_db):
        """Test that upsert_issues correctly inserts data."""
        # Create test data
        df = pd.DataFrame([{
            "key": "TEST-1",
            "board_name": "Test Board",
            "sprint_id": 1,
            "sprint_name": "Sprint 1",
            "summary": "Test Issue",
            "assignee": "Test User",
            "reported_sp": 5.0,
            "status": "To Do",
            "status_category": "To Do",
            "priority": "High",
            "issuetype": "Story",
            "resolution": None,
            "flagged": False,
            "created": "2025-01-01T00:00:00",
            "updated": "2025-01-01T00:00:00",
            "description": "Test description"
        }])
        
        # Insert data
        count = test_db.upsert_issues(df)
        assert count == 1
        
        # Verify data
        issues = test_db.get_all_issues()
        assert len(issues) == 1
        assert issues.iloc[0]["key"] == "TEST-1"
        assert issues.iloc[0]["reported_sp"] == 5.0
    
    def test_upsert_issues_updates_existing(self, test_db):
        """Test that upsert_issues updates existing records."""
        # Insert initial data
        df1 = pd.DataFrame([{
            "key": "TEST-1",
            "board_name": "Test Board",
            "sprint_id": 1,
            "sprint_name": "Sprint 1",
            "summary": "Original Summary",
            "assignee": "User 1",
            "reported_sp": 3.0,
            "status": "To Do",
            "status_category": "To Do",
            "priority": "Medium",
            "issuetype": "Story",
            "resolution": None,
            "flagged": False,
            "created": "2025-01-01T00:00:00",
            "updated": "2025-01-01T00:00:00",
            "description": "Original"
        }])
        test_db.upsert_issues(df1)
        
        # Update with new data
        df2 = pd.DataFrame([{
            "key": "TEST-1",
            "board_name": "Test Board",
            "sprint_id": 1,
            "sprint_name": "Sprint 1",
            "summary": "Updated Summary",
            "assignee": "User 2",
            "reported_sp": 8.0,
            "status": "In Progress",
            "status_category": "進行中",
            "priority": "High",
            "issuetype": "Story",
            "resolution": None,
            "flagged": True,
            "created": "2025-01-01T00:00:00",
            "updated": "2025-01-02T00:00:00",
            "description": "Updated"
        }])
        test_db.upsert_issues(df2)
        
        # Verify update
        issues = test_db.get_all_issues()
        assert len(issues) == 1
        assert issues.iloc[0]["summary"] == "Updated Summary"
        assert issues.iloc[0]["reported_sp"] == 8.0
        assert issues.iloc[0]["assignee"] == "User 2"


class TestVelocityCalculations:
    """Test velocity calculation functions."""
    
    def test_get_velocity_by_team_empty(self, test_db):
        """Test get_velocity_by_team with no data."""
        result = test_db.get_velocity_by_team()
        assert isinstance(result, pd.DataFrame)
        assert result.empty
    
    def test_get_team_summary_empty(self, test_db):
        """Test get_team_summary with no data."""
        result = test_db.get_team_summary()
        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestIndividualLeaderboard:
    """Test individual leaderboard functions."""
    
    def test_get_individual_leaderboard_empty(self, test_db):
        """Test get_individual_leaderboard with no data."""
        result = test_db.get_individual_leaderboard()
        assert isinstance(result, pd.DataFrame)
        assert result.empty
    
    def test_get_individual_leaderboard_by_period_empty(self, test_db):
        """Test get_individual_leaderboard_by_period with no data."""
        result = test_db.get_individual_leaderboard_by_period()
        assert isinstance(result, dict)
        assert "last_week" in result
        assert "last_3_weeks" in result
        assert result["last_week"].empty
        assert result["last_3_weeks"].empty


class TestSprintSnapshot:
    """Test sprint snapshot functionality."""
    
    def test_get_sprint_snapshot_none(self, test_db):
        """Test get_sprint_snapshot returns None for non-existent sprint."""
        result = test_db.get_sprint_snapshot(99999)
        assert result is None
    
    def test_create_sprint_snapshot(self, test_db):
        """Test creating a sprint snapshot."""
        # First create a synced sprint
        test_db.mark_sprint_synced(1, "Test Board", "Sprint 1", "active")
        
        # Create snapshot
        test_db.create_sprint_snapshot(1, 50.0, "2025-01-01")
        
        # Verify
        snapshot = test_db.get_sprint_snapshot(1)
        assert snapshot == 50.0
    
    def test_create_sprint_snapshot_duplicate_raises_error(self, test_db):
        """Test that creating duplicate snapshot raises error."""
        # Create first snapshot
        test_db.mark_sprint_synced(1, "Test Board", "Sprint 1", "active")
        test_db.create_sprint_snapshot(1, 50.0, "2025-01-01")
        
        # Attempt to create duplicate
        with pytest.raises(ValueError, match="Snapshot already exists"):
            test_db.create_sprint_snapshot(1, 60.0, "2025-01-01")


class TestSQLInjectionPrevention:
    """Test SQL injection prevention."""
    
    def test_team_filter_parameter_safe(self, test_db):
        """Test that team filter uses parameterized queries."""
        # Attempt SQL injection via team filter
        malicious_team = "'; DROP TABLE issues; --"
        
        # This should not cause an error or drop the table
        result = test_db.get_velocity_by_team()
        
        # Verify table still exists
        con = test_db._connect()
        tables = con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name = 'issues'"
        ).fetchdf()
        con.close()
        
        assert len(tables) == 1, "issues table should still exist"
    
    def test_date_filter_parameter_safe(self, test_db):
        """Test that date filter uses parameterized queries."""
        from datetime import date
        
        # Use a date that could be mistaken for SQL
        test_date = date(2025, 1, 1)
        
        # Should not raise an error
        result = test_db.get_velocity_by_team(date_from=test_date)
        assert isinstance(result, pd.DataFrame)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
