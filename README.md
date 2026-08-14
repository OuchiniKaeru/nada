# NADA — AI Agent Platform

AI エージェントの作成・管理・対話・運用メトリクスを 1 画面で行う Web プラットフォームです。
エージェントごとの個別チャットに加え、複数エージェントによる **スクワッド(Team) チャット**、**ストリーミング表示**、**ファイル添付**、**ダッシュボード（コスト/トークン集計）** を備えています。

- バックエンド: **FastAPI** + **Agno**（エージェントランタイム）
- フロントエンド: **Vanilla HTML / CSS / JavaScript**（ビルド不要）
- データベース: **PostgreSQL 16**（エージェントの設定・メモリ・実行メトリクス）

## 主な機能

- ユーザー認証（登録 / ログイン）
- エージェント CRUD（モデル / プロバイダー / Skills / MCP / Tools の選択）
- エージェント個別チャット（**SSE ストリーミング**、**Markdown + コードブロック/テーブル表示**、**ファイル添付**）
- スクワッド（Agno Team）チャット（リーダー + メンバーの協働）
- セッション管理（直近1週間表示、先頭20文字のタイトル自動生成）
- Skill / MCP / Tool 一覧
- ダッシュボード（実行コスト・トークン・作業時間の集計、日別グラフ、モデル価格マスター）
- テーマ切替（Dark Emerald / Light / Light Pink / Light Orange / Dark / Slate / Mono）

## アーキテクチャ

| 役割 | コンテナ / サービス | ポート |
| --- | --- | --- |
| フロントエンド | `frontend`（nginx + 静的ファイル） | http://localhost:3000 |
| API サーバー | `api`（FastAPI / uvicorn） | http://localhost:8000 |
| データベース | `db`（PostgreSQL 16） | localhost:5432 |

## 起動方法

### 1. 事前準備

```bash
# .env を作成（実キーは環境に合わせて設定）
cp .env.example .env
```

### 2. ビルド & 起動

```bash
docker compose up --build
```

> フロントエンドは HTML/CSS/JS/nginx 設定をイメージ内に焼き込むため、**フロントエンドを変更した場合は再ビルド**が必要です。
> バックエンドは `backend/` をボリュームマウントしているため、**再起動のみで反映**されます。

### 3. DB マイグレーション（初回・スキーマ変更時）

```bash
docker compose exec api alembic upgrade head
```

> API 起動時にモデル価格マスターテーブルが自動シードされます。

### 4. 動作確認

```bash
# ヘルスチェック
curl http://localhost:8000/health
```

ブラウザで http://localhost:3000 を開き、ユーザー登録 → エージェント作成 → チャット送信 → ダッシュボードを確認します。

### 5. 停止 / 破棄

```bash
docker compose down        # 停止
docker compose down -v     # 停止 + ボリューム破棄（データ初期化）
```

## 環境変数

`.env.example` を参考に `.env` を作成してください（**APIキー等はコミットしない**）。

- `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB`
- `DATABASE_URL`（例: `postgresql+asyncpg://nada:nada@db:5432/nada`）
- `SECRET_KEY`（JWT署名に使用。本番では必ず変更）
- `FRONTEND_URL` / `CORS_ALLOW_ORIGINS`
- AIプロバイダーキー: `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` / `OPENROUTER_API_KEY` / `AZURE_*` / `OLLAMA_*`

## ディレクトリ構成

```
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI ルーター（agents, chat, squads, skills, mcps, metrics, ...）
│   │   ├── models/       # SQLAlchemy モデル
│   │   ├── schemas/      # Pydantic スキーマ
│   │   ├── services/     # ビジネスロジック・実行/メトリクス/セッション
│   │   └── runtime/      # Agno エージェント/チーム ランタイム（SSE ストリーミング）
│   ├── alembic/          # マイグレーション
│   └── tests/
├── frontend/
│   ├── index.html
│   ├── css/              # main.css / chat.css（テーマ変数対応）
│   ├── js/               # chat, agents, squads, dashboard, ...
│   └── nginx.conf
├── docker-compose.yml    # 開発用
├── docker-compose.prod.yml
├── Dockerfile.backend
└── Dockerfile.frontend
```

## トラブルシューティング

### ポートが使用中の場合

```bash
lsof -i :3000 -i :8000 -i :5432
# docker-compose.yml の ports を変更して再起動
docker compose down
docker compose up --build
```

### ストリーミングが途中で切れる / 初回応答が遅い

Agno のツール/MCP/Skills が多いと初回レスポンスまで時間がかかることがあります。
`frontend/nginx.conf` の `proxy_read_timeout` / `proxy_send_timeout` を確認してください。

## ライセンス

ライセンスはMITです。