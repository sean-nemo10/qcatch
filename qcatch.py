#!/usr/bin/env python3
"""qcatch.py - 爆速タスクキャッチ & AI自動整理 CLI"""

import argparse
import io
import json
import logging
import os
import re
import sys
import threading
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Literal

import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

if sys.platform == "win32":
    os.system("")  # ANSI 有効化
    if sys.stdout is not None:
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )
    if sys.stdin is not None:
        sys.stdin = io.TextIOWrapper(
            sys.stdin.buffer, encoding="utf-8", errors="replace"
        )

# PyInstaller .exe 実行時は sys.executable（.exe パス）を基準にする
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

DATA_DIR = BASE_DIR / "data"
INBOX_FILE = DATA_DIR / "inbox.txt"
SORTED_FILE = DATA_DIR / "sorted_tasks.md"
ARCHIVE_FILE = DATA_DIR / "archive.txt"
CONFIG_FILE = BASE_DIR / "qcatch_config.json"
FEW_SHOT_FILE = DATA_DIR / "few_shot_examples.json"

DATA_DIR.mkdir(exist_ok=True)

CATEGORIES = ["仕事", "プライベート", "買い物", "学習", "その他"]

# ── 設定ファイル ──────────────────────────────────────────────────────────────
_DEFAULT_CONFIG = {
    "sort_backend": "auto",  # "auto" | "ollama" | "gemini" | "anthropic" | "export"
    "ollama_model": "phi4",  # ollama pull phi4 で取得
    "ollama_host": "http://localhost:11434",
}


def _load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return {**_DEFAULT_CONFIG, **data}
        except Exception:
            pass
    return dict(_DEFAULT_CONFIG)


def _save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── ANSI カラー ──────────────────────────────────────────────────────────────
class C:
    RST = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GRN = "\033[32m"
    YLW = "\033[33m"
    CYN = "\033[36m"
    WHT = "\033[37m"
    MGT = "\033[35m"


# ── Pydantic モデル（Gemini 構造化出力用）───────────────────────────────────
try:
    from pydantic import BaseModel

    class TaskItem(BaseModel):
        text: str
        timestamp: str
        category: Literal["仕事", "プライベート", "買い物", "学習", "その他"]

    class SortedTasks(BaseModel):
        tasks: list[TaskItem]

    PYDANTIC_OK = True
except ImportError:
    PYDANTIC_OK = False


# ── ログ設定 ─────────────────────────────────────────────────────────────────
def _setup_logging() -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(
            filename=str(DATA_DIR / "qcatch.log"),
            level=logging.INFO,
            encoding="utf-8",
            format="%(asctime)s %(message)s",
        )


# ── テーマ ────────────────────────────────────────────────────────────────────
def _apply_theme() -> None:
    try:
        import sv_ttk

        sv_ttk.set_theme("dark")
    except ImportError:
        pass
    except Exception as e:
        logging.warning(f"sv_ttk theme failed: {e}")


