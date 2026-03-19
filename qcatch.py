#!/usr/bin/env python3
"""qcatch.py - 爆速タスクキャッチ & AI自動整理 CLI"""

import argparse
import io
import os
import sys
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    os.system("")  # ANSI エスケープコードを有効化
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stdin  = io.TextIOWrapper(sys.stdin.buffer,  encoding="utf-8", errors="replace")

# PyInstaller でビルドされた .exe の場合、__file__ は展開先の tmpフォルダを指す。
# sys.executable（.exe 自身のパス）を基準にすることで data/ が正しく解決される。
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

DATA_DIR     = BASE_DIR / "data"
INBOX_FILE   = DATA_DIR / "inbox.txt"
SORTED_FILE  = DATA_DIR / "sorted_tasks.md"
ARCHIVE_FILE = DATA_DIR / "archive.txt"

DATA_DIR.mkdir(exist_ok=True)

# ── ANSI カラー ──────────────────────────────────────────────────────────────
class C:
    RST  = "\033[0m";  BOLD = "\033[1m";  DIM  = "\033[2m"
    RED  = "\033[31m"; GRN  = "\033[32m"; YLW  = "\033[33m"
    CYN  = "\033[36m"; WHT  = "\033[37m"; MGT  = "\033[35m"


# ── add ──────────────────────────────────────────────────────────────────────
def cmd_add(text: str) -> None:
    """タスクを inbox.txt に追記。API通信なし・即終了。"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"[{timestamp}] {text}\n"
    with open(INBOX_FILE, "a", encoding="utf-8") as f:
        f.write(entry)
    print(f"{C.GRN}{C.BOLD}✓{C.RST} {entry.strip()}")


# ── prompt（Windows Search / バッチ起動用）──────────────────────────────────
def cmd_prompt() -> None:
    """ターミナルを開いて対話入力 → add して終了。Windows Search から呼ぶ用。"""
    print(f"\n{C.BOLD}{C.CYN}{'─' * 40}{C.RST}")
    print(f"{C.BOLD}{C.CYN}  qcatch  ─  タスクをすばやく記録{C.RST}")
    print(f"{C.BOLD}{C.CYN}{'─' * 40}{C.RST}\n")
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
    _count = sum(1 for ln in INBOX_FILE.read_text(encoding="utf-8").splitlines() if ln.strip())
    print(f"  {C.DIM}inbox に {_count} 件のタスクがあります。{C.RST}\n")
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
def cmd_sort(export: bool = False) -> None:
    """
    inbox を AI で自動分類 → sorted_tasks.md に保存 → inbox をアーカイブ。
    API キー優先順位: GEMINI_API_KEY（無料）> ANTHROPIC_API_KEY（有料）
    export=True: API 不使用・プロンプトをファイルに書き出す
    """
    if not INBOX_FILE.exists():
        print(f"{C.YLW}inbox が見つかりません。{C.RST}")
        return
    content = INBOX_FILE.read_text(encoding="utf-8").strip()
    if not content:
        print(f"{C.YLW}inbox は空です。{C.RST}")
        return

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    prompt_text = _build_sort_prompt(content, now_str)

    # ── エクスポートモード ─────────────────────────────────────────────────
    if export:
        export_path = DATA_DIR / "sort_prompt.txt"
        export_path.write_text(prompt_text, encoding="utf-8")
        print(f"{C.GRN}{C.BOLD}✓{C.RST} プロンプトを書き出しました → {C.BOLD}{export_path}{C.RST}")
        print(f"  {C.DIM}Claude.ai や Gemini にこのファイルの内容を貼り付けて実行してください。{C.RST}")
        return

    # ── API 自動選択 ───────────────────────────────────────────────────────
    gemini_key    = os.environ.get("GEMINI_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

    if gemini_key:
        result = _sort_with_gemini(prompt_text, gemini_key)
    elif anthropic_key:
        result = _sort_with_anthropic(prompt_text, anthropic_key)
    else:
        print(f"{C.YLW}API キーが設定されていません。{C.RST}")
        print(f"  {C.DIM}無料で使うには: GEMINI_API_KEY を設定してください（Google AI Studio）{C.RST}")
        print(f"  {C.DIM}API なし: python qcatch.py sort --export{C.RST}")
        sys.exit(1)

    _save_sorted(result)
    _archive_inbox(content, now_str)
    print(f"{C.GRN}{C.BOLD}✓{C.RST} 分類完了 → {C.BOLD}{SORTED_FILE.name}{C.RST}")
    print(f"{C.GRN}{C.BOLD}✓{C.RST} inbox をアーカイブ → {C.BOLD}{ARCHIVE_FILE.name}{C.RST}")


def _build_sort_prompt(content: str, now_str: str) -> str:
    return f"""\
以下のタスクリストを読み、「仕事」「プライベート」「買い物」「学習」「その他」のカテゴリに分類してください。
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


def _sort_with_gemini(prompt_text: str, api_key: str) -> str:
    """
    Gemini 1.5 Flash で分類。
    ────────────────────────────────────────────────────────────
    【無料枠の安全性について】
    - google-generativeai ライブラリ + Google AI Studio のキー（AIzaSy...）を使用
    - Google AI Studio のキーは請求先アカウント（クレカ）が不要
    - レート制限を超えた場合は「エラーで止まる」だけで課金は発生しない
    - 自動で有料プランに移行する仕組みはない
    - ★ Vertex AI（google-cloud-aiplatform）のキーは別物・有料 → 使用しない
    ────────────────────────────────────────────────────────────
    無料枠: 15 RPM / 1,000,000 TPM / 1,500 RPD（1日1500リクエスト）
    """
    try:
        import google.generativeai as genai
    except ImportError:
        print(f"{C.RED}google-generativeai が見つかりません。{C.RST}")
        print(f"  pip install google-generativeai")
        sys.exit(1)

    genai.configure(api_key=api_key)
    # gemini-1.5-flash は無料枠対象モデル（高速・軽量）
    model = genai.GenerativeModel("gemini-1.5-flash")
    print(f"{C.CYN}Gemini 1.5 Flash（無料枠）で分類中...{C.RST}")

    try:
        response = model.generate_content(prompt_text)
        return response.text
    except Exception as e:
        err = str(e)
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            print(f"{C.YLW}レート制限に達しました（課金は発生しません）。少し待ってから再試行してください。{C.RST}")
        else:
            print(f"{C.RED}Gemini API エラー: {e}{C.RST}")
        sys.exit(1)


def _sort_with_anthropic(prompt_text: str, api_key: str) -> str:
    """Claude Haiku で分類（有料 API）。"""
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

    p_sort = sub.add_parser("sort", help="AI でタスクを自動分類（Gemini 無料 or Anthropic）")
    p_sort.add_argument(
        "--export", action="store_true",
        help="API を使わずプロンプトをファイルに書き出す",
    )

    sub.add_parser("list",   help="inbox の一覧表示")
    sub.add_parser("prompt", help="対話入力モード（Windows Search / ランチャー起動用）")

    args = parser.parse_args()

    if args.command == "add":
        cmd_add(args.text)
    elif args.command == "sort":
        cmd_sort(export=args.export)
    elif args.command == "list":
        cmd_list()
    elif args.command == "prompt":
        cmd_prompt()
    else:
        # 引数なし起動（Windows Search からダブルクリックなど）→ prompt モード
        if len(sys.argv) == 1:
            cmd_prompt()
        else:
            parser.print_help()


if __name__ == "__main__":
    main()
