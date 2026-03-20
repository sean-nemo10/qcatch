# qcatch UI 改善案 — Gemini Q&A（2026-03-20）

> 回答を受けて実装済みの内容: （未着手）

---

## プロンプト

# qcatch アプリの改善案を検討してください

## アプリの概要
`qcatch.py` — Python 製の Windows 向けタスクキャッチ CLI（単一ファイル、PyInstaller で .exe にビルド）

### 現在のコマンド
| コマンド | 説明 |
|---|---|
| `add "テキスト"` | inbox.txt に即追記（API 通信なし・ゼロレイテンシ） |
| `toast` | win11toast でトースト通知に入力フィールドを表示 |
| `prompt` | ターミナルで対話入力 |
| `list` | inbox.txt の内容を表示して終了 |
| `sort` | Gemini/Ollama/Claude で AI 分類 → sorted_tasks.md に保存 |
| `config` | 設定表示・変更 |

### データ構造
- `data/inbox.txt` — 未分類タスク（`[YYYY-MM-DD HH:MM] テキスト` 形式）
- `data/sorted_tasks.md` — AI 分類済みタスク（カテゴリ別マークダウン）
- `data/archive.txt` — sort 済み inbox のバックアップ
- SQLite 化はしない（他ツール連携・可読性のためテキストファイル維持）

### 技術制約
- `add` コマンドには API 通信・重い処理を追加しない（ゼロレイテンシ必須）
- データファイルは上書き削除しない
- 単一ファイル（`qcatch.py`）の構造を維持することが望ましい
- Windows 11 / Python 3.11+ / PyInstaller ビルド対応

### 現在の問題点
1. **入力 UI**: win11toast は1行テキストフィールドのみ。Windows Search から起動すると
   即 TIMED_OUT になりフォールバックの `tkinter.simpledialog.askstring` が表示される
   が、ウィンドウが非常に小さく複数行入力に向かない
2. **アプリが都度終了**: タスクを複数追加したい場合、毎回起動する必要がある
3. **タスク閲覧**: `list` コマンドは内容を表示して即終了。
   アプリ内で inbox と sorted_tasks.md を両方閲覧・管理したい

---

## 相談したい改善点

### 1. 複数タスクを連続追加できる「ループモード」
現状は1タスク追加してアプリが終了する。
Windows Search から呼び出した後、そのまま複数のタスクを追加し続けられるモードが欲しい。

**検討してほしいこと:**
- tkinter で「追加→フィールドクリア→次の入力」をループするダイアログの設計
- 「空送信 or キャンセルで終了」というUXが適切か
- ループ中に追加済み件数（`inbox: N 件`）をフィードバック表示する方法

### 2. アプリ内タスク閲覧・管理ビュー
inbox と sorted_tasks.md をアプリ内で閲覧できるようにしたい。

**検討してほしいこと:**
- tkinter での簡易ビュー（ScrolledText など）の設計案
- inbox のタスクを選択して削除・編集できると理想的
- sorted_tasks.md はカテゴリ別に表示できると良い
- 「閲覧ビュー」と「タスク追加」を同一ウィンドウで切り替えられるか（タブUI等）

### 3. 入力 UI の改善（win11toast の代替・補完）
win11toast は軽量で良いが、Windows Search 起動時に機能しないことが多い。
フォールバックの tkinter ダイアログをより使いやすくする方法を検討したい。

**検討してほしいこと:**
- テキストエリア（複数行入力）＋送信ボタンの tkinter ウィンドウ設計
- ウィンドウを最前面・中央に表示し、起動直後にフォーカスを当てる方法
- ウィンドウサイズ・フォントサイズをユーザーが設定できる仕組み
- `win11toast` を完全に廃止して tkinter に一本化するメリット・デメリット

### 4. その他の改善案（自由に提案してください）
上記以外で、このアプリの使い勝手・品質を上げられる改善点があれば提案してください。
ただし以下は**スコープ外**とします:
- データの SQLite 化・DB 移行
- Web UI / Electron への移行
- クラウド同期機能
- 複数ファイル分割や大規模リファクタリング

---

各改善点について、**具体的な実装方針**（使うライブラリ、関数・クラスの設計、コード断片など）を示してください。

---

## 回答

現状の課題と技術的な制約（テキストベース・単一ファイル・高速起動）を深く理解しました。`win11toast` はネイティブで美しい反面、Windows Search のような非同期の呼び出し元からだと COM サーバーの初期化に失敗したりタイムアウトを起こしやすいという弱点があります。

ご提案の通り、**軽量かつ確実な `tkinter` にUIを一本化し、ループ機能や閲覧タブを備えた「統合ダッシュボード」へと進化させる**のが、2026年時点での最も堅牢な解決策です。

以下に各改善点の具体的な実装方針とコード断片を提案します。

---

### 1 & 3. 入力 UI の改善 ＋ ループモード（Quick Add モード）

**結論:** `win11toast` と `simpledialog` を廃止し、専用の `tkinter` ウィンドウ（マルチライン対応、最前面表示、ループ入力可能）を自作して一本化します。

**詳細:**
* **UI設計:** `tkinter.Text`（複数行入力）と送信ボタンを配置。`Enter` キーで送信、`Shift + Enter` で改行というモダンなチャットUIの挙動を実装します。
* **ループ UX:** 送信後、ウィンドウは閉じずにテキストエリアをクリアし、上部に `「inbox: N 件 (最新: 牛乳を買う)」` のようにステータスを一時表示します。終了は `Esc` キーまたは空送信で行います。
* **最前面・中央表示:** `root.attributes('-topmost', True)` で最前面に固定し、起動直後にフォーカスを奪うよう `root.focus_force()` を呼び出します。

