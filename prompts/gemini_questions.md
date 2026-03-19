# Gemini への質問プロンプト & 回答まとめ

---

## 質問 1: Windows 11 で python.exe ターゲットのショートカットが Windows Search に表示されない

### 回答（2026-03-19）

**原因:** Windows Search の仕様（ヒューリスティックによるフィルタリング）。
`python.exe` / `cmd.exe` などの「汎用的なホスト実行ファイル」をターゲットにした
ショートカットはスパム防止・重複排除のために「アプリ」として認識されない。
引数が違っていても `python.exe` をターゲットにした時点で弾かれる。

**解決策（確実な順）:**

1. **PyInstaller で `.exe` 化 ★推奨**
   - `pyinstaller --onefile qcatch.py` で `qcatch.exe` を生成
   - `%APPDATA%\Microsoft\Windows\Start Menu\Programs\` にショートカットを配置
   - Windows Search が独立したアプリとして認識する

2. **AppUserModelId を付与する（ハック）**
   - PowerShell の WScript.Shell からは難しい（C# や専用モジュールが必要）
   - Windows Update で挙動が変わるリスクあり → 採用しない

---

## 質問 2: Claude Code Pro ユーザーが Claude API を利用する方法

### 回答（2026-03-19）

**重要な事実:** Claude Code Pro サブスクリプションと Anthropic API は**完全に別契約**。
API 利用権限は一切含まれない。API を使うには Anthropic Console で従量課金登録が必要。

**代替案（採用予定）:**

| 方法 | コスト | オフライン | 難易度 |
|---|---|---|---|
| Gemini API (Gemini 1.5 Flash) | **無料枠あり**（15RPM / 1500req/日） | 不可 | 低 |
| Anthropic API (Claude Haiku) | 有料（最低5ドル事前チャージ） | 不可 | 低 |
| Ollama (ローカル LLM) | 無料 | **可** | 中（GPU/メモリ消費） |

**Gemini API のサンプルコード:**

```python
import google.generativeai as genai
import os, json

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

def sort_tasks(inbox_text):
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""
    以下のタスク一覧を「仕事」「プライベート」「買い物」などのカテゴリに分類し、
    JSON形式で出力してください。
    タスク一覧:
    {inbox_text}
    """
    response = model.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    return json.loads(response.text)
```

API キーは Google AI Studio (aistudio.google.com) で無料発行可能。

---

## 質問 3: Python CLI を Windows Search に登録するベストプラクティス

### 回答（2026-03-19）

**結論: PyInstaller による `.exe` 化が最も確実（2026年現在）**

```bash
pyinstaller --onefile qcatch.py
# → dist/qcatch.exe が生成される
```

- Windows Search が独立したアプリとして認識・インデックスする
- アイコン設定も可能（`--icon=icon.ico`）
- Windows Terminal プロファイルへの追加は Windows Search 連携には不向き

---

## 次のアクション候補

1. **PyInstaller で `qcatch.exe` を作成** → Windows Search 問題を解決
2. **Gemini API で `sort` コマンドを実装** → API キー不要で自動分類を実現