# ── few-shot 学習 ────────────────────────────────────────────────────────────
def _update_few_shot_examples() -> int:
    """sorted_tasks.md から過去の分類実績を抽出して few_shot_examples.json に保存。"""
    if not SORTED_FILE.exists():
        return 0
    by_cat: dict[str, list[str]] = defaultdict(list)
    current_cat = None
    for line in SORTED_FILE.read_text(encoding="utf-8").splitlines():
        for cat in CATEGORIES:
            if line.strip() == f"## {cat}":
                current_cat = cat
                break
        else:
            if current_cat and line.startswith("- "):
                text = re.sub(
                    r"^- \[\d{4}-\d{2}-\d{2} \d{2}:\d{2}\] ", "", line
                ).strip()
                if text and text not in by_cat[current_cat]:
                    by_cat[current_cat].append(text)
    examples = {cat: items[-3:] for cat, items in by_cat.items() if items}
    FEW_SHOT_FILE.write_text(
        json.dumps(examples, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return sum(len(v) for v in examples.values())


def _get_few_shot_text() -> str:
    """保存済みの分類実績をプロンプト用テキストに変換。"""
    if not FEW_SHOT_FILE.exists():
        return ""
    try:
        examples = json.loads(FEW_SHOT_FILE.read_text(encoding="utf-8"))
        lines = ["【過去の分類実績（参考）】"]
        for cat, items in examples.items():
            for item in items:
                lines.append(f"  「{item}」→ {cat}")
        return "\n".join(lines) + "\n\n"
    except Exception:
        return ""


# ── 統合アプリ ────────────────────────────────────────────────────────────────
class QcatchApp(tk.Tk):
    """Quick Add + Inbox 管理 + Sort を統合したメインウィンドウ。"""

    def __init__(self):
        _setup_logging()
        super().__init__()
        self.title("qcatch")
        self.geometry("500x540")
        self.eval("tk::PlaceWindow . center")
        self.attributes("-topmost", True)
        self.resizable(True, True)

        # ── Quick Add エリア ───────────────────────────────────────────────
        qa_frame = ttk.LabelFrame(self, text=" Quick Add ")
        qa_frame.pack(fill=tk.X, padx=8, pady=(8, 4))

        self.status_var = tk.StringVar(value=f"Inbox: {self._count_inbox()} 件")
        self.status_label = ttk.Label(
            qa_frame, textvariable=self.status_var, foreground="gray"
        )
        self.status_label.pack(anchor=tk.W, padx=6, pady=(4, 0))

        self.text_area = tk.Text(qa_frame, height=3, font=("Meiryo", 11), wrap=tk.WORD)
        self.text_area.pack(fill=tk.X, padx=6, pady=(2, 6))
        self.text_area.focus_set()
        self.text_area.bind("<Return>", self._handle_enter)
        self.text_area.bind("<Shift-Return>", self._insert_newline)
        self.bind("<Escape>", lambda e: self.destroy())

        # ── Notebook (Inbox / 分類済み) ────────────────────────────────────
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        tab_inbox = ttk.Frame(self.notebook)
        self.notebook.add(tab_inbox, text="Inbox")
        self.listbox = tk.Listbox(tab_inbox, font=("Meiryo", 10), selectmode=tk.SINGLE)
        sb = ttk.Scrollbar(tab_inbox, orient=tk.VERTICAL, command=self.listbox.yview)
        self.listbox.config(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.pack(fill=tk.BOTH, expand=True)
        self.listbox.bind("<Delete>", self._delete_selected)
        btn_row = ttk.Frame(tab_inbox)
        btn_row.pack(fill=tk.X, padx=4, pady=(2, 2))
        ttk.Button(btn_row, text="Sort（AI 分類）", command=self._run_sort).pack(
            side=tk.LEFT
        )
        ttk.Label(btn_row, text="Delete: 削除", foreground="gray").pack(side=tk.RIGHT)

        tab_sorted = ttk.Frame(self.notebook)
        self.notebook.add(tab_sorted, text="分類済み")
        self.sorted_listbox = tk.Listbox(
            tab_sorted, font=("Meiryo", 10), selectmode=tk.SINGLE
        )
        sb2 = ttk.Scrollbar(
            tab_sorted, orient=tk.VERTICAL, command=self.sorted_listbox.yview
        )
        self.sorted_listbox.config(yscrollcommand=sb2.set)
        sb2.pack(side=tk.RIGHT, fill=tk.Y)
        self.sorted_listbox.pack(fill=tk.BOTH, expand=True)
        self.sorted_task_map: list[tuple[bool, str, str]] = []
        btn_row2 = ttk.Frame(tab_sorted)
        btn_row2.pack(fill=tk.X, padx=4, pady=(2, 2))
        ttk.Button(btn_row2, text="✓ 完了", command=self._complete_sorted_task).pack(
            side=tk.LEFT
        )

        # ── 下部バー ───────────────────────────────────────────────────────
        bottom = ttk.Frame(self)
        bottom.pack(fill=tk.X, padx=8, pady=(0, 6))
        self.sort_status = tk.StringVar(value="")
        ttk.Label(bottom, textvariable=self.sort_status, foreground="gray").pack(
            side=tk.LEFT
        )
        ttk.Button(
            bottom, text="分類を改善", command=self._improve_classification
        ).pack(side=tk.RIGHT, padx=(4, 0))
        self._load_inbox()
        self._load_sorted()

    # ── Quick Add ─────────────────────────────────────────────────────────
    def _count_inbox(self) -> int:
        if not INBOX_FILE.exists():
            return 0
        return sum(
            1
            for ln in INBOX_FILE.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        )

    def _handle_enter(self, event) -> str:
        raw = self.text_area.get("1.0", tk.END).strip()
        if not raw:
            self.destroy()
            return "break"
        tasks = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        for t in tasks:
            cmd_add(t)
        logging.info(f"GUI: Added {len(tasks)} task(s): {tasks[0][:40]}")
        self.text_area.delete("1.0", tk.END)
        preview = tasks[0][:12] + ("..." if len(tasks[0]) > 12 else "")
        msg = (
            f"{len(tasks)} 件追加（{preview}）"
            if len(tasks) > 1
            else f"追加: {preview}"
        )
        self._show_feedback(msg)
        self._load_inbox()
        return "break"

    def _insert_newline(self, event) -> str:
        self.text_area.insert(tk.INSERT, "\n")
        return "break"

    def _show_feedback(self, message: str) -> None:
        self.status_var.set(f"✓ {message}")
        self.status_label.config(foreground="green")
        self.after(3000, self._reset_status)

    def _reset_status(self) -> None:
        self.status_label.config(foreground="gray")
        self.status_var.set(f"Inbox: {self._count_inbox()} 件")

    # ── Inbox ─────────────────────────────────────────────────────────────
    def _load_inbox(self) -> None:
        self.listbox.delete(0, tk.END)
        if INBOX_FILE.exists():
            for ln in INBOX_FILE.read_text(encoding="utf-8").splitlines():
                if ln.strip():
                    self.listbox.insert(tk.END, ln.strip())
        self.notebook.tab(0, text=f"Inbox ({self.listbox.size()} 件)")

    def _complete_sorted_task(self) -> None:
        sel = self.sorted_listbox.curselection()
        if not sel:
            return
        is_task, _cat, task_text = self.sorted_task_map[sel[0]]
        if not is_task:
            return
        if SORTED_FILE.exists():
            lines = SORTED_FILE.read_text(encoding="utf-8").splitlines(keepends=True)
            lines = [l for l in lines if l.rstrip() != f"- {task_text}"]
            SORTED_FILE.write_text("".join(lines), encoding="utf-8")
        done_file = DATA_DIR / "done.txt"
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M]")
        with done_file.open("a", encoding="utf-8") as f:
            f.write(f"{timestamp} {task_text}\n")
        logging.info(f"Task completed: {task_text}")
        self._load_sorted()

    def _delete_selected(self, event) -> None:
        sel = self.listbox.curselection()
        if not sel:
            return
        task_text = self.listbox.get(sel[0])
        if messagebox.askyesno(
            "削除の確認", f"削除しますか？\n\n{task_text}", parent=self
        ):
            self.listbox.delete(sel[0])
            tasks = self.listbox.get(0, tk.END)
            INBOX_FILE.write_text("".join(t + "\n" for t in tasks), encoding="utf-8")
            logging.info(f"Task deleted: {task_text}")
            self.notebook.tab(0, text=f"Inbox ({self.listbox.size()} 件)")

    def _load_sorted(self) -> None:
        self.sorted_listbox.delete(0, tk.END)
        self.sorted_task_map = []
        if not SORTED_FILE.exists():
            self.sorted_listbox.insert(tk.END, "(sorted_tasks.md が見つかりません)")
            self.sorted_task_map.append((False, "", ""))
            return
        # セッション区切りをまたいで全タスクをカテゴリ別に集約（重複除去）
        categories: dict[str, list[str]] = {}
        current_cat = ""
        for line in SORTED_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                current_cat = line[3:].strip()
                categories.setdefault(current_cat, [])
            elif line.startswith("- ") and current_cat:
                task = line[2:].strip()
                if task not in categories[current_cat]:
                    categories[current_cat].append(task)
        for cat, tasks in categories.items():
            self.sorted_listbox.insert(tk.END, f"■ {cat}")
            self.sorted_task_map.append((False, cat, ""))
            for task in tasks:
                self.sorted_listbox.insert(tk.END, f"  {task}")
                self.sorted_task_map.append((True, cat, task))

    # ── Sort / 学習 ───────────────────────────────────────────────────────
    def _run_sort(self) -> None:
        if (
            not INBOX_FILE.exists()
            or not INBOX_FILE.read_text(encoding="utf-8").strip()
        ):
            self.sort_status.set("inbox が空です")
            self.after(3000, lambda: self.sort_status.set(""))
            return
        self.sort_status.set("分類中...")
        threading.Thread(target=self._sort_worker, daemon=True).start()

    def _sort_worker(self) -> None:
        try:
            cmd_sort()
            self.after(0, self._on_sort_done)
        except SystemExit:
            self.after(0, lambda: self.sort_status.set("エラー（バックエンド未設定）"))
            self.after(3000, lambda: self.sort_status.set(""))

    def _on_sort_done(self) -> None:
        _update_few_shot_examples()  # 分類完了後に自動で学習データ更新
        self._load_inbox()
        self._load_sorted()
        self.sort_status.set("✓ 分類完了・学習データ更新")
        self.after(4000, lambda: self.sort_status.set(""))

    def _improve_classification(self) -> None:
        n = _update_few_shot_examples()
        if n == 0:
            self.sort_status.set("学習データなし（先に Sort を実行してください）")
        else:
            self.sort_status.set(f"✓ 学習完了（{n} 件の過去分類を記憶）")
        self.after(4000, lambda: self.sort_status.set(""))


# ── add ──────────────────────────────────────────────────────────────────────
def _add_to_sorted(text: str, category: str, timestamp: str) -> None:
    """@タグ付きタスクを sorted_tasks.md の該当セクションに直接追記。"""
    entry = f"- [{timestamp}] {text}"
    section = f"## {category}"
    content = SORTED_FILE.read_text(encoding="utf-8") if SORTED_FILE.exists() else ""
    if section in content:
        lines = content.splitlines()
        insert_idx = len(lines)
        in_section = False
        for i, line in enumerate(lines):
            if line.strip() == section:
                in_section = True
            elif in_section and line.startswith("## "):
                insert_idx = i
                break
        lines.insert(insert_idx, entry)
        SORTED_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        SORTED_FILE.write_text(
            content.rstrip() + f"\n\n{section}\n{entry}\n", encoding="utf-8"
        )


def cmd_add(text: str) -> None:
    """タスクを inbox.txt に追記。@カテゴリ タグがあれば sorted_tasks.md に直接追加。"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    tag_match = re.search(r"@(" + "|".join(CATEGORIES) + r")\s*$", text)
    if tag_match:
        category = tag_match.group(1)
        clean = text[: tag_match.start()].strip()
        _add_to_sorted(clean, category, timestamp)
        print(
            f"{C.GRN}{C.BOLD}✓{C.RST} [{timestamp}] {clean}  {C.CYN}→ {category}{C.RST}"
        )
        return
    entry = f"[{timestamp}] {text}\n"
    with open(INBOX_FILE, "a", encoding="utf-8") as f:
        f.write(entry)
    print(f"{C.GRN}{C.BOLD}✓{C.RST} {entry.strip()}")


# ── toast（Quick Add ウィンドウを起動）───────────────────────────────────────
def cmd_toast() -> None:
    """QcatchApp を起動（Quick Add + Inbox + Sort 統合）。Windows Search 起動用。"""
    app = QcatchApp()
    _apply_theme()
    app.mainloop()


# ── dashboard ─────────────────────────────────────────────────────────────────
def cmd_dashboard() -> None:
    """QcatchApp を起動して Inbox タブを表示。"""
    app = QcatchApp()
    app.notebook.select(0)
    _apply_theme()
    app.mainloop()


# ── prompt（ターミナル対話入力）──────────────────────────────────────────────
def cmd_prompt() -> None:
    """ターミナルを開いて対話入力 → add して終了。toast が使えない環境向け。"""
    print(f"\n{C.BOLD}{C.CYN}{'─' * 42}{C.RST}")
    print(f"{C.BOLD}{C.CYN}  qcatch  ─  タスクをすばやく記録{C.RST}")
    print(f"{C.BOLD}{C.CYN}{'─' * 42}{C.RST}\n")
    try:
        text = input(f"  {C.BOLD}タスク>{C.RST} ").strip()
    except (EOFError, KeyboardInterrupt):
        print(f"\n  {C.DIM}キャンセルしました。{C.RST}\n")
        _pause()
        return
    if not text:
        print(f"  {C.DIM}何も入力されませんでした。{C.RST}\n")
        _pause()
        return
    cmd_add(text)
    count = sum(
        1 for ln in INBOX_FILE.read_text(encoding="utf-8").splitlines() if ln.strip()
    )
    print(f"  {C.DIM}inbox: {count} 件  ─  整理: python qcatch.py sort{C.RST}\n")
    _pause()


def _pause() -> None:
    input(f"  {C.DIM}[Enter] で閉じる...{C.RST}")


# ── list ─────────────────────────────────────────────────────────────────────
def cmd_list() -> None:
    if not INBOX_FILE.exists():
        print(f"{C.DIM}inbox は空です。{C.RST}")
        return
    content = INBOX_FILE.read_text(encoding="utf-8").strip()
    if not content:
        print(f"{C.DIM}inbox は空です。{C.RST}")
        return
    lines = [ln for ln in content.splitlines() if ln.strip()]
    print(f"\n{C.BOLD}{C.CYN}inbox ({len(lines)} 件){C.RST}")
    print(f"{C.DIM}{'─' * 50}{C.RST}")
    for ln in lines:
        print(f"  {ln}")
    print(f"{C.DIM}{'─' * 50}{C.RST}\n")


# ── sort ─────────────────────────────────────────────────────────────────────
def cmd_sort(export: bool = False, local: bool = False) -> None:
    """
    inbox を AI で自動分類 → sorted_tasks.md に保存 → inbox をアーカイブ。

    バックエンド決定順:
      1. --export フラグ        → プロンプトをファイルに書き出す
      2. --local フラグ         → Ollama（ローカル）を強制
      3. qcatch_config.json    → sort_backend の設定値に従う
      4. auto（設定なし）       → Ollama が起動中なら Ollama、なければ API キーを探す
    """
    if not INBOX_FILE.exists():
        print(f"{C.YLW}inbox が見つかりません。{C.RST}")
        return
    content = INBOX_FILE.read_text(encoding="utf-8").strip()
    if not content:
        print(f"{C.YLW}inbox は空です。{C.RST}")
        return

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── --export ───────────────────────────────────────────────────────────
    if export:
        prompt_text = _build_sort_prompt(content, now_str)
        export_path = DATA_DIR / "sort_prompt.txt"
        export_path.write_text(prompt_text, encoding="utf-8")
        print(
            f"{C.GRN}{C.BOLD}✓{C.RST} プロンプトを書き出しました → {C.BOLD}{export_path}{C.RST}"
        )
        print(
            f"  {C.DIM}Claude.ai や Gemini にこのファイルの内容を貼り付けて実行してください。{C.RST}"
        )
        return

    cfg = _load_config()

    # ── --local フラグで強制 Ollama ────────────────────────────────────────
    if local:
        result_md = _sort_with_ollama(content, now_str, cfg)

    # ── 設定ファイルの backend 指定 ────────────────────────────────────────
    elif cfg["sort_backend"] == "ollama":
        result_md = _sort_with_ollama(content, now_str, cfg)

    elif cfg["sort_backend"] == "gemini":
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            print(f"{C.RED}GEMINI_API_KEY が設定されていません。{C.RST}")
            sys.exit(1)
        result_md = _sort_with_gemini(content, now_str, key)

    elif cfg["sort_backend"] == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            print(f"{C.RED}ANTHROPIC_API_KEY が設定されていません。{C.RST}")
            sys.exit(1)
        result_md = _sort_with_anthropic(_build_sort_prompt(content, now_str), key)

    # ── auto: Ollama が動いていれば優先、なければ API キーを探す ─────────────
    else:
        if _ollama_is_running():
            result_md = _sort_with_ollama(content, now_str, cfg)
        else:
            gemini_key = os.environ.get("GEMINI_API_KEY")
            anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
            if gemini_key:
                result_md = _sort_with_gemini(content, now_str, gemini_key)
            elif anthropic_key:
                result_md = _sort_with_anthropic(
                    _build_sort_prompt(content, now_str), anthropic_key
                )
            else:
                print(
                    f"{C.YLW}バックエンドが見つかりません。以下のどれかを設定してください:{C.RST}"
                )
                print(
                    f"  {C.BOLD}Ollama（推奨・無料・ローカル）{C.RST}: ollama serve を起動"
                )
                print(
                    f"  {C.BOLD}Gemini（無料枠）{C.RST}:           GEMINI_API_KEY を設定"
                )
                print(
                    f"  {C.BOLD}設定を固定{C.RST}:                  qcatch config set backend ollama"
                )
                print(
                    f"  {C.BOLD}手動{C.RST}:                        qcatch sort --export"
                )
                sys.exit(1)

    _save_sorted(result_md)
    _archive_inbox(content, now_str)
    print(f"{C.GRN}{C.BOLD}✓{C.RST} 分類完了 → {C.BOLD}{SORTED_FILE.name}{C.RST}")
    print(
        f"{C.GRN}{C.BOLD}✓{C.RST} inbox をアーカイブ → {C.BOLD}{ARCHIVE_FILE.name}{C.RST}"
    )


# ── sort ヘルパー ─────────────────────────────────────────────────────────────
def _build_sort_prompt(content: str, now_str: str) -> str:
    return f"""\
{_get_few_shot_text()}以下のタスクリストを読み、「仕事」「プライベート」「買い物」「学習」「その他」のカテゴリに分類してください。
タイムスタンプ（[YYYY-MM-DD HH:MM] の部分）はそのまま保持してください。
空のカテゴリは省略してください。

タスクリスト:
{content}

以下の形式のマークダウンで出力してください（説明文や前置きは不要・マークダウンのみ）:

# タスク整理 ({now_str})

## 仕事
- [YYYY-MM-DD HH:MM] タスク内容

## プライベート
- ...

## 買い物
- ...

## 学習
- ...

## その他
- ...
"""


def _sort_with_gemini(content: str, now_str: str, api_key: str) -> str:
    """
    Gemini 2.0 Flash + Pydantic 構造化出力で分類。

    ────────────────────────────────────────────────────────────
    【無料枠の安全性】
    - google-genai ライブラリ + Google AI Studio キー（AIzaSy...）を使用
    - クレジットカード不要・レート制限超過はエラーで止まるだけ・自動課金なし
    - ★ Vertex AI（google-cloud-aiplatform）とは別物。使用しないこと。
    ────────────────────────────────────────────────────────────
    """
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print(f"{C.RED}google-genai が見つかりません: pip install google-genai{C.RST}")
        sys.exit(1)

    print(f"{C.CYN}Gemini 2.5 Flash（無料枠）で分類中...{C.RST}")

    client = genai.Client(api_key=api_key)

    # Pydantic スキーマが使える場合は構造化出力、そうでなければマークダウン直接出力
    if PYDANTIC_OK:
        prompt = (
            _get_few_shot_text()
            + f"以下のタスクを {CATEGORIES} のいずれかに分類してください。\n"
            f"タイムスタンプは [YYYY-MM-DD HH:MM] の形式をそのまま使用してください。\n\n"
            f"{content}"
        )
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=SortedTasks,
                    temperature=0.1,
                ),
            )
            sorted_data = SortedTasks.model_validate_json(response.text)
            return _tasks_to_md(sorted_data.tasks, now_str)
        except Exception:
            pass  # フォールバック: マークダウン直接出力

    # フォールバック: マークダウン形式で直接出力
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=_build_sort_prompt(content, now_str),
        config=types.GenerateContentConfig(temperature=0.1),
    )
    return response.text


def _tasks_to_md(tasks, now_str: str) -> str:
    """TaskItem のリストをマークダウン文字列に変換。"""
    by_cat: dict[str, list[str]] = defaultdict(list)
    for t in tasks:
        by_cat[t.category].append(f"- [{t.timestamp}] {t.text}")

    lines = [f"# タスク整理 ({now_str})", ""]
    for cat in CATEGORIES:
        if cat in by_cat:
            lines.append(f"## {cat}")
            lines.extend(by_cat[cat])
            lines.append("")
    return "\n".join(lines)


def _ollama_is_running() -> bool:
    """Ollama のローカルサーバーが起動しているか確認する（軽量チェック）。"""
    try:
        import urllib.request

        cfg = _load_config()
        urllib.request.urlopen(cfg["ollama_host"], timeout=1)
        return True
    except Exception:
        return False


def _sort_with_ollama(content: str, now_str: str, cfg: dict | None = None) -> str:
    """Ollama（完全ローカル）で分類。`ollama serve` が起動済みであること。"""
    try:
        import ollama as ollama_lib
    except ImportError:
        print(f"{C.RED}ollama が見つかりません: pip install ollama{C.RST}")
        print(f"  また Ollama アプリのインストールも必要: https://ollama.com")
        sys.exit(1)

    if cfg is None:
        cfg = _load_config()
    # 優先順位: 環境変数 > config > デフォルト(phi4)
    model = os.environ.get("QCATCH_OLLAMA_MODEL", cfg.get("ollama_model", "phi4"))
    print(f"{C.CYN}Ollama（{model}）でローカル分類中...{C.RST}")

    prompt = (
        f"以下のタスクを '仕事', 'プライベート', '買い物', '学習', 'その他' に分類し、"
        f"必ず次の JSON 形式のみを返すこと（説明文不要）:\n"
        f'{{"tasks": [{{"text": "...", "timestamp": "...", "category": "..."}}]}}\n\n'
        f"{content}"
    )

    try:
        response = ollama_lib.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            format="json",
        )
        raw = response["message"]["content"]
        data = json.loads(raw)
        tasks_raw = data.get("tasks", [])

        # 簡易バリデーション & マークダウン変換
        by_cat: dict[str, list[str]] = defaultdict(list)
        for t in tasks_raw:
            cat = t.get("category", "その他")
            if cat not in CATEGORIES:
                cat = "その他"
            ts = t.get("timestamp", "")
            txt = t.get("text", "")
            by_cat[cat].append(f"- [{ts}] {txt}" if ts else f"- {txt}")

        lines = [f"# タスク整理 ({now_str})（Ollama: {model}）", ""]
        for cat in CATEGORIES:
            if cat in by_cat:
                lines.append(f"## {cat}")
                lines.extend(by_cat[cat])
                lines.append("")
        return "\n".join(lines)

    except Exception as e:
        print(f"{C.RED}Ollama エラー: {e}{C.RST}")
        print(f"  ollama serve が起動しているか確認してください。")
        print(f"  モデルのインストール: ollama pull {model}")
        sys.exit(1)


def _sort_with_anthropic(prompt_text: str, api_key: str) -> str:
    """Claude Haiku で分類（有料 API・フォールバック用）。"""
    try:
        import anthropic
    except ImportError:
        print(f"{C.RED}anthropic が見つかりません: pip install anthropic{C.RST}")
        sys.exit(1)
    print(f"{C.CYN}Claude Haiku（Anthropic API）で分類中...{C.RST}")
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt_text}],
    )
    return message.content[0].text


def cmd_config(action: str, key: str = "", value: str = "") -> None:
    """設定の表示・変更。"""
    cfg = _load_config()

    if action == "show":
        print(f"\n{C.BOLD}{C.CYN}qcatch 設定  ({CONFIG_FILE}){C.RST}")
        print(f"{C.DIM}{'─' * 45}{C.RST}")
        for k, v in cfg.items():
            print(f"  {C.BOLD}{k:<20}{C.RST} {v}")
        print(f"{C.DIM}{'─' * 45}{C.RST}")
        print(f"  {C.DIM}変更: qcatch config set <key> <value>{C.RST}\n")

    elif action == "set":
        if key not in _DEFAULT_CONFIG:
            print(f"{C.RED}不明なキー: {key}{C.RST}")
            print(f"  使用可能: {list(_DEFAULT_CONFIG.keys())}")
            sys.exit(1)
        if key == "sort_backend" and value not in (
            "auto",
            "ollama",
            "gemini",
            "anthropic",
            "export",
        ):
            print(
                f"{C.RED}sort_backend に指定できる値: auto / ollama / gemini / anthropic / export{C.RST}"
            )
            sys.exit(1)
        cfg[key] = value
        _save_config(cfg)
        print(
            f"{C.GRN}{C.BOLD}✓{C.RST} {key} = {C.BOLD}{value}{C.RST}  ({CONFIG_FILE})"
        )

    elif action == "reset":
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
        print(f"{C.GRN}{C.BOLD}✓{C.RST} 設定をデフォルトにリセットしました。")

    else:
        print(f"使い方: qcatch config show | set <key> <value> | reset")


def _save_sorted(result: str) -> None:
    if SORTED_FILE.exists() and SORTED_FILE.read_text(encoding="utf-8").strip():
        with open(SORTED_FILE, "a", encoding="utf-8") as f:
            f.write("\n\n---\n\n")
            f.write(result.strip() + "\n")
    else:
        SORTED_FILE.write_text(result.strip() + "\n", encoding="utf-8")


def _archive_inbox(content: str, now_str: str) -> None:
    with open(ARCHIVE_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n# アーカイブ ({now_str})\n")
        f.write(content + "\n")
    INBOX_FILE.write_text("", encoding="utf-8")


# ── エントリポイント ──────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        prog="qcatch",
        description="爆速タスクキャッチ & AI自動整理",
    )
    sub = parser.add_subparsers(dest="command")

    p_add = sub.add_parser("add", help="タスクを即追加（API通信なし）")
    p_add.add_argument("text", help="追加するタスクのテキスト")

    sub.add_parser("toast", help="Quick Add ウィンドウを起動（Windows Search 起動用）")
    sub.add_parser(
        "dashboard", help="ダッシュボード（Inbox 管理 + 分類済みタスク閲覧）"
    )
    sub.add_parser("prompt", help="ターミナル対話入力モード")
    sub.add_parser("list", help="inbox の一覧表示")

    p_sort = sub.add_parser("sort", help="AI でタスクを自動分類")
    p_sort.add_argument(
        "--export",
        action="store_true",
        help="API 不使用・プロンプトをファイルに書き出す",
    )
    p_sort.add_argument(
        "--local", action="store_true", help="Ollama（ローカル）を強制使用"
    )

    p_cfg = sub.add_parser("config", help="設定の表示・変更")
    p_cfg.add_argument(
        "action",
        choices=["show", "set", "reset"],
        help="show: 表示 / set: 変更 / reset: 初期化",
    )
    p_cfg.add_argument(
        "key",
        nargs="?",
        default="",
        help="変更するキー（sort_backend / ollama_model など）",
    )
    p_cfg.add_argument("value", nargs="?", default="", help="設定する値")

    args = parser.parse_args()

    if args.command == "add":
        cmd_add(args.text)
    elif args.command == "toast":
        cmd_toast()
    elif args.command == "dashboard":
        cmd_dashboard()
    elif args.command == "prompt":
        cmd_prompt()
    elif args.command == "list":
        cmd_list()
    elif args.command == "sort":
        cmd_sort(export=args.export, local=args.local)
    elif args.command == "config":
        cmd_config(args.action, args.key, args.value)
    else:
        # 引数なし起動 → toast モード（使えない場合は prompt にフォールバック）
        cmd_toast()


if __name__ == "__main__":
    main()
