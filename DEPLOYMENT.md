# デプロイメントガイド

このドキュメントでは、JTVOダッシュボードを各種プラットフォームにデプロイする方法を説明します。

## 🎯 推奨プラットフォーム比較

| プラットフォーム | 難易度 | 無料枠 | 推奨度 | 備考 |
|---|---|---|---|---|
| **Streamlit Cloud** | ⭐ 簡単 | ✅ あり | ✅ 最推奨 | Streamlit公式、1クリックデプロイ |
| **Railway** | ⭐ 簡単 | ✅ あり | ○ 推奨 | Docker対応、$5/月無料クレジット |
| **Render** | ⭐ 簡単 | ✅ あり | ○ 推奨 | Docker対応、無料枠あり |
| **Vercel** | ⚠️ 不可 | - | ✗ | サーバーレスのためStreamlit非対応 |

> **注意**: VercelはサーバーレスアーキテクチャのためStreamlitアプリを直接デプロイできません。
> Streamlitはサーバーを常時起動する必要があるため、Streamlit Cloud、Railway、Renderを推奨します。

---

## 🚀 方法1: Streamlit Cloud (最推奨)

最も簡単な方法です。GitHubリポジトリと連携して自動デプロイできます。

### ステップ1: GitHubにプッシュ

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/jtvo-final.git
git push -u origin main
```

### ステップ2: Streamlit Cloudに登録

1. [share.streamlit.io](https://share.streamlit.io) にアクセス
2. GitHubアカウントでサインイン
3. "New app" をクリック

### ステップ3: アプリを設定

- **Repository**: `YOUR_USERNAME/jtvo-final`
- **Branch**: `main`
- **Main file path**: `src/app.py`

### ステップ4: Secretsを設定

1. "Advanced settings" をクリック
2. "Secrets" タブで以下を追加:

```toml
JIRA_BASE_URL = "https://your-domain.atlassian.net"
JIRA_EMAIL = "your-email@example.com"
JIRA_API_TOKEN = "your-api-token"
JIRA_STORY_POINTS_FIELD = "customfield_10016"
GEMINI_API_KEY = "your-gemini-api-key"
```

### ステップ5: デプロイ

"Deploy!" をクリックして完了！

**URL形式**: `https://your-app-name.streamlit.app`

### 自動デプロイ

GitHubの`main`ブランチにプッシュすると自動でデプロイされます。

---

## 🚂 方法2: Railway

Dockerコンテナとしてデプロイする方法です。

### ステップ1: Railwayに登録

