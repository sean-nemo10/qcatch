# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## このディレクトリについて

`C:\dev\ZzzMemo` — **qcatch / ZzzMemo**。元は単一ファイルの CLI だったが、現在は
**FastAPI 製の Web ダッシュボード + 爆速キャプチャ CLI** に進化している。
タスク管理を中心に、日記・ブログ・フラッシュカード・語学練習・AIチャット・
Google Calendar/Tasks 連携を持つ個人向け生産性アプリ。

- **独立した git リポジトリ**（remote: `sean-from-japan/ZzzMemo`）。
  親の `C:\dev` も別の git リポジトリだが、ZzzMemo の作業はこのリポジトリ内で行う
  （flashcard アプリ `C:\dev\remember` も別リポジトリ）。
- **本番は Fly.io にデプロイ済み**（https://zzzmemo.fly.dev、region nrt、TZ=Asia/Tokyo）。
- ローカルとサーバーで同じ `qcatch.py` が動く（no-arg で Web ダッシュボード起動）。

---

## ファイル構成

| パス | 役割 |
|---|---|
| `qcatch.py` | エントリポイント。`add` / `prompt` と Web ダッシュボード起動のみ（薄い） |
| `core/` | ドメインロジック（Web から分離） |
| `core/models.py` | Pydantic データモデル（Task / Checklist / Diary / Blog / FlashCard 等） |
| `core/storage.py` | **SQLite 読み書き**・JSON→SQLite 移行・inbox 吸い上げ・定期/アーカイブ |
| `core/ai.py` | sort バックエンド（Gemini / Ollama / Anthropic）・タグ/分割提案・few-shot |
| `core/chat.py` | AIチャット（Gemini Function Calling） |
| `core/google_sync.py` | Google Calendar / Tasks 連携（OAuth・push/pull・重複排除） |
| `core/writing.py` `core/lang.py` | 日記/ブログ提案・語学練習のストリーム生成 |
| `web/server.py` | FastAPI アプリ組み立て・認証ミドルウェア・lifespan・スケジューラ |
| `web/deps.py` | 共有状態（`app_data`）・セッション認証・config 読み書き |
| `web/routers/` | API エンドポイント（tasks / checklists / recurring / chat / diary / blog / flashcards / lang / sync / config） |
| `web/static/` | SPA フロント（index.html + js/）+ PWA（manifest.json / sw.js / icons） |
| `mcp_server.py` | MCP サーバー。本番 HTTP API 経由でタスク操作（AIエージェント用） |
| `dedupe_calendar.py` | Google Calendar/Tasks の qcatch_id 重複イベント掃除ツール |
| `data/qcatch.db` | **主データストア（SQLite, WAL）** |
| `data/inbox.txt` | 未整理タスク（`add` で即追記 → 起動/GET 時に DB へ吸い上げ） |
| `data/token.json` | Google OAuth トークン（コミット禁止） |
| `data/*.json` `sorted_tasks.md` `done.txt` | 旧データ。初回のみ DB へ移行に使う（以後は読まれない） |
| `Dockerfile` `fly.toml` | Fly.io デプロイ定義 |
| `requirements.txt` | ローカル/ビルド用（win11toast・pyinstaller 等を含む） |
| `requirements-prod.txt` | 本番 Web サーバー用（fastapi・uvicorn 等） |
| `build.ps1` | exe ビルド + Windows Search ショートカット登録 |
| `docs/spec_slides.py` | 仕様 PPTX 生成 |

---

## コマンド

```bash
# ── ローカル実行 ──
python qcatch.py                 # Web ダッシュボードを起動（http://localhost:5000 を開く）
python qcatch.py add "タスク"     # inbox.txt に即追記（API通信・重いimportなし）
python qcatch.py prompt          # ターミナル対話入力（add の代替）
python qcatch.py toast           # 後方互換: 現在はダッシュボード起動にフォールバック

# ── ビルド / ドキュメント ──
.\build.ps1                      # exe ビルド + Windows Search 登録（PowerShell）
python docs/spec_slides.py       # 仕様 PPTX を再生成

# ── 本番デプロイ（Fly.io） ──
fly deploy --app zzzmemo         # Dockerfile からビルドしてリリース
fly logs --app zzzmemo           # 本番ログ
fly secrets list --app zzzmemo   # シークレット名一覧（値は出ない）
```