**【実装コード断片: Quick Add UI】**
```python
import tkinter as tk
from tkinter import ttk
import os
from datetime import datetime

INBOX_FILE = "data/inbox.txt"

class QuickAddWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("qcatch - Quick Add")
        self.geometry("400x150")
        self.eval('tk::PlaceWindow . center') # 画面中央に配置
        self.attributes('-topmost', True)     # 最前面表示
        self.focus_force()

        # UI要素の構築
        self.status_var = tk.StringVar(value=f"Inbox: {self.count_inbox()} 件")
        ttk.Label(self, textvariable=self.status_var, foreground="gray").pack(pady=(5, 0))

        self.text_area = tk.Text(self, height=3, font=("Meiryo", 11))
        self.text_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.text_area.focus_set()

        # キーバインド
        self.text_area.bind("<Return>", self.handle_enter)
        self.text_area.bind("<Shift-Return>", self.insert_newline)
        self.bind("<Escape>", lambda e: self.destroy())

    def count_inbox(self):
        if not os.path.exists(INBOX_FILE): return 0
        with open(INBOX_FILE, "r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())

    def handle_enter(self, event):
        text = self.text_area.get("1.0", tk.END).strip()
        if not text:
            self.destroy() # 空送信で終了
            return "break"

        # 保存処理
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M]")
        os.makedirs("data", exist_ok=True)
        with open(INBOX_FILE, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} {text}\n")

        # UIリセット（ループモード）
        self.text_area.delete("1.0", tk.END)
        self.status_var.set(f"Inbox: {self.count_inbox()} 件 (追加: {text[:10]}...)")
        return "break" # デフォルトの改行を防ぐ

    def insert_newline(self, event):
        self.text_area.insert(tk.INSERT, "\n")
        return "break"
```

---

### 2. アプリ内タスク閲覧・管理ビュー（ダッシュボード）

**結論:** `tkinter.ttk.Notebook`（タブUI）を使用し、「Inbox管理」タブと「AI分類済み」タブを切り替えられる統合ビューを作成します。

**詳細:**
* **Inbox タブ:** `tkinter.Listbox` を使用。各行を選択して `Delete` キーで削除できる機能を付けます（ファイルの該当行を再書き込みします）。
* **分類済み タブ:** Markdownテキストを表示するため `tkinter.scrolledtext.ScrolledText` を使用します。こちらはリードオンリー（または簡易編集機能つき）にします。
* これらは `qcatch dashboard` などの新しいコマンドで呼び出すように設計します。

**【実装コード断片: ダッシュボード UI】**
```python
import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext
import os

class DashboardWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("qcatch - Dashboard")
        self.geometry("600x400")

        # タブの作成
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Inbox タブ ---
        self.tab_inbox = ttk.Frame(notebook)
        notebook.add(self.tab_inbox, text="Inbox (未分類)")

        self.listbox = tk.Listbox(self.tab_inbox, font=("Meiryo", 10))
        self.listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self.listbox.bind("<Delete>", self.delete_selected_task)

        self.load_inbox()

        # --- Sorted タブ ---
        self.tab_sorted = ttk.Frame(notebook)
        notebook.add(self.tab_sorted, text="分類済み (sorted_tasks.md)")

        self.text_sorted = scrolledtext.ScrolledText(self.tab_sorted, font=("Meiryo", 10), state=tk.DISABLED)
        self.text_sorted.pack(fill=tk.BOTH, expand=True)
        self.load_sorted()

    def load_inbox(self):
        self.listbox.delete(0, tk.END)
        if os.path.exists(INBOX_FILE):
            with open(INBOX_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip(): self.listbox.insert(tk.END, line.strip())

    def delete_selected_task(self, event):
        selection = self.listbox.curselection()
        if not selection: return

        index = selection[0]
        self.listbox.delete(index)

        tasks = self.listbox.get(0, tk.END)
        with open(INBOX_FILE, "w", encoding="utf-8") as f:
            for t in tasks: f.write(t + "\n")

    def load_sorted(self):
        pass # ファイル読み込みと text_sorted への insert を実装
```

---

### 4. その他の改善案

#### A. `sv-ttk` (Sun Valley Theme) の導入による UI のモダン化
標準の `tkinter` は Windows 11 のデザインから浮いてしまいます。`sv-ttk` を追加するだけで、完全にネイティブな Windows 11 風のダーク/ライトテーマが適用されます。PyInstaller のビルドにも含められます。
* `pip install sv-ttk`
* コードの最後に `import sv_ttk; sv_ttk.set_theme("dark")` を足すだけ。

#### B. タスク入力時のカテゴリ手動強制タグ（@記法）
`qcatch add "牛乳を買う @買い物"` のように `@カテゴリ名` を検知し、AI を通さず直接 `sorted_tasks.md` の該当セクションに書き込む仕組み。

#### C. パス解決の堅牢化（PyInstaller 対策）
※現在の `qcatch.py` はすでに `sys.frozen` を使った `BASE_DIR` 解決を実装済みのため、この点は対応不要。

---

**次の一手として:**
まずは既存の `win11toast` と `prompt` のコードを削除し、提案した **「Quick Add UI（ループ対応）」** のクラスを `qcatch.py` に組み込んでみるのはいかがでしょうか？ 必要であれば、既存の `argparse` とどう結合させるかの全体コードもご提示できます。
