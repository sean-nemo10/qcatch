# qcatch

思いついたタスクを爆速でテキストファイルに保存し、後で Gemini AI で自動分類する CLI タスク管理アプリ。

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

# ビルド + Windows Search ショートカット作成
.\build.ps1
```

これで Windows Search に `qcatch` と入力するだけで起動できるようになります。

### Step 3: Gemini API キーを取得（無料・クレカ不要）

1. [Google AI Studio](https://aistudio.google.com/app/apikey) を開く
2. 「Create API key」をクリックして `AIzaSy...` 形式のキーを発行
3. PowerShell で設定（永続化）:

```powershell
[Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "AIzaSy...", "User")
# → PowerShell を再起動して反映
```

> **⚠ 無料枠について（自動課金されない理由）**
> - Google AI Studio のキー（`AIzaSy...` で始まる）は**請求先アカウント（クレカ）が不要**
> - レート制限（15回/分・1,500回/日）を超えた場合は**エラーで止まるだけ**。課金は発生しない
> - 自動で有料プランに移行する仕組みはない
> - ★ Vertex AI（Google Cloud）のキーは別物・有料なので**使わないこと**

---

## 使い方

### `add` — 爆速メモ（待ち時間ゼロ）

```bash
python qcatch.py add "牛乳を買う"
python qcatch.py add "企画書を月曜までに仕上げる"

# .exe ビルド後
qcatch add "牛乳を買う"
```

`data/inbox.txt` にタイムスタンプ付きで即追記。API 通信なし。

### `list` — inbox を確認

```bash
python qcatch.py list
```

### `sort` — AI で自動分類

```bash
# Gemini（推奨・無料）→ GEMINI_API_KEY を設定していれば自動使用
python qcatch.py sort

# プロンプトをファイルに書き出す（API キーなしでも使える）
python qcatch.py sort --export
# → data/sort_prompt.txt を Claude.ai / Gemini に手動で貼り付け
```

- API キー優先順位: `GEMINI_API_KEY`（無料）> `ANTHROPIC_API_KEY`（有料）
- 分類結果は `data/sorted_tasks.md` に保存
- `inbox.txt` は `data/archive.txt` に移動してクリア

### `prompt` — 対話入力モード

ターミナルを開いて入力を促す。Windows Search から起動した際のメインモード。

---

## ファイル構成

```
ZzzMemo/
├── qcatch.py             # メインスクリプト（sort 含むフル機能）
├── qcatch_launcher.py    # .exe ビルド用軽量版（add/list/prompt のみ）
├── qcatch.exe            # ビルド後に生成（.gitignore 済み）
├── qcatch_add.bat        # ランチャー（ダブルクリック用）
├── build.ps1             # .exe ビルド + Windows Search 登録
├── setup.ps1             # 初期セットアップ（python.exe ベース）
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
    └── gemini_questions.md  # 調査済み Q&A
```

---

## 起動方法まとめ

| 方法 | コマンド | 条件 |
|---|---|---|
| Windows Search | `qcatch` で検索 → Enter | `build.ps1` 実行後・数分後 |
| PowerShell | `qcatch add "タスク"` | `build.ps1` 実行後、即時 |
| ダブルクリック | `qcatch_add.bat` | 常時（python 必要）|
| Win+R | `qcatch-add` | `setup.ps1` 実行後・再起動後 |

---

## トラブルシューティング

### `build.ps1` が実行できない

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Windows Search に出てこない

- `.exe` ショートカット作成直後は数分待つ
- 「qcatch Task Capture」でも検索してみる
- スタートメニューを右クリック → 「すべてのアプリ」から確認

### Gemini API エラー

```
429 RESOURCE_EXHAUSTED
```
レート制限（15回/分）。**課金は発生しない**。少し待って再試行してください。

### `GEMINI_API_KEY` が認識されない

```powershell
echo $env:GEMINI_API_KEY   # 確認
```

空の場合は設定後 PowerShell を再起動。
