.PHONY: help test lint format security install clean

help:
	@echo "Available commands:"
	@echo "  make install    - Install dependencies"
	@echo "  make test       - Run tests with coverage"
	@echo "  make lint       - Run linters"
	@echo "  make format     - Format code with black and isort"
	@echo "  make security   - Run security checks"
	@echo "  make clean      - Remove temporary files"
	@echo "  make all        - Run format, lint, test, and security"

install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

test:
	python3 -m pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html

lint:
	python3 -m flake8 src/ tests/ --max-line-length=127 --extend-ignore=E203,W503
	python3 -m mypy src/ --ignore-missing-imports

format:
	python3 -m black src/ tests/
	python3 -m isort src/ tests/

security:
	python3 -m safety check
	python3 -m bandit -r src/ -ll

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache htmlcov coverage.xml .coverage

all: format lint test security
