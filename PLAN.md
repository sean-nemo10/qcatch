# PLAN.md — qcatch Web UI リアーキテクチャ

## Goal

qcatch を Tkinter GUI から **FastAPI + ブラウザ UI** に移行する。
同時に、定期タスク・チェックリスト・複数選択完了・ゴミ箱・タグ承認フローを実装する。

**制約（不変）:**
- `qcatch add "text"` は API 通信なし・即終了を維持
- `data/` 内のファイルを破壊しない
- PyInstaller ビルドは後で対応（今回はスクリプト実行のみ検証）
- オフライン動作（AI 機能以外はローカルのみ）

---

## Files to Change

### 新規作成

| ファイル | 内容 |
|---|---|
| `core/__init__.py` | パッケージ初期化（空） |
| `core/models.py` | Pydantic モデル（Task, Checklist, RecurringRule, AppData） |
| `core/storage.py` | tasks.json の読み書き・inbox.txt の吸い上げ・既存データ移行 |
| `core/ai.py` | AI sort・タグ提案（qcatch.py から移植） |
| `web/__init__.py` | パッケージ初期化（空） |
| `web/server.py` | FastAPI アプリ・全 API ルート・サーバー起動ロジック |
| `web/static/index.html` | シングルページ UI（Vanilla JS、Tailwind CDN） |

### 変更

| ファイル | 変更内容 |
|---|---|
| `qcatch.py` | `cmd_add` のみ残し、他コマンドを `web/server.py` 起動に委譲。Tkinter コード削除。 |
| `build.ps1` | `--add-data` で `web/static` と `core/` を同梱するよう更新（今回は記述のみ） |

---

## データモデル（tasks.json）

```json
{
  "tasks": [
    {
      "id": "uuid4",
      "text": "タスク本文",
      "status": "inbox|todo|done|trashed",
      "category": "仕事|プライベート|買い物|学習|その他|null",
      "tags": [],
      "created_at": "2026-03-22T10:00:00",
      "completed_at": null
    }
  ],
  "checklists": {
    "template-uuid": {
      "name": "サッカーの日の持ち物",
      "items": [{"text": "スパイク", "done": false}]
    }
  },
  "recurring": [
    {
      "id": "uuid4",
      "text": "週報を提出",
      "frequency": "daily|weekly|monthly",
      "days_of_week": [4],
      "day_of_month": null,
      "last_generated_date": "2026-03-22"
    }
  ]
}
```

status の意味:
- `inbox` — CLI add から来た未仕分けタスク
- `todo` — AI sort 済み（カテゴリあり）
- `done` — 完了（ゴミ箱から復元可能）
- `trashed` — 削除（ゴミ箱）

---

## API 設計（web/server.py）

| Method | Path | 役割 |
|---|---|---|
| GET | `/` | index.html を返す |
| GET | `/api/tasks` | 全タスク取得（status フィルタ可） |
| POST | `/api/tasks` | タスク追加（inbox status） |
| PATCH | `/api/tasks/{id}` | ステータス変更・カテゴリ変更 |
| DELETE | `/api/tasks/{id}` | 完全削除 |
| POST | `/api/sort` | AI sort 実行（inbox→todo に分類） |
| GET | `/api/checklists` | チェックリスト一覧 |
| POST | `/api/checklists` | テンプレート作成 |
| PATCH | `/api/checklists/{id}` | アイテム完了・リセット |
| DELETE | `/api/checklists/{id}` | テンプレート削除 |
| GET | `/api/recurring` | 定期ルール一覧 |
| POST | `/api/recurring` | 定期ルール作成 |
| DELETE | `/api/recurring/{id}` | 定期ルール削除 |
| POST | `/api/suggest-tags` | AI タグ提案（未コミット） |
| POST | `/api/apply-tags` | タグ変更を承認・適用 |
| GET | `/api/config` | 設定取得 |
| POST | `/api/config` | 設定変更 |

---

## UI タブ構成（index.html）

