# Testing Infrastructure

## Overview

This project now follows Test-Driven Development (TDD) practices with integrated CI/CD testing.

## Running Tests

### Quick Commands

```bash
# Run all tests
make test

# Run tests with verbose output
python3 -m pytest tests/ -v

# Run specific test file
python3 -m pytest tests/test_database.py -v

# Run specific test
python3 -m pytest tests/test_database.py::TestDatabaseInit::test_init_db_creates_tables -v
```

### Other Development Commands

```bash
# Install dependencies
make install

# Run linters (flake8, mypy)
make lint

# Format code (black, isort)
make format

# Security checks (safety, bandit)
make security

# Clean temporary files
make clean

# Run all quality checks
make all
```

## Test Coverage

Current coverage: **12.41%** (target: 10%)

Coverage breakdown:
- `src/database.py`: 38% (131/341 statements)
- `src/jira_client.py`: 0% (needs tests)
- `src/app.py`: 0% (needs tests)
- `src/analyzer.py`: 0% (needs tests)

## Test Structure

```
tests/
├── __init__.py
└── test_database.py          # Database module unit tests (14 tests)
```

### Test Categories

1. **Database Initialization** - Verifies all tables are created correctly
2. **Team SQL Logic** - Tests team derivation CASE expressions
3. **Issue Operations** - Tests CRUD operations for issues
4. **Velocity Calculations** - Tests team velocity metrics
5. **Individual Leaderboards** - Tests contributor rankings
6. **Sprint Snapshots** - Tests snapshot creation and retrieval
7. **SQL Injection Prevention** - Security tests for parameterized queries

## Test Fixtures

The `test_db` fixture creates an isolated temporary DuckDB database for each test:

```python
@pytest.fixture(scope="function")
def test_db():
    """Create a temporary test database for each test."""
    # Creates temp database
    # Initializes schema
    # Yields database module
    # Cleans up after test
```

This ensures:
- Test isolation (no shared state)
- No pollution of production database
- Automatic cleanup after tests

## Continuous Integration

GitHub Actions runs tests automatically on:
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop` branches

See [.github/workflows/ci.yml](.github/workflows/ci.yml) for configuration.

## Adding New Tests

When making changes to the codebase, add corresponding tests:

1. **For new functions**: Add test cases covering:
   - Normal operation (happy path)
   - Edge cases (empty data, nulls, etc.)
   - Error conditions (invalid input, constraints)

2. **For bug fixes**: Add regression tests that would have caught the bug

3. **For refactoring**: Ensure existing tests still pass

### Example Test Template

```python
class TestNewFeature:
    """Test suite for new feature."""

    def test_basic_functionality(self, test_db):
        """Test that the feature works in normal conditions."""
        # Arrange
        data = create_test_data()

        # Act
        result = test_db.new_function(data)

        # Assert
        assert result == expected_value

    def test_edge_case_empty_data(self, test_db):
        """Test that the feature handles empty data correctly."""
        result = test_db.new_function(None)
        assert result == default_value

    def test_error_handling(self, test_db):
        """Test that invalid input raises appropriate errors."""
        with pytest.raises(ValueError):
            test_db.new_function(invalid_data)
```

## Coverage Goals

- **Short-term**: Increase to 30% coverage
- **Medium-term**: Reach 60% coverage
- **Long-term**: Maintain 80%+ coverage

Focus areas for test expansion:
1. Complete `database.py` coverage (currently 38%)
2. Add `jira_client.py` unit tests with mocked API calls
3. Add `analyzer.py` tests
4. Add integration tests for full sync workflow

## Best Practices

1. **Test Naming**: Use descriptive names that explain what is being tested
   - `test_upsert_issues_inserts_data` ✓
   - `test_upsert` ✗

2. **Test Independence**: Each test should be runnable in isolation
   - Use fixtures for setup
   - Don't rely on execution order
   - Clean up after tests

3. **Assert Messages**: Include helpful messages for failures
   ```python
   assert expected_tables.issubset(actual_tables), \
       f"Missing tables: {expected_tables - actual_tables}"
   ```

4. **Test Organization**: Group related tests in classes
   ```python
   class TestSprintSnapshot:
       def test_get_sprint_snapshot_none(self, test_db): ...
       def test_create_sprint_snapshot(self, test_db): ...
   ```

## Troubleshooting

### Tests Fail Due to Missing Dependencies

```bash
pip install -r requirements-dev.txt
```

### Coverage Too Low

The minimum coverage is set in `pytest.ini`:
```ini
--cov-fail-under=10
```

Adjust this value as more tests are added.

### DuckDB File Lock Issues

If tests fail with database lock errors:
```bash
rm -rf *.duckdb *.duckdb.wal
```

The test fixture should handle cleanup automatically, but manual cleanup may be needed if tests are interrupted.

## Security Testing

SQL injection prevention is tested in `TestSQLInjectionPrevention`:
- Verifies parameterized queries prevent injection
- Tests with malicious input strings
- Confirms database integrity after attempts

## Future Enhancements

- [ ] Add integration tests for sync workflow
- [ ] Add tests for `jira_client.py` with mocked API
- [ ] Add tests for `app.py` Streamlit components
- [ ] Add tests for `analyzer.py` AI analysis
- [ ] Add performance/load tests
- [ ] Add pre-commit hooks for automatic testing
- [ ] Set up test data fixtures for realistic scenarios
- [ ] Add snapshot testing for UI components
