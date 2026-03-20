# qcatch 改善案 — Gemini Q&A（2026-03-20）

> 回答を受けて実装済みの内容:
> - `google-genai`（新SDK）に移行 → TensorFlow 依存解消・単一 exe ビルド可能に
> - `win11toast` による `toast` コマンド追加（Windows Search から通知入力）
> - Gemini 2.0 Flash + Pydantic 構造化出力（JSON Schema）
> - Ollama `--local` モード追加（`--local` フラグ、モデルは `QCATCH_OLLAMA_MODEL` で変更可能）
> - Windows Search ショートカット → `qcatch.exe toast` に更新

---

# qcatch 改善案を求める Gemini プロンプト（送信内容）

---

## 背景・現状（コンテキスト）

Windows 11 で動作する Python 製の CLI タスク管理アプリ「qcatch」を開発しています。
以下に現状の設計と実装上の判断をまとめます。これを踏まえて改善案を教えてください。

### 現在のアーキテクチャ

```
qcatch/
├── qcatch.py           # フル機能版（sort コマンド含む）
├── qcatch_launcher.py  # 軽量版（add/list/prompt のみ、PyInstaller でビルド）
├── qcatch.exe          # 6MB（qcatch_launcher.py から生成）
└── data/
    ├── inbox.txt       # タイムスタンプ付きタスクの蓄積場所
    └── sorted_tasks.md # AI 分類後の出力
```

### 2つのモード

1. **爆速メモモード（add）**
   - `qcatch add "牛乳を買う"` → `inbox.txt` に即追記して終了（API通信なし）
   - `qcatch.exe` で Windows Search から `qcatch prompt` として起動

2. **AI 自動整理モード（sort）**
   - `python qcatch.py sort` → Gemini 1.5 Flash（GEMINI_API_KEY が優先）で分類
   - 分類先カテゴリ: 仕事 / プライベート / 買い物 / 学習 / その他
   - 結果を `sorted_tasks.md`（マークダウン）に保存、inbox をアーカイブしてクリア

### 判明済みの制約・知見

- `python.exe` をターゲットにした Windows ショートカットは Windows Search に出ない（仕様）
  → `.exe` 化（PyInstaller）で解決済み
- `google-generativeai` ライブラリが TensorFlow まで依存するため PyInstaller でのビルドが不可
  → `qcatch.py`（フル機能）と `qcatch_launcher.py`（stdlib のみ）に分離
- Claude Code Pro サブスクリプション ≠ Anthropic API（別契約）
  → Gemini API（Google AI Studio・無料枠）を採用

---

## 質問 1: Python CLI を Windows に統合する最新のベストプラクティス（2025〜2026年）

### 現状の問題点

- `qcatch.exe prompt` は対話入力画面を出すが、Windows Search から起動すると
  コンソールウィンドウが一瞬開いて入力待ちになる体験がやや雑に見える
- `qcatch add "テキスト"` はコマンドラインからしか使えず、
  テキストを引数に渡す操作が「爆速」とは言いにくい場面もある

### 聞きたいこと

1. Windows 11 (2025〜2026年) で Python CLI アプリを「アプリ」として
   快適に使えるようにする方法として、PyInstaller 以外に何があるか？
   - **Nuitka** は PyInstaller より優れているか？ビルド時間・サイズ・速度の比較。
   - **cx_Freeze** や **briefcase** は選択肢になるか？
   - Python 3.13 以降の「フリースレッド」や「ネイティブバイナリ」生成は実用的か？

2. Windows の **トースト通知**（右下に出るポップアップ）から
   テキスト入力を受け取る方法はあるか？
   Python（または PowerShell）で実装できるか？
   `qcatch add` を「通知から呼び出す」ような UX が実現できれば理想。

3. **Windows Terminal のカスタムアクション / コマンドパレット** に
   qcatch を組み込む方法はあるか？

---

## 質問 2: Gemini API の最新動向と qcatch への活用（2025〜2026年）

### 現状の実装

```python
import google.generativeai as genai
genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-1.5-flash")
response = model.generate_content(prompt_text)
```

### 聞きたいこと

1. **2025〜2026年時点での無料枠の最新状況**
   - `gemini-1.5-flash` は今も無料枠の対象か？
   - `gemini-2.0-flash` や `gemini-2.5-pro` など新モデルの無料枠はどうなっているか？
   - 無料枠での「最もコスパの良いモデル」は何か？

2. **`google-generativeai` ライブラリは非推奨になったか？**
   - 新しい SDK `google-genai`（`pip install google-genai`）との違いは何か？
   - 移行する価値があるか？API の書き方はどう変わるか？
   - PyInstaller との依存問題（TensorFlow が引き込まれる件）は新 SDK で解消されるか？

3. **タスク分類の精度向上**
   - 現在はプレーンなマークダウンで出力させているが、
     JSON スキーマを指定して構造化出力させる方が良いか？
   - `response_mime_type: "application/json"` と JSON Schema を使った
     サンプルコードを示してほしい（Python・タスク分類用途）
   - Few-shot プロンプティングでカテゴリ分類の精度を上げる方法は？

---

## 質問 3: ローカル LLM（Ollama）との組み合わせ（オフライン・完全無料）

### 聞きたいこと

1. **Ollama の 2025〜2026年時点での状況**
   - Windows 11 での Ollama のインストールと Python 連携の最新手順
   - `ollama` Python ライブラリの基本的な使い方（タスク分類用途）
   - qcatch の `sort` コマンドを Ollama に対応させるサンプルコード

2. **qcatch のタスク分類に適した軽量モデル**
   - RAM 8〜16GB の PC で快適に動くモデルは何か？（Gemma3、Llama3.2、Phi-4 など）
   - タスク分類（短いテキスト・日英混在）に特化した推奨モデルは？
   - 応答速度の目安（モデルごとに何秒程度かかるか）

3. **Gemini API（クラウド）と Ollama（ローカル）のハイブリッド構成**
   - ネット接続あり → Gemini API、なし → Ollama に自動切り替えする実装パターン

---

## 質問 4: タスク管理アプリとしての改善アイデア

### 現状の設計上の疑問

- `inbox.txt` はシンプルなテキストファイルだが、将来的に SQLite などに移行すべきか？
  それともテキストファイルのまま（UNIX 哲学）の方が良いか？
- タスクに「優先度」「期限」「プロジェクト」を付けたい場合、
  どんなデータ形式・コマンド設計が良いか？

### 聞きたいこと

1. **2025年時点での CLI タスク管理ツールのトレンド**
   - `todo.txt` フォーマット、Taskwarrior、org-mode など既存の標準との互換性は考慮すべきか？
   - Python 製の参考になる OSS タスク CLI ツールはあるか？

2. **「爆速キャプチャ → AI 整理」の UX 改善アイデア**
   - `add` コマンドをさらに速くする方法（起動時間の短縮など）
   - AI 整理の結果を見やすくする出力形式（ターミナル表示・ファイル保存以外）
   - スマートフォンとの連携（iCloud / OneDrive 共有など）で
     モバイルからもタスク追加できる仕組みのアイデア

3. **セキュリティとプライバシー**
   - `inbox.txt` に個人情報を含むタスクを書いた場合、Gemini API に送信することの
     プライバシーリスクをどう評価すべきか？
   - ローカル処理（Ollama）への移行を勧めるケースは？

---

## 出力形式のお願い

- 質問ごとに「結論（1〜2文）」→「詳細」の順で答えてください
- コードサンプルは Python で、コピペしてすぐ動く形でお願いします
- 「2026年3月時点の情報」として回答し、不確かな情報には明記してください
