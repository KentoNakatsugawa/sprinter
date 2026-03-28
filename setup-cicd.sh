#!/bin/bash
# CI/CD Setup Script
# このスクリプトは、プロジェクトのCI/CD環境を初期化します

set -e  # エラーで即座に終了

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  JTVO CI/CD Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 1. Gitリポジトリ確認/初期化
echo "📦 Step 1: Git Repository Setup"
if [ ! -d ".git" ]; then
    echo "  ⚠️  Not a git repository. Initializing..."
    git init
    git branch -M main
    echo "  ✓ Git repository initialized"
else
    echo "  ✓ Git repository already exists"
fi
echo ""

# 2. 依存関係のインストール
echo "📚 Step 2: Installing Dependencies"
if [ -f "requirements-dev.txt" ]; then
    echo "  Installing development dependencies..."
    python3 -m pip install -r requirements-dev.txt
    echo "  ✓ Development dependencies installed"
else
    echo "  ⚠️  requirements-dev.txt not found"
fi
echo ""

# 3. Pre-commitフックのインストール
echo "🪝 Step 3: Installing Pre-commit Hooks"
if command -v pre-commit &> /dev/null; then
    pre-commit install
    echo "  ✓ Pre-commit hooks installed"
    echo "  Running pre-commit on all files..."
    pre-commit run --all-files || echo "  ⚠️  Some checks failed - please fix and commit"
else
    echo "  ⚠️  pre-commit not found. Installing..."
    python3 -m pip install pre-commit
    pre-commit install
    echo "  ✓ Pre-commit installed and hooks configured"
fi
echo ""

# 4. .envファイルの確認
echo "🔐 Step 4: Environment Configuration"
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "  Creating .env from .env.example..."
        cp .env.example .env
        echo "  ⚠️  Please edit .env with your credentials"
    else
        echo "  ⚠️  .env.example not found"
    fi
else
    echo "  ✓ .env file already exists"
fi
echo ""

# 5. .gitignoreの確認
echo "📝 Step 5: Git Ignore Configuration"
if [ ! -f ".gitignore" ]; then
    echo "  Creating .gitignore..."
    cat > .gitignore << 'EOF'
# Environment
.env
*.env
!.env.example

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Testing
.pytest_cache/
.coverage
.coverage.*
htmlcov/
.tox/
coverage.xml
*.cover
.hypothesis/
pytest-report.xml

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# Database
*.duckdb
*.duckdb.wal
*.db

# Logs
*.log

# OS
.DS_Store
Thumbs.db

# Pre-commit
.pre-commit-config.yaml.bak
EOF
    echo "  ✓ .gitignore created"
else
    echo "  ✓ .gitignore already exists"
fi
echo ""

# 6. 初回テスト実行
echo "🧪 Step 6: Running Tests"
if command -v pytest &> /dev/null; then
    echo "  Running test suite..."
    pytest tests/ -v --cov=src --cov-report=term-missing || echo "  ⚠️  Some tests failed"
    echo "  ✓ Tests completed"
else
    echo "  ⚠️  pytest not found"
fi
echo ""

# 7. セットアップ完了メッセージ
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ CI/CD Setup Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Next steps:"
echo ""
echo "1. Configure .env file:"
echo "   vim .env"
echo ""
echo "2. Create initial commit:"
echo "   git add ."
echo "   git commit -m \"Initial commit with CI/CD setup\""
echo ""
echo "3. Add GitHub remote (replace YOUR_USERNAME/YOUR_REPO):"
echo "   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git"
echo "   git push -u origin main"
echo ""
echo "4. Enable GitHub Actions:"
echo "   - Go to: https://github.com/YOUR_USERNAME/YOUR_REPO/actions"
echo "   - Click 'I understand my workflows, go ahead and enable them'"
echo ""
echo "5. (Optional) Setup Codecov:"
echo "   - Sign up at: https://codecov.io"
echo "   - Add your repository"
echo "   - Copy CODECOV_TOKEN to GitHub Secrets"
echo ""
echo "Available commands:"
echo "  make test      - Run tests with coverage"
echo "  make lint      - Run linters"
echo "  make format    - Format code"
echo "  make security  - Run security checks"
echo "  make all       - Run all quality checks"
echo ""
echo "Documentation:"
echo "  - CI/CD Setup:  CI_CD_SETUP.md"
echo "  - Testing:      TESTING.md"
echo "  - Security:     SECURITY_AUDIT.md"
echo ""
