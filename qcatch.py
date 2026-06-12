#!/usr/bin/env python3
"""qcatch.py — 爆速タスクキャッチ & Web ダッシュボード

コマンド:
  (引数なし)          ブラウザでダッシュボードを起動
  add "タスク"        inbox.txt に即追記（API通信・重いimportなし）
  prompt              ターミナル対話入力モード
"""

import argparse
import io
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# ── Windows UTF-8 設定 ────────────────────────────────────────────────────────
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

# ── パス解決（PyInstaller 対応） ──────────────────────────────────────────────
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

DATA_DIR = BASE_DIR / "data"
INBOX_FILE = DATA_DIR / "inbox.txt"
DATA_DIR.mkdir(exist_ok=True)

CATEGORIES = ["仕事", "プライベート", "買い物", "学習", "その他"]


# ── ANSI カラー ───────────────────────────────────────────────────────────────
class C:
    RST = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GRN = "\033[32m"
    CYN = "\033[36m"


# ── add（即追記・重いimport一切なし） ────────────────────────────────────────
def cmd_add(text: str) -> None:
    """タスクを inbox.txt に追記。@カテゴリ タグは siphon 時に解釈され todo になる。"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    tag_match = re.search(r"@(" + "|".join(CATEGORIES) + r")\s*$", text)

    entry = f"[{timestamp}] {text.strip()}\n"
    with open(INBOX_FILE, "a", encoding="utf-8") as f:
        f.write(entry)

    if tag_match:
        clean = text[: tag_match.start()].strip()
        print(
            f"{C.GRN}{C.BOLD}✓{C.RST} [{timestamp}] {clean}  {C.CYN}→ {tag_match.group(1)}{C.RST}"
        )
    else:
        print(f"{C.GRN}{C.BOLD}✓{C.RST} {entry.strip()}")


# ── prompt（ターミナル対話入力） ──────────────────────────────────────────────
def cmd_prompt() -> None:
    print(f"\n{C.BOLD}{C.CYN}{'─'*42}{C.RST}")
    print(f"{C.BOLD}{C.CYN}  qcatch  ─  タスクをすばやく記録{C.RST}")
    print(f"{C.BOLD}{C.CYN}{'─'*42}{C.RST}\n")
    try:
        text = input(f"  {C.BOLD}タスク>{C.RST} ").strip()
    except (EOFError, KeyboardInterrupt):
        print(f"\n  {C.DIM}キャンセルしました。{C.RST}\n")
        input(f"  {C.DIM}[Enter] で閉じる...{C.RST}")
        return
    if not text:
        print(f"  {C.DIM}何も入力されませんでした。{C.RST}\n")
        input(f"  {C.DIM}[Enter] で閉じる...{C.RST}")
        return
    cmd_add(text)
    input(f"  {C.DIM}[Enter] で閉じる...{C.RST}")


# ── dashboard（Web サーバー起動） ─────────────────────────────────────────────
def cmd_dashboard() -> None:
    # web パッケージは起動時にだけ import（add の瞬速を維持するため）
    sys.path.insert(0, str(BASE_DIR))
    from web.server import run

    run()


# ── エントリポイント ──────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        prog="qcatch", description="爆速タスクキャッチ & Web ダッシュボード"
    )
    sub = parser.add_subparsers(dest="command")

    p_add = sub.add_parser("add", help="タスクを即追加（API通信なし）")
    p_add.add_argument("text", help="追加するタスクのテキスト")

    sub.add_parser("prompt", help="ターミナル対話入力モード")
    sub.add_parser("toast", help="ダッシュボードを起動（後方互換）")
    sub.add_parser("dashboard", help="Web ダッシュボードを起動")

    args = parser.parse_args()

    if args.command == "add":
        cmd_add(args.text)
    elif args.command == "prompt":
        cmd_prompt()
    else:
        # 引数なし / toast / dashboard → Web UI 起動
        cmd_dashboard()


if __name__ == "__main__":
    main()
