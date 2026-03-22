# qcatch UI 改善 フォローアップ — Gemini Q&A（2026-03-20）

> 前回の回答を受けて実装を進める前に確認したい技術的な疑問。
> 前回提案: tkinter QuickAddWindow（ループ入力）・DashboardWindow（タブUI）・sv-ttk・@タグ記法

---

## プロンプト

前回いただいた提案（QuickAddWindow・DashboardWindow・sv-ttk）を実装する前に、
技術的な確認事項が4点あります。

### 前提（再共有）
- Python 3.11 / Windows 11 / PyInstaller で単一 `.exe` にビルド
- 現在 `pyinstaller --onefile --noconsole qcatch.py` でビルド中
- `tkinter` は Python 標準ライブラリのため追加依存なし

---

### 質問 1: `--noconsole` ビルドと `print()` の問題

`--noconsole` オプションを使うと `sys.stdout` が消え、`print()` の出力が完全に失われます。
現在 `cmd_add()` は `print(f"✓ {entry}")` でフィードバックを返していますが、
GUI モード（QuickAddWindow）でこのフィードバックをユーザーに見せる方法を教えてください。

**候補として考えているもの:**
- QuickAddWindow のステータスラベルに表示（既存の `status_var`）
- Windows トースト通知で別途通知（`win11toast` または `winsound`）
- ログファイルに書き出す

どれが最もシンプルかつ確実か、推奨実装を示してください。

---

### 質問 2: マルチライン入力の扱い方

QuickAddWindow で `Shift+Enter` による複数行入力を許可した場合、
送信時に以下のどちらの挙動が適切でしょうか？

**A) 1タスクとして保存（複数行を1エントリに）**
```
[2026-03-20 10:00] 会議の準備
スライド作成・資料印刷・アジェンダ確認
```

**B) 行ごとに分割して複数タスクとして保存**
```
[2026-03-20 10:00] 会議の準備
[2026-03-20 10:00] スライド作成・資料印刷
[2026-03-20 10:00] アジェンダ確認
```

UX・AI分類精度・後工程（sort コマンド）への影響を踏まえて推奨を教えてください。
また、どちらの場合も `inbox.txt` の既存フォーマット（`[YYYY-MM-DD HH:MM] テキスト`）と
互換性を保てるか確認してください。

---

### 質問 3: `sv-ttk` の PyInstaller 対応

`sv-ttk` を PyInstaller の `--onefile` ビルドに含める際の注意点を教えてください。

**具体的に確認したいこと:**
- テーマのリソースファイル（画像・TCL ファイル等）は自動で含まれますか？
  それとも `--add-data` で明示指定が必要ですか？
- `sv-ttk` が見つからない環境（`ImportError`）でも起動できるよう、
  以下のようなフォールバックを書けば十分ですか？

```python
try:
    import sv_ttk
    sv_ttk.set_theme("dark")
except ImportError:
    pass  # 標準テーマのまま続行
```

- `--onefile` と `sv-ttk` の組み合わせで既知の問題はありますか？

---

### 質問 4: Dashboard の編集機能スコープ

DashboardWindow の Inbox タブで、どこまでの編集機能を実装すべきか判断したいです。

**実装コストと UX のトレードオフを踏まえて以下を教えてください:**

1. **削除のみ（`Delete` キー）** — 最小実装。誤削除のリスクはどう防ぐか（確認ダイアログ？Undo？）
2. **インライン編集（ダブルクリックでテキスト変更）** — `Listbox` では難しい。
   `ttk.Treeview` や `Entry` ウィジェットへの切り替えが必要か？
3. **sorted_tasks.md タブ** — リードオンリーで十分か、それとも手動編集できると
   どんなユースケースで役立つか？

実装が最もシンプルで実用的な構成を推奨してください。

---

各質問について「結論（1〜2文）→ 実装コード断片」の形式で回答してください。

---

## 回答

### 質問 1: `--noconsole` ビルドと `print()` の問題

**結論:** GUI モードでは **QuickAddWindow のステータスラベル（`status_var`）の更新** が最もシンプルでユーザー体験が良く確実。デバッグ・エラー追跡用として `logging` モジュールでファイル出力を併用する。

```python
import logging
import tkinter as tk

logging.basicConfig(filename='data/qcatch.log', level=logging.INFO,
                    format='%(asctime)s - %(message)s')

class QuickAddWindow(tk.Tk):
    def show_feedback(self, message):
        """成功メッセージを緑色で表示し、3秒後に元に戻す"""
        self.status_var.set(f"✓ {message}")
        self.status_label.config(foreground="green")
        logging.info(f"Task added: {message}")
        self.after(3000, self.reset_status)

    def reset_status(self):
        self.status_label.config(foreground="gray")
        self.status_var.set(f"Inbox: {self.count_inbox()} 件")
```

---

### 質問 2: マルチライン入力の扱い方

**結論:** **B) 行ごとに分割して複数タスクとして保存** を強く推奨。`inbox.txt` の1行1タスク形式と互換性が完全に保たれ、AI 分類精度も高い。

```python
    def handle_enter(self, event):
        raw_text = self.text_area.get("1.0", tk.END).strip()
        if not raw_text:
            self.destroy()
            return "break"

        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M]")
        tasks = [line.strip() for line in raw_text.split('\n') if line.strip()]

        with open(INBOX_FILE, "a", encoding="utf-8") as f:
            for task in tasks:
                f.write(f"{timestamp} {task}\n")

        self.text_area.delete("1.0", tk.END)
        self.show_feedback(f"{len(tasks)}件追加 ({tasks[0][:10]}...)")
        return "break"
```

---

### 質問 3: `sv-ttk` の PyInstaller 対応

**結論:** テーマリソース（TCL ファイル等）は自動で含まれないため、`--collect-data sv_ttk` の明示指定が必要。`try-except` フォールバックは完璧な実装で、そのまま使える。

```powershell
# ビルドコマンドに --collect-data を追加
pyinstaller --onefile --noconsole --collect-data sv_ttk qcatch.py
```

```python
def apply_theme():
    try:
        import sv_ttk
        sv_ttk.set_theme("dark")
    except ImportError:
        logging.warning("sv_ttk is not installed. Using default theme.")
    except tk.TclError as e:
        # PyInstaller でリソースが読み込めなかった場合のフェイルセーフ
        logging.warning(f"Failed to load sv_ttk theme data: {e}")
```

---

### 質問 4: Dashboard の編集機能スコープ

**結論:** Inbox タブは **「削除のみ（`Delete` キー + 確認ダイアログ）」**、sorted_tasks.md タブは **「リードオンリー」** に留める。編集が必要な場合はテキストエディタで直接 `.md` ファイルを開く（UNIX哲学）のが理にかなっている。

```python
from tkinter import messagebox

    def delete_selected_task(self, event):
        selection = self.listbox.curselection()
        if not selection: return

        index = selection[0]
        task_text = self.listbox.get(index)

        if messagebox.askyesno("削除の確認", f"以下のタスクを削除しますか？\n\n{task_text}"):
            self.listbox.delete(index)

            tasks = self.listbox.get(0, tk.END)
            with open(INBOX_FILE, "w", encoding="utf-8") as f:
                for t in tasks:
                    f.write(t + "\n")

            logging.info(f"Task deleted: {task_text}")
```
