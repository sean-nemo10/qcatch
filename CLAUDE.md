# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## このディレクトリについて

`C:\dev\ZzzMemo` には 2 つのプロジェクトが同居している:
- **qcatch** (メイン): 爆速タスクキャッチ & AI 自動整理 CLI（このディレクトリ）
- **flashcard** (参照用): `C:\dev\remember\` にある間隔反復学習アプリ（git root は C:\dev）

---

## qcatch ファイル構成

| パス | 役割 |
|---|---|
| `qcatch.py` | メインスクリプト（add / list / sort / prompt） |
| `qcatch_add.bat` | ダブルクリック / Win+R 用ランチャー |
| `setup.ps1` | Windows ランチャー一括セットアップ |
| `data/inbox.txt` | 未整理タスク（add で追記） |
| `data/sorted_tasks.md` | AI 分類済みタスク |
| `data/archive.txt` | sort 済みの inbox バックアップ |
| `data/sort_prompt.txt` | `sort --export` で生成されるプロンプト |
| `docs/generate_docs.py` | PPTX ガイド生成（`python docs/generate_docs.py`） |
| `docs/qcatch_guide.pptx` | 生成済みガイド |
| `docs/generate_docs_flashcard_ref.py` | flashcard 用 PPTX（参考用、編集不要） |
| `prompts/gemini_questions.md` | 未解決の疑問点（Windows Search / API キーなど） |
| `windows_setup.md` | Windows Search 連携の技術的注意点（参考資料） |

---

## コマンド

```bash
python qcatch.py add "タスクのテキスト"   # 即追記（API通信なし）
python qcatch.py list                      # inbox 確認
python qcatch.py sort                      # Claude API で分類（ANTHROPIC_API_KEY 必要）
python qcatch.py sort --export             # API 不使用・プロンプトをファイルに書き出し
python qcatch.py prompt                    # 対話入力モード
python docs/generate_docs.py              # PPTX を再生成
```

---

## 重要な設計上の制約

- **`add` コマンドは API 通信禁止**: 待ち時間ゼロが必須。ファイル追記のみ。
- **`data/` のファイルは上書き削除しない**: inbox.txt にはタスクデータが入っている。
  スキーマ変更が必要な場合は既存データへの影響を確認してから行う。
- **`sort` は `data/inbox.txt` をクリアする**: 実行前に必ず `list` で内容を確認すること。

---

## 未解決の問題（`prompts/gemini_questions.md` 参照）

1. **Windows Search にショートカットが表示されない**: `setup.ps1` を実行したが
   検索結果に出てこない。質問ファイルに詳細あり。
2. **API キーなし**: ユーザーは Claude Code Pro サブスクだが Anthropic API キーは未取得。
   現状の回避策: `sort --export` でプロンプトを書き出して Claude.ai に手動貼り付け。
