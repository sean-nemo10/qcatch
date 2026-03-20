# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## このディレクトリについて

`C:\dev\ZzzMemo` — qcatch CLI タスク管理アプリ。
git root は `C:\dev`（flashcard アプリ `remember/` も同居）。

---

## ファイル構成

| パス | 役割 |
|---|---|
| `qcatch.py` | メインスクリプト（全コマンド実装） |
| `build.ps1` | exe ビルド + Windows Search ショートカット更新 |
| `data/inbox.txt` | 未整理タスク（add で追記） |
| `data/sorted_tasks.md` | AI 分類済みタスク |
| `data/archive.txt` | sort 済みの inbox バックアップ |
| `docs/generate_docs.py` | PPTX ガイド生成（`python docs/generate_docs.py`） |
| `prompts/gemini_questions.md` | 技術調査 Q&A（Windows Search / API 課金） |
| `prompts/gemini_improvement.md` | 改善案調査 Q&A（SDK / toast / Ollama） |

---

## コマンド

```bash
python qcatch.py toast                  # トースト通知から入力（最速・Windows Search 用）
python qcatch.py add "タスクのテキスト"  # 即追記（API通信なし）
python qcatch.py list                   # inbox 確認
python qcatch.py sort                   # Gemini 2.0 Flash で分類（GEMINI_API_KEY 必要）
python qcatch.py sort --local           # Ollama（ローカル）で分類
python qcatch.py sort --export          # API 不使用・プロンプトをファイル出力
python qcatch.py prompt                 # ターミナル対話入力（toast の代替）
python docs/generate_docs.py           # PPTX を再生成
.\build.ps1                            # exe ビルド + Windows Search 登録（PowerShell）
```

---

## アーキテクチャ上の重要な判断

### なぜ `qcatch_launcher.py` を削除したか
- 旧 `google-generativeai` は TensorFlow まで引き込み PyInstaller が失敗
- 新 `google-genai`（v1.x）は httpx/pydantic/requests のみ → TensorFlow 依存なし
- 結果: `qcatch.py` 単体でビルド可能（39MB exe）
- `qcatch_launcher.py`（6MB exe）は不要になり削除した

### sort コマンドのバックエンド優先順位
1. `--export` フラグ → プロンプトをファイル出力（最優先）
2. `--local` フラグ → Ollama（完全ローカル）
3. `qcatch_config.json` の `sort_backend` 設定値
4. auto（`sort_backend=auto`）: Ollama 起動中なら Ollama → `GEMINI_API_KEY` → `ANTHROPIC_API_KEY`

設定例: `python qcatch.py config set sort_backend ollama`

### Windows Search への登録方法
`.lnk` ショートカットの TargetPath に `python.exe` を指定しても Windows Search に出ない（仕様）。
`qcatch.exe` を直接 TargetPath にすることで「アプリ」として認識される。

### toast コマンドの動作
`win11toast` ライブラリで Windows 11 のトースト通知にテキスト入力フィールドを表示。
`win11toast` が使えない環境では自動的に `prompt`（ターミナル対話）にフォールバック。

---

## 設計上の制約

- **`add` コマンドは API 通信・重い処理を追加しないこと**（待ち時間ゼロが絶対条件）
- **`data/` のファイルは上書き削除しないこと**（学習データが入っている）
- **`sort` は `inbox.txt` をクリアする**（実行前に `list` で確認）
- **データはテキストファイルのまま維持**（他ツールとの連携・可読性のため SQLite 化しない）
