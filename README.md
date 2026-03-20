# qcatch

思いついたタスクを爆速でキャッチし、後で Gemini AI で自動分類する CLI タスク管理アプリ。

---

## クイックスタート

### Step 1: 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### Step 2: `.exe` をビルドして Windows Search に登録

```powershell
# 実行ポリシーの変更（初回のみ）
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

.\build.ps1
```

Windows Search に `qcatch` と入力すると、**トースト通知（右下ポップアップ）** が表示され、
コンソールを開かずにタスクを追加できます。

### Step 3: Gemini API キーを取得（無料・クレカ不要）

1. [Google AI Studio](https://aistudio.google.com/app/apikey) を開く
2. 「Create API key」で `AIzaSy...` 形式のキーを発行
3. PowerShell で永続設定:

```powershell
[Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "AIzaSy...", "User")
# → PowerShell を再起動して反映
```

> **⚠ 無料枠について（自動課金されない理由）**
> - Google AI Studio キーはクレカ不要
> - レート制限超過は「エラーで止まる」だけ。課金は発生しない
> - ★ Vertex AI（GCP）のキーは別物・有料なので使わないこと

---

## 使い方

### `toast` — トースト通知から追加（最速・推奨）

Windows Search から `qcatch` を起動すると右下にポップアップが出る。
コンソールウィンドウが前面に出ないため最も邪魔にならない。

```bash
python qcatch.py toast
qcatch toast     # .exe ビルド後
```

### `add` — コマンドラインから追加（API通信なし）

```bash
python qcatch.py add "牛乳を買う"
qcatch add "牛乳を買う"
```

### `list` — inbox を確認

```bash
python qcatch.py list
```

### `sort` — AI で自動分類

```bash
# Gemini 2.0 Flash（推奨・無料）
python qcatch.py sort

# Ollama（完全ローカル・オフライン）
python qcatch.py sort --local

# API なし（プロンプトをファイルに書き出す）
python qcatch.py sort --export
```

バックエンド設定: `python qcatch.py config set sort_backend ollama`（Ollama を常用する場合）

分類結果は `data/sorted_tasks.md` に保存。`inbox.txt` は `data/archive.txt` に移動してクリア。

---

## ファイル構成

```
ZzzMemo/
├── qcatch.py             # メインスクリプト（全機能）
├── qcatch.exe            # ビルド後に生成（.gitignore 済み）
├── build.ps1             # .exe ビルド + Windows Search 登録
├── requirements.txt
├── .gitignore
│
├── data/                 # 実行時データ（.gitignore 済み）
│   ├── inbox.txt         # 未整理タスク
│   ├── sorted_tasks.md   # AI 分類済みタスク
│   ├── archive.txt       # sort 済みの inbox バックアップ
│   └── sort_prompt.txt   # --export で生成されるプロンプト
│
├── docs/
│   ├── generate_docs.py  # PPTX ガイド生成
│   └── qcatch_guide.pptx
│
└── prompts/
    ├── gemini_questions.md    # 技術調査 Q&A（済）
    └── gemini_improvement.md  # 改善案調査 Q&A（済）
```

---

## 起動方法まとめ

| 方法 | 動作 | 条件 |
|---|---|---|
| Windows Search → Enter | トースト通知が出る（最速） | `build.ps1` 実行後・数分後 |
| `qcatch add "タスク"` | 即追記して終了 | `build.ps1` 実行後、即時 |
| `python qcatch.py prompt` | ターミナルで対話入力 | Python 環境があれば常時 |

---

## sort コマンドのバックエンド選択

| バックエンド | コスト | オフライン | コマンド |
|---|---|---|---|
| Gemini 2.0 Flash | 無料枠あり | 不可 | `qcatch sort`（GEMINI_API_KEY 設定） |
| Ollama（phi4 等） | 無料 | **可** | `qcatch sort --local` |
| Claude Haiku | 有料 | 不可 | `qcatch sort`（ANTHROPIC_API_KEY 設定） |
| 手動（export） | 無料 | 可 | `qcatch sort --export` |

Ollama を使う場合は [ollama.com](https://ollama.com) からアプリをインストール後:
```bash
ollama pull phi4      # 推奨（軽量・高精度）
# または
ollama pull llama3.2  # 代替
```

モデルは `python qcatch.py config set ollama_model llama3.2` で変更可能（デフォルト: `phi4`）。

---

## トラブルシューティング

### `build.ps1` が実行できない

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Windows Search に出てこない

- ショートカット作成直後は数分待つ
- 「qcatch Task Capture」でも検索してみる

### トースト通知が表示されない

Windows 11 の通知設定でアプリの通知が無効になっている可能性。
「設定 → システム → 通知」で確認。フォールバックとして `qcatch prompt` が使える。

### Gemini API エラー 429

レート制限（15回/分）。課金は発生しない。少し待って再試行。
