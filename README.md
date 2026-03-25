# ZzzMemo

AI 搭載のパーソナルタスク管理 Web アプリ。タスク・日記・語学学習・Google Calendar 連携をブラウザ上で一元管理する。

---

## クイックスタート

### 1. 依存パッケージのインストール

```powershell
pip install -r requirements.txt
```

### 2. Gemini API キーを設定

```powershell
[Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "AIzaSy...", "User")
# PowerShell を再起動して反映
```

> API キーは [Google AI Studio](https://aistudio.google.com/app/apikey) で取得。無料枠 1500 回/日。

### 3. 起動

```powershell
cd C:\dev\ZzzMemo
python qcatch.py
```

ブラウザが自動で `http://localhost:5000` を開く。

---

## 機能一覧

### タスク管理
- **ステータス**: Inbox（未分類）/ Todo / 長期 / 完了 / ゴミ箱
- **重要度**: 高 / 中 / 低
- **期日**: 📅 ボタンで設定、「明日」「来週」などの自然言語入力にも対応
- **カテゴリ**: 仕事 / プライベート / 買い物 / 学習 / その他
- ドラッグ並び替え、一括完了、一括インポート
- 定期タスク（毎日 / 毎週 / 毎月）の自動生成
- チェックリスト（期日・アイテム管理）

### AI 機能
- **AI Sort**: タスクを自動分類（Gemini / Ollama / Anthropic カスケード）
- **タグ提案**: カテゴリ過多になったタスクをサブタグに分割提案
- **朝のブリーフィング**: 今日のタスク・状況を AI が要約

### チャット（AI 思考パートナー）

チャットタブから自然言語でタスクを操作できる。

| 発言例 | 実行される操作 |
|---|---|
| 「今日何をすべき？」 | タスク分析・優先度アドバイス |
| 「〇〇を追加して」 | タスク追加（期日・カテゴリ付きも可） |
| 「〇〇を完了にして」 | タスク完了 |
| 「〇〇の期日を明日に変更して」 | 期日変更 |
| 「〇〇を高優先度にして」 | 重要度変更 |
| 「〇〇を仕事カテゴリに」 | カテゴリ変更 |
| 「今日の予定は？」 | Google Calendar の予定を一覧表示 |
| 「明日午後3時にミーティングを追加して」 | カレンダー予定を確認UI付きで追加 |
| 「今週のタスク状況を分析して」 | 滞留・傾向・優先度の分析 |

### 日記 / ブログ
- 日付ナビ付き日記（オートセーブ）
- ブログ記事管理（タイトル・タグ付き）
- AI 提案: 空日記 → 完了タスクから話題提案 / 書いた後 → 内容充実案

### 語学学習（英語）
- 今日の完了タスク・日記から AI が英語練習問題を3問生成
- 問題ごとに回答を書いて AI 添削を受ける
- 添削後にフラッシュカード保存、マルチターン議論も可能
- SM-2 アルゴリズムによるカード復習スケジューリング

### Google Calendar / Tasks 連携
設定タブ → 「Google 連携」から OAuth2 認証を行う。

- **Push**: ZzzMemo のタスク（期日付き）を Google に同期
- **Pull**: Google Tasks で完了したタスクを ZzzMemo に反映
- **自動同期**: 30分ごとにバックグラウンドで実行（APScheduler）
- **カレンダー予定確認**: チャットで「今日の予定は？」
- **カレンダー予定追加**: チャットで自然言語 → 確認カード → 追加

---

## ファイル構成

```
ZzzMemo/
├── qcatch.py              # エントリポイント（python qcatch.py で起動）
├── requirements.txt
│
├── core/
│   ├── models.py          # データモデル（Task / Diary / Blog / FlashCard 等）
│   ├── storage.py         # 読み書き・マイグレーション・SM-2
│   ├── ai.py              # AI sort / タグ提案
│   ├── chat.py            # チャット・ブリーフィング（Function Calling）
│   ├── writing.py         # 日記・ブログ AI 提案
│   ├── lang.py            # 英語練習・添削・議論
│   └── google_sync.py     # Google Calendar / Tasks 同期
│
├── web/
│   ├── server.py          # FastAPI アプリ・ライフスパン
│   ├── deps.py            # 共有状態（app_data / logger）
│   └── routers/           # APIルーター（tasks / chat / diary / lang 等）
│
├── web/static/
│   ├── index.html         # SPA 本体
│   └── js/                # ES モジュール（16ファイル）
│
└── data/                  # 実行時データ（.gitignore 済み）
    ├── qcatch.db          # SQLite（タスク・チェックリスト等）
    ├── diary.json
    ├── blog.json
    ├── flashcards.json
    ├── chat_history.json
    └── app.log
```

---

## 設定

### AI バックエンド（Sort 用）

| バックエンド | コスト | 設定方法 |
|---|---|---|
| Gemini 2.5 Flash | 無料枠あり | `GEMINI_API_KEY` 環境変数 |
| Ollama（ローカル） | 無料・オフライン | Ollama インストール後、自動検出 |
| Claude Haiku | 有料 | `ANTHROPIC_API_KEY` 環境変数 |

Ollama を使う場合:
```powershell
# ollama.com からインストール後
ollama pull phi4
```

### チャットの AI キー

チャットタブ右上の ⚙ アイコンから Gemini API キーを入力（localStorage に保存）。

---

## トラブルシューティング

### ポート 5000 が使用中

```powershell
python qcatch.py --port 5001
```

### Google 認証エラー

`client_secret.json` がプロジェクトルートに必要。
GCP Console → APIs & Services → Credentials → OAuth 2.0 クライアント ID からダウンロード。

### Gemini API エラー 429

レート制限（15回/分）。課金は発生しない。少し待って再試行。
