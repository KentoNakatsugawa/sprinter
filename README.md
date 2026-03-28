# JTVO — Jira Truth Velocity Observer

[![CI/CD](https://github.com/YOUR_USERNAME/jtvo-final/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/jtvo-final/actions)
[![codecov](https://codecov.io/gh/YOUR_USERNAME/jtvo-final/branch/main/graph/badge.svg)](https://codecov.io/gh/YOUR_USERNAME/jtvo-final)

AI-powered sprint analysis dashboard. Extracts Jira Cloud data, analyzes individual contribution quality with Gemini 1.5 Pro, and visualizes "real velocity" vs reported story points.

## 🚀 Quick Start

### Setup

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/jtvo-final.git
cd jtvo-final

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Configure environment
cp .env.example .env
# Edit .env with your Jira and Gemini credentials
```

### Run

```bash
# Start dashboard
streamlit run src/app.py

# Or sync data first
python sync.py
```

## 🧪 Testing & Development

```bash
# Run all tests
make test

# Run linting
make lint

# Format code
make format

# Run security checks
make security

# Run all quality checks
make all
```

**詳細は [CI_CD_SETUP.md](CI_CD_SETUP.md) を参照**

## 📋 Architecture

| File | Role |
|------|------|
| `src/app.py` | Streamlit dashboard |
| `src/jira_client.py` | Jira Cloud API extraction |
| `src/analyzer.py` | LangChain + Gemini 1.5 Pro analysis |
| `src/database.py` | DuckDB storage & aggregation |
| `sync.py` | Data synchronization script |

## 🔒 Security

- API tokens stored in `.env` (not committed)
- SQL injection prevention via parameterized queries
- XSS prevention via Streamlit native components
- Security scanning via Bandit in CI/CD

**詳細は [SECURITY_AUDIT.md](SECURITY_AUDIT.md) を参照**

## 📊 Testing

- **Current Coverage**: 12.41% (Target: 30%+)
- **Test Framework**: pytest
- **CI/CD**: GitHub Actions (Python 3.9, 3.10, 3.11)

**詳細は [TESTING.md](TESTING.md) を参照**

## 🛠️ Development Workflow

1. Create feature branch from `develop`
2. Make changes with tests
3. Run `make all` to verify quality
4. Push and create PR
5. CI/CD automatically runs all checks
6. Merge after approval and CI pass

## 📚 Documentation

- [CI/CD Setup Guide](CI_CD_SETUP.md) - CI/CD パイプライン設定
- [Testing Guide](TESTING.md) - テスト戦略とカバレッジ
- [Security Audit](SECURITY_AUDIT.md) - セキュリティ分析結果