1. **Inbox** — 未仕分けタスク一覧・クイック追加・AI Sort ボタン
2. **タスク** — カテゴリ別 todo 一覧・複数選択・一括完了
3. **ゴミ箱** — done + trashed 一覧・復元・完全削除
4. **チェックリスト** — テンプレート一覧・新規作成・項目チェック
5. **定期タスク** — ルール一覧・新規作成（頻度・曜日設定）
6. **設定** — AI バックエンド設定・タグ提案→承認フロー

---

## Implementation Steps

### Phase 1: データ基盤

1. `core/__init__.py` 作成（空ファイル）
2. `core/models.py` 作成 — Pydantic モデル定義
3. `core/storage.py` 作成:
   - `load_data()` / `save_data()` — tasks.json の読み書き
   - `siphon_inbox()` — inbox.txt を読み込み tasks.json の inbox タスクに変換
   - `migrate_from_sorted_md()` — 既存 sorted_tasks.md を tasks に移行（初回のみ）
   - `check_recurring()` — 定期タスクのチェック・自動追加

### Phase 2: AI モジュール分離

4. `core/ai.py` 作成:
   - `sort_tasks(tasks, api_key)` — Gemini/Ollama/Anthropic で分類
   - `suggest_tags(tasks, api_key)` — 既存タスクへのタグ提案
   - 既存の `_sort_with_*` 関数を移植・整理

### Phase 3: Web サーバー

5. `web/__init__.py` 作成（空ファイル）
6. `web/server.py` 作成:
   - FastAPI アプリ・全 API ルート実装
   - `startup` イベント: siphon + recurring チェック
   - `run()` 関数: uvicorn 起動 + `webbrowser.open("http://localhost:5000")`
   - 終了時に inbox.txt を同期（sort済みタスクの逆流防止）

### Phase 4: Web UI

7. `web/static/index.html` 作成:
   - Tailwind CSS CDN（オフライン時はフォールバックスタイル）
   - 6タブ構成
   - Fetch API で FastAPI と通信
   - 複数選択: checkbox + 一括完了ボタン
   - ゴミ箱: status=trashed 表示・復元ボタン
   - チェックリスト: テンプレート作成フォーム・各アイテムのチェックボックス
   - 定期タスク: 頻度選択（daily/weekly/monthly）・曜日チェックボックス
   - 設定タブ: タグ提案ボタン → 差分モーダル → 承認ボタン

### Phase 5: エントリポイント整理

8. `qcatch.py` 修正:
   - `cmd_add()` のみ残す（inbox.txt への直接書き込み）
   - 他コマンド（toast/dashboard/sort/list/config）は `web.server.run()` に統合
   - Tkinter 関連コードを全削除
   - `main()`: 引数なし or toast/dashboard → `web.server.run()` 起動

---

## Risks

1. **Tailwind CDN のオフライン問題**
   - CDN が使えないと UI が崩れる
   - 対策: Tailwind のミニファイ版を `web/static/tailwind.min.css` にバンドル

2. **既存 sorted_tasks.md の移行精度**
   - Markdown パースは既存コードを流用するが、タイムスタンプ形式が混在する可能性
   - 対策: 移行失敗行は inbox status にフォールバック

3. **ポート競合（5000番）**
   - 別プロセスがポートを使っていると起動失敗
   - 対策: 空きポートを自動探索するロジックを追加

4. **PyInstaller での `web/static/` 同梱**
   - `--add-data` 指定が必要。今回は `.py` 実行のみで検証、exe ビルドは別フェーズ

5. **既存 `done.txt` の扱い**
   - tasks.json 移行後は done.txt に書かなくなる
   - 対策: 既存 done.txt の内容も初回移行時に `status=done` で取り込む

6. **`qcatch add` の import コスト**
   - `core/models.py` で pydantic を import すると遅くなる可能性
   - 対策: `cmd_add` は inbox.txt に直接書き込み（core/ を import しない）。models は web server 側でのみ使用。

---

## 承認後に着手します