1. [railway.app](https://railway.app) にアクセス
2. GitHubアカウントでサインイン

### ステップ2: プロジェクト作成

1. "New Project" → "Deploy from GitHub repo"
2. リポジトリを選択

### ステップ3: 環境変数を設定

Railway ダッシュボードで "Variables" タブを開き、以下を追加:

```
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-api-token
JIRA_STORY_POINTS_FIELD=customfield_10016
GEMINI_API_KEY=your-gemini-api-key
```

### ステップ4: デプロイ

自動でDockerfileを検出してビルド・デプロイされます。

**URL形式**: `https://your-app.up.railway.app`

---

## 🎨 方法3: Render

Dockerコンテナとしてデプロイする方法です。

### ステップ1: Renderに登録

1. [render.com](https://render.com) にアクセス
2. GitHubアカウントでサインイン

### ステップ2: Web Serviceを作成

1. "New" → "Web Service"
2. GitHubリポジトリを選択
3. 設定:
   - **Name**: `jtvo-dashboard`
   - **Environment**: `Docker`
   - **Plan**: `Free`

### ステップ3: 環境変数を設定

"Environment" タブで以下を追加:

```
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-api-token
JIRA_STORY_POINTS_FIELD=customfield_10016
GEMINI_API_KEY=your-gemini-api-key
```

### ステップ4: デプロイ

"Create Web Service" をクリックして完了！

**URL形式**: `https://jtvo-dashboard.onrender.com`

---

## 🐳 方法4: Docker (自前サーバー)

自前のサーバーやVPSにDockerでデプロイする方法です。

### ビルド & 実行

```bash
# イメージをビルド
docker build -t jtvo-dashboard .

# コンテナを実行
docker run -d \
  -p 8501:8501 \
  -e JIRA_BASE_URL="https://your-domain.atlassian.net" \
  -e JIRA_EMAIL="your-email@example.com" \
  -e JIRA_API_TOKEN="your-api-token" \
  -e JIRA_STORY_POINTS_FIELD="customfield_10016" \
  -e GEMINI_API_KEY="your-gemini-api-key" \
  --name jtvo \
  jtvo-dashboard
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'
services:
  jtvo:
    build: .
    ports:
      - "8501:8501"
    env_file:
      - .env
    restart: unless-stopped
```

```bash
docker-compose up -d
```

---

## ⚠️ Vercelについて

**VercelはStreamlitアプリに対応していません。**

理由:
- Vercelはサーバーレスアーキテクチャ（リクエストごとに起動・停止）
- Streamlitは常時起動するサーバーが必要
- WebSocketを使用するため、サーバーレス環境では動作しない

### 代替案

Vercelを使いたい場合は、以下の構成が考えられます:

1. **APIのみVercel + フロントエンド別途**
   - FastAPIでAPIを作成してVercelにデプロイ
   - フロントエンドは別途React等で作成

2. **Vercel + Railway/Render連携**
   - フロントエンド(Next.js等)をVercelに
   - Streamlitダッシュボードをiframeで埋め込み

ただし、これらは追加の開発が必要になるため、Streamlit Cloudの使用を推奨します。

---

## 🔐 セキュリティ考慮事項

### 環境変数の管理

- **絶対にコードにシークレットをハードコードしない**
- 各プラットフォームの環境変数機能を使用
- `.env`ファイルは`.gitignore`に含める

### アクセス制限

Streamlit Cloudでは以下のオプションがあります:

1. **Private app** (有料プラン): 認証が必要
2. **Public app** (無料プラン): URLを知っている人はアクセス可能

機密データを扱う場合は、Private appまたは自前サーバーでの運用を検討してください。

### SSL/TLS

すべての推奨プラットフォームはHTTPSを自動で提供します。

---

## 🔄 CI/CD連携

### Streamlit Cloud

GitHubの`main`ブランチにプッシュすると自動デプロイ。

### Railway / Render

GitHubと連携して自動デプロイ。CI/CDが通った後にデプロイするよう設定も可能。

### GitHub Actions連携例

`.github/workflows/ci.yml`に以下を追加してデプロイ前にテストを必須に:

```yaml
# 既存のCI/CDワークフローの後に...
deploy:
  name: Deploy
  runs-on: ubuntu-latest
  needs: [lint, test]  # CI成功後にデプロイ
  if: github.ref == 'refs/heads/main'
  
  steps:
    - name: Trigger Railway Deploy
      run: |
        curl -X POST "${{ secrets.RAILWAY_WEBHOOK_URL }}"
```

---

## 📊 監視とログ

### Streamlit Cloud

- ダッシュボードでログを確認可能
- アプリの使用状況を表示

### Railway

- ログストリーミング機能あり
- メトリクスダッシュボード

### Render

- ログ確認機能
- ヘルスチェック設定

---

## 🆘 トラブルシューティング

### デプロイが失敗する

1. **依存関係エラー**: `requirements.txt`を確認
2. **メモリ不足**: 無料プランの制限を確認
3. **ポート設定**: 環境変数`PORT`を確認

### アプリが起動しない

1. ログを確認
2. ローカルで`streamlit run src/app.py`が動作するか確認
3. 環境変数が正しく設定されているか確認

### データベースエラー

DuckDBはファイルベースなので、サーバーレス環境では永続化に注意:

```python
# メモリモードを使用する場合
DB_PATH = ":memory:"
```

永続化が必要な場合は、外部データベース(PostgreSQL等)の使用を検討してください。

---

## 📚 参考リンク

- [Streamlit Cloud Documentation](https://docs.streamlit.io/streamlit-community-cloud)
- [Railway Documentation](https://docs.railway.app/)
- [Render Documentation](https://render.com/docs)
- [Docker Documentation](https://docs.docker.com/)
