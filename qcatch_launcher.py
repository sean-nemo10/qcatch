#!/usr/bin/env python3
"""
qcatch_launcher.py - Windows Search / qcatch.exe 用の軽量ランチャー

外部ライブラリに依存しないため PyInstaller で小さな .exe にビルドできる。
add / list / prompt のみ実装。sort は python qcatch.py sort を使う。
"""

import argparse
import io
import os
import sys
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    os.system("")  # ANSI 有効化
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stdin  = io.TextIOWrapper(sys.stdin.buffer,  encoding="utf-8", errors="replace")

# PyInstaller .exe 実行時は sys.executable（.exe パス）を基準にする
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

DATA_DIR   = BASE_DIR / "data"
INBOX_FILE = DATA_DIR / "inbox.txt"
DATA_DIR.mkdir(exist_ok=True)


class C:
    RST  = "\033[0m";  BOLD = "\033[1m";  DIM  = "\033[2m"
    GRN  = "\033[32m"; YLW  = "\033[33m"; CYN  = "\033[36m"


def cmd_add(text: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"[{timestamp}] {text}\n"
    with open(INBOX_FILE, "a", encoding="utf-8") as f:
        f.write(entry)
    print(f"{C.GRN}{C.BOLD}✓{C.RST} {entry.strip()}")


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


def cmd_prompt() -> None:
    """Windows Search / バッチ起動用の対話入力モード。"""
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
    count = sum(1 for ln in INBOX_FILE.read_text(encoding="utf-8").splitlines() if ln.strip())
    print(f"  {C.DIM}inbox: {count} 件  ─  整理: python qcatch.py sort{C.RST}\n")
    _pause()


def _pause() -> None:
    input(f"  {C.DIM}[Enter] で閉じる...{C.RST}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="qcatch",
        description="爆速タスクキャッチ（Windows Search 版）",
    )
    sub = parser.add_subparsers(dest="command")

    p_add = sub.add_parser("add", help="タスクを即追加")
    p_add.add_argument("text", help="タスクのテキスト")
    sub.add_parser("list",   help="inbox の一覧表示")
    sub.add_parser("prompt", help="対話入力モード")

    p_sort = sub.add_parser("sort", help="AI 分類（python qcatch.py sort を使用）")
    p_sort.add_argument("--export", action="store_true")

    args = parser.parse_args()

    if args.command == "add":
        cmd_add(args.text)
    elif args.command == "list":
        cmd_list()
    elif args.command == "prompt":
        cmd_prompt()
    elif args.command == "sort":
        # .exe 版では sort は動かない（依存ライブラリが含まれていないため）
        print(f"{C.YLW}sort は Python スクリプト版を使用してください:{C.RST}")
        print(f"  python {BASE_DIR / 'qcatch.py'} sort")
        print(f"  python {BASE_DIR / 'qcatch.py'} sort --export")
    else:
        # 引数なし（Windows Search からのダブルクリックなど）→ prompt モード
        cmd_prompt()


if __name__ == "__main__":
    main()
