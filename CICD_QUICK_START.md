# CI/CD クイックスタートガイド

## 🚀 3分でセットアップ

### 方法1: 自動セットアップスクリプト

```bash
# セットアップスクリプトを実行
./setup-cicd.sh
```

これで以下が自動実行されます:
- ✅ Gitリポジトリ初期化
- ✅ 依存関係インストール
- ✅ Pre-commitフック設定
- ✅ .env作成
- ✅ テスト実行

### 方法2: 手動セットアップ

```bash
# 1. 依存関係インストール
pip install -r requirements-dev.txt

# 2. Pre-commitフックインストール
pre-commit install

# 3. 環境変数設定
cp .env.example .env
# .envを編集

# 4. 動作確認
make test
```

## 📋 セットアップ後の確認

### ローカルでテスト

```bash
# 全チェック実行
make all

# 個別実行
make test      # テスト
make lint      # Lint
make format    # コード整形
make security  # セキュリティ
```

### Gitにプッシュ

```bash
# 初回コミット
git add .
git commit -m "Initial commit with CI/CD"

# GitHubにプッシュ
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### GitHub Actionsを有効化

1. GitHubリポジトリを開く
2. **Actions** タブをクリック
3. **I understand my workflows, go ahead and enable them** をクリック

これで、プッシュやPR作成時に自動でCI/CDが実行されます！

## 🎯 日々の開発ワークフロー

### 機能追加の流れ

```bash
# 1. ブランチ作成
git checkout -b feature/new-feature

# 2. コード変更 + テスト追加
vim src/module.py
vim tests/test_module.py

# 3. ローカル確認
make test
make lint

# 4. コミット (pre-commitが自動実行)
git add .
git commit -m "Add new feature"

# 5. プッシュ
git push origin feature/new-feature

# 6. PR作成 → CI/CDが自動実行
```

### Pre-commitフックの動作

コミット時に自動で以下が実行されます:

```
git commit -m "message"
↓
[pre-commit] black..................Passed
[pre-commit] isort..................Passed
[pre-commit] flake8.................Passed
[pre-commit] bandit.................Passed
[pre-commit] check-yaml.............Passed
[pre-commit] trailing-whitespace....Passed
↓
コミット成功 ✅
```

エラーがある場合は自動修正されるか、エラーメッセージが表示されます。

## 🔍 CI/CDパイプラインの確認

### GitHub Actionsで確認

1. GitHubリポジトリの **Actions** タブを開く
2. 最新のワークフロー実行をクリック
3. 各ジョブの詳細を確認:
   - **Lint & Security**: コード品質チェック
   - **Test (Python 3.9/3.10/3.11)**: 各バージョンでテスト
   - **Test Summary**: 結果サマリー

### カバレッジレポートの確認

```bash
# ローカルで生成
make test

# ブラウザで開く
open htmlcov/index.html
```

または、GitHub Actions の Artifacts からダウンロード。

## 📊 CI/CD成功の確認

### ステータスバッジ

README.mdに表示されるバッジが緑色になればOK:

```markdown
[![CI/CD](https://github.com/YOUR_USERNAME/YOUR_REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/YOUR_REPO/actions)
```

### PRマージの条件

以下が全て✅になったらマージ可能:
- ✅ All checks have passed (CI/CD成功)
- ✅ Reviewers approved (レビュー承認)
- ✅ No merge conflicts (コンフリクトなし)

## 🐛 よくあるエラーと解決方法

### エラー1: pre-commitでコミット失敗

```
[pre-commit] black..................Failed
- hook id: black
- files were modified by this hook
```

**解決方法**: 自動修正されたファイルを再度コミット

```bash
git add .
git commit -m "message"  # 再度コミット
```

### エラー2: CIでテスト失敗

```
FAILED tests/test_module.py::test_function - AssertionError
```

**解決方法**: ローカルで再現・修正

```bash
# 失敗したテストを実行
pytest tests/test_module.py::test_function -v

# 修正後、再度コミット
git add .
git commit -m "Fix test"
git push
```

### エラー3: Lintエラー

```
src/module.py:42:80: E501 line too long (88 > 127 characters)
```

**解決方法**: 自動修正

```bash
make format  # blackとisortで自動修正
make lint    # 確認
```

### エラー4: カバレッジ不足

```
ERROR: Coverage failure: total of 8 is less than fail-under=10
```

**解決方法**: テストを追加するか、閾値を下げる

```bash
# pytest.iniを編集
--cov-fail-under=8  # 閾値を下げる

# または、テストを追加
vim tests/test_module.py
```

## 🔧 高度な設定

### Codecovの設定 (オプション)

1. [codecov.io](https://codecov.io)でサインアップ
2. リポジトリを追加
3. GitHubにトークンを設定:
   - Settings → Secrets → New repository secret
   - Name: `CODECOV_TOKEN`
   - Value: (Codecovから取得したトークン)

### テストするPythonバージョンの変更

`.github/workflows/ci.yml`を編集:

```yaml
matrix:
  python-version: ["3.9", "3.10", "3.11", "3.12"]
```

### Pre-commitでテストも実行

`.pre-commit-config.yaml`の最後のコメントを外す:

```yaml
- repo: local
  hooks:
    - id: pytest
      name: pytest
      entry: python -m pytest tests/ -v
      language: system
      pass_filenames: false
      always_run: true
```

⚠️ コミットが遅くなる可能性があります。

## 📚 関連ドキュメント

- **詳細設定**: [CI_CD_SETUP.md](CI_CD_SETUP.md)
- **テスト戦略**: [TESTING.md](TESTING.md)
- **セキュリティ**: [SECURITY_AUDIT.md](SECURITY_AUDIT.md)

## 💡 Tips

### コミット時間を短縮

Pre-commitが遅い場合:

```bash
# 特定のファイルのみチェック
SKIP=bandit git commit -m "message"

# 全スキップ (緊急時のみ)
git commit --no-verify -m "message"
```

### CIを高速化

キャッシュが有効になっているか確認:

```yaml
- name: Cache pip packages
  uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements*.txt') }}
```

### ローカルでCIと同じ環境を再現

```bash
# Docker使用 (推奨)
docker run -it --rm -v $(pwd):/app -w /app python:3.10 bash
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/ -v
```

## 🎉 完了！

これでCI/CDの設定が完了しました。

コードをプッシュするたびに自動でテスト・Lint・セキュリティチェックが実行され、コード品質が保たれます。

Happy coding! 🚀
