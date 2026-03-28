# セキュリティ監査レポート

実施日: 2026-03-24

## 🔴 重大リスク (Critical)

なし

## 🟡 中リスク (Medium)

### 1. 機密情報の管理
**場所**: `.env` ファイル
**リスク**: Jira API トークンと Gemini API キーが平文で保存されている

**現状**:
- ✅ `.gitignore` に `.env` が含まれており、Git管理外
- ✅ 環境変数経由で読み込み
- ⚠️ `.env.example` ファイルが存在しない

**推奨対応**:
1. `.env.example` ファイルを作成し、プレースホルダーを提供
2. README に環境変数のセットアップ手順を記載
3. 本番環境では、環境変数を直接設定（`.env` ファイル不使用）

### 2. エラーハンドリングとログ出力
**場所**: `sync.py`, `jira_client.py`
**リスク**: エラーメッセージに機密情報が含まれる可能性

**現状**:
- ✅ 一般的な Exception キャッチ
- ⚠️ ログファイル (`data/sync.log`) に詳細なエラーが記録される可能性

**推奨対応**:
1. ログファイルを `.gitignore` に追加（既に `data/` が含まれているため対応済み）
2. エラーメッセージから機密情報を除外

### 3. レート制限と DoS 対策
**場所**: `jira_client.py`
**リスク**: Jira API への過度なリクエストによる制限

**現状**:
- ✅ 429 エラーのリトライロジック実装済み
- ✅ ページング間にスリープ (0.5秒)
- ✅ 最大3回のリトライ

**推奨対応**:
- 現状の実装で十分

## 🟢 低リスク (Low)

### 4. データ検証
**場所**: `database.py`, `app.py`
**リスク**: ユーザー入力の不適切な検証

**現状**:
- ✅ DuckDB のパラメータ化クエリを使用（SQL インジェクション対策済み）
- ✅ Streamlit のネイティブコンポーネント使用（XSS 対策済み）
- ✅ チーム名、日付などのフィルターは事前定義された値のみ

**推奨対応**:
- 現状の実装で十分

### 5. HTTPS / TLS
**場所**: `jira_client.py`
**リスク**: 通信の盗聴

**現状**:
- ✅ Jira Cloud API は HTTPS 必須
- ✅ requests ライブラリはデフォルトで証明書検証

**推奨対応**:
- 現状の実装で十分

## ✅ 良好な実装

1. **SQL インジェクション対策**
   - パラメータ化クエリを一貫して使用
   - f-string は SQL 構造のみに使用、ユーザー入力は `?` プレースホルダー経由

2. **XSS 対策**
   - Streamlit の `unsafe_allow_html=True` は静的HTMLのみで使用
   - ユーザー入力を直接HTML に埋め込まない

3. **認証情報の管理**
   - 環境変数経由での読み込み
   - `.gitignore` で `.env` を除外

4. **依存関係の管理**
   - 信頼できるライブラリ使用（requests, pandas, streamlit, duckdb）

## 推奨される追加対策

### 即時対応（優先度: 高）

1. **`.env.example` の作成**
```bash
# Jira Cloud
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-api-token-here
JIRA_STORY_POINTS_FIELD=customfield_10016

# Google Gemini
GEMINI_API_KEY=your-gemini-api-key-here
```

2. **README のセキュリティセクション追加**
   - 環境変数の設定手順
   - API トークンの取得方法
   - セキュリティベストプラクティス

### 中期対応（優先度: 中）

1. **ログローテーション**
   - `sync.log` のサイズ制限
   - 古いログの自動削除

2. **アクセス制御**
   - Streamlit Cloud デプロイ時の認証設定
   - IP ホワイトリスト検討

3. **依存関係の脆弱性スキャン**
   - `pip-audit` または `safety` の定期実行
   - GitHub Dependabot の有効化

### 長期対応（優先度: 低）

1. **監査ログ**
   - 重要な操作のログ記録
   - 異常なアクセスパターンの検出

2. **シークレット管理ツールの導入**
   - AWS Secrets Manager
   - HashiCorp Vault
   - Azure Key Vault

## 総評

**全体的なセキュリティレベル**: 🟢 良好

主要なセキュリティリスクは適切に対処されています。
`.env.example` の作成と README の更新を推奨しますが、
現状でも社内ツールとしては十分なセキュリティレベルです。