> 分類（sort）・タスク操作・設定変更は **Web UI / REST API（`/api/sort` 等）** から行う。
> 旧 CLI サブコマンド `list` / `sort` / `config` は廃止された。

---

## アーキテクチャ上の重要な判断

### データストアは SQLite（旧「SQLite 化しない」方針は撤回済み）
- 主ストアは `data/qcatch.db`（SQLite, WAL）。`core/storage.py` が一手に担う。
- 起動時に DB が空なら旧 JSON（`tasks.json` 等）から一度だけ移行する。
- `inbox.txt` は**爆速キャプチャ専用バッファ**として残置。`siphon_inbox()` が
  起動時と `GET /api/tasks` 時に DB へ吸い上げてクリアする。
- `sorted_tasks.md` / `done.txt` は初回移行（`migrate_from_existing`）でしか読まれない。
  → これらに直接書いても UI には反映されない（過去にタグ付き add が消えるバグの原因）。

### sort バックエンドの優先順位
`qcatch_config.json` の `sort_backend`（`auto` / `ollama` / `gemini` / `anthropic`）で決まる。
`auto` の場合: Ollama 起動中なら Ollama → `GEMINI_API_KEY` → `ANTHROPIC_API_KEY` の順。
実装は `web/routers/tasks.py` の `_do_sort()` + `core/ai.py`。モデルは Gemini 2.5 Flash。

### Google 同期は一方向（qcatch → Google）+ per-task フラグ
- 各タスクの `calendar_sync=True` かつ `due_date` ありのものだけ Google に出す。
- 時刻あり → Google Calendar イベント、00:00 → Google Tasks。
- 同期は qcatch が source of truth。予定だけ Google 側で消してもタスクが残れば再同期で復活する。
  消すならタスク自体を complete / `due_date` クリアする。
- 重複防止のため `qcatch_id` を拡張プロパティ/notes に埋め、`dedupe_calendar.py` で掃除可能。

### 認証（`web/deps.py`）
- `ZZZMEMO_USER` + `ZZZMEMO_PASS`（パスワード）と `ZZZMEMO_GOOGLE_EMAIL`（Google ログイン）。
- どちらも未設定ならローカル開発モード（認証スキップ）。
- `ZZZMEMO_API_KEY`（`X-Api-Key`）は MCP / 外部連携用の内部 API キー。
- セッショントークンは認証情報から決定論的に導出（サーバー側ストレージ不要）。

### MCP は本番 HTTP API のバックエンド
`mcp_server.py` は `https://zzzmemo.fly.dev` の REST API を `X-Api-Key` 認証で叩く。
Google 資格情報を持つ本番サーバーが唯一の同期主体なので、エージェント経由で
タスクを足しても重複イベントが出ない。設定は `.mcp.json`（Python 3.13 のフルパスを指定）。

---

## 設計上の制約

- **`add` は API 通信・重い import を絶対に増やさないこと**（待ち時間ゼロが絶対条件）。
- **`data/` のファイルは削除・上書きしないこと**（`qcatch.db` に全学習/履歴データ）。
  `token.json` は秘密情報なのでコミットも禁止。
- **検証目的でもリポジトリ内で Web サーバーを起動しないこと**。`storage.initialize()` が
  起動だけで inbox.txt 吸い上げ・DB 書込み・アーカイブを行い `data/` を変更してしまう。
  動作確認は `core/ web/ qcatch.py qcatch_config.json` を一時ディレクトリにコピーし、
  **空の `data/`**（token.json を入れない）で起動する（`PYTHONIOENCODING=utf-8` 必須）。
- **Fly.io では `fly secrets` が `fly.toml` の `[env]` を上書きする**（同名キー）。
- **本番コンテナは TZ=Asia/Tokyo**（naive `datetime.now()` の「今日」境界が JST 基準）。
- コミット/プッシュは明示的に求められた時のみ。`--no-verify` は使わない。
