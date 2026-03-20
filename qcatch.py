#!/usr/bin/env python3
"""qcatch.py - 爆速タスクキャッチ & AI自動整理 CLI"""

import argparse
import io
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Literal

if sys.platform == "win32":
    os.system("")  # ANSI 有効化
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stdin  = io.TextIOWrapper(sys.stdin.buffer,  encoding="utf-8", errors="replace")

# PyInstaller .exe 実行時は sys.executable（.exe パス）を基準にする
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

DATA_DIR     = BASE_DIR / "data"
INBOX_FILE   = DATA_DIR / "inbox.txt"
SORTED_FILE  = DATA_DIR / "sorted_tasks.md"
ARCHIVE_FILE = DATA_DIR / "archive.txt"

DATA_DIR.mkdir(exist_ok=True)

CATEGORIES = ["仕事", "プライベート", "買い物", "学習", "その他"]

# ── ANSI カラー ──────────────────────────────────────────────────────────────
class C:
    RST  = "\033[0m";  BOLD = "\033[1m";  DIM  = "\033[2m"
    RED  = "\033[31m"; GRN  = "\033[32m"; YLW  = "\033[33m"
    CYN  = "\033[36m"; WHT  = "\033[37m"; MGT  = "\033[35m"


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


# ── add ──────────────────────────────────────────────────────────────────────
def cmd_add(text: str) -> None:
    """タスクを inbox.txt に追記。API通信なし・即終了。"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"[{timestamp}] {text}\n"
    with open(INBOX_FILE, "a", encoding="utf-8") as f:
        f.write(entry)
    print(f"{C.GRN}{C.BOLD}✓{C.RST} {entry.strip()}")


# ── toast（Windows トースト通知からの入力）──────────────────────────────────
def cmd_toast() -> None:
    """
    Windows 11 のトースト通知にテキスト入力フィールドを表示し、
    入力されたタスクを inbox.txt に追記する。
    Windows Search から呼ぶ最速モード（コンソールウィンドウが前面に出ない）。
    """
    try:
        from win11toast import toast
    except ImportError:
        print(f"{C.YLW}win11toast が見つかりません: pip install win11toast{C.RST}")
        print(f"  代わりに prompt モードを起動します...\n")
        cmd_prompt()
        return

    result = toast(
        "⚡ qcatch",
        "思いついたタスクを入力",
        input="タスク内容",
        button="追加",
        duration="long",
    )

    # win11toast のレスポンスから入力テキストを取得
    text = ""
    if isinstance(result, dict):
        user_input = result.get("user_input", {})
        if isinstance(user_input, dict):
            text = next(iter(user_input.values()), "").strip()
        elif isinstance(user_input, str):
            text = user_input.strip()

    if text:
        cmd_add(text)
        count = sum(1 for ln in INBOX_FILE.read_text(encoding="utf-8").splitlines() if ln.strip())
        toast("qcatch", f"追加しました（inbox: {count} 件）", duration="short")
    # キャンセルや空入力は何もしない（トースト通知が自然に消えるだけ）


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
    count = sum(1 for ln in INBOX_FILE.read_text(encoding="utf-8").splitlines() if ln.strip())
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

    優先順位:
      --local 指定: Ollama（完全ローカル）
      GEMINI_API_KEY あり: Gemini 2.0 Flash（無料枠）
      ANTHROPIC_API_KEY あり: Claude Haiku（有料・フォールバック）
      --export: API 不使用・プロンプトをファイルに書き出す
    """
    if not INBOX_FILE.exists():
        print(f"{C.YLW}inbox が見つかりません。{C.RST}")
        return
    content = INBOX_FILE.read_text(encoding="utf-8").strip()
    if not content:
        print(f"{C.YLW}inbox は空です。{C.RST}")
        return

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── エクスポートモード ─────────────────────────────────────────────────
    if export:
        prompt_text = _build_sort_prompt(content, now_str)
        export_path = DATA_DIR / "sort_prompt.txt"
        export_path.write_text(prompt_text, encoding="utf-8")
        print(f"{C.GRN}{C.BOLD}✓{C.RST} プロンプトを書き出しました → {C.BOLD}{export_path}{C.RST}")
        print(f"  {C.DIM}Claude.ai や Gemini にこのファイルの内容を貼り付けて実行してください。{C.RST}")
        return

    # ── ローカルモード（Ollama）──────────────────────────────────────────
    if local:
        result_md = _sort_with_ollama(content, now_str)
    else:
        gemini_key    = os.environ.get("GEMINI_API_KEY")
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

        if gemini_key:
            result_md = _sort_with_gemini(content, now_str, gemini_key)
        elif anthropic_key:
            result_md = _sort_with_anthropic(_build_sort_prompt(content, now_str), anthropic_key)
        else:
            print(f"{C.YLW}API キーが設定されていません。{C.RST}")
            print(f"  {C.DIM}無料: GEMINI_API_KEY を設定（Google AI Studio）{C.RST}")
            print(f"  {C.DIM}ローカル: python qcatch.py sort --local  （Ollama 必要）{C.RST}")
            print(f"  {C.DIM}手動: python qcatch.py sort --export{C.RST}")
            sys.exit(1)

    _save_sorted(result_md)
    _archive_inbox(content, now_str)
    print(f"{C.GRN}{C.BOLD}✓{C.RST} 分類完了 → {C.BOLD}{SORTED_FILE.name}{C.RST}")
    print(f"{C.GRN}{C.BOLD}✓{C.RST} inbox をアーカイブ → {C.BOLD}{ARCHIVE_FILE.name}{C.RST}")


# ── sort ヘルパー ─────────────────────────────────────────────────────────────
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

    print(f"{C.CYN}Gemini 2.0 Flash（無料枠）で分類中...{C.RST}")

    client = genai.Client(api_key=api_key)

    # Pydantic スキーマが使える場合は構造化出力、そうでなければマークダウン直接出力
    if PYDANTIC_OK:
        prompt = (
            f"以下のタスクを {CATEGORIES} のいずれかに分類してください。\n"
            f"タイムスタンプは [YYYY-MM-DD HH:MM] の形式をそのまま使用してください。\n\n"
            f"{content}"
        )
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
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
        model="gemini-2.0-flash",
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


def _sort_with_ollama(content: str, now_str: str) -> str:
    """Ollama（完全ローカル）で分類。`ollama serve` が起動済みであること。"""
    try:
        import ollama
    except ImportError:
        print(f"{C.RED}ollama が見つかりません: pip install ollama{C.RST}")
        print(f"  また Ollama アプリのインストールも必要: https://ollama.com")
        sys.exit(1)

    # 推奨モデル: phi4（精度高・軽量）または llama3.2
    model = os.environ.get("QCATCH_OLLAMA_MODEL", "phi4")
    print(f"{C.CYN}Ollama（{model}）でローカル分類中...{C.RST}")

    prompt = (
        f"以下のタスクを '仕事', 'プライベート', '買い物', '学習', 'その他' に分類し、"
        f"必ず次の JSON 形式のみを返すこと（説明文不要）:\n"
        f'{{\"tasks\": [{{\"text\": \"...\", \"timestamp\": \"...\", \"category\": \"...\"}}]}}\n\n'
        f"{content}"
    )

    try:
        response = ollama.chat(
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
            ts  = t.get("timestamp", "")
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

    p_add = sub.add_parser("add",    help="タスクを即追加（API通信なし）")
    p_add.add_argument("text", help="追加するタスクのテキスト")

    sub.add_parser("toast",  help="トースト通知から入力（Windows Search 起動用・最速）")
    sub.add_parser("prompt", help="ターミナル対話入力モード")
    sub.add_parser("list",   help="inbox の一覧表示")

    p_sort = sub.add_parser("sort",  help="AI でタスクを自動分類")
    p_sort.add_argument("--export", action="store_true",
                        help="API 不使用・プロンプトをファイルに書き出す")
    p_sort.add_argument("--local",  action="store_true",
                        help="Ollama（ローカル LLM）を使用")

    args = parser.parse_args()

    if args.command == "add":
        cmd_add(args.text)
    elif args.command == "toast":
        cmd_toast()
    elif args.command == "prompt":
        cmd_prompt()
    elif args.command == "list":
        cmd_list()
    elif args.command == "sort":
        cmd_sort(export=args.export, local=args.local)
    else:
        # 引数なし起動 → toast モード（使えない場合は prompt にフォールバック）
        cmd_toast()


if __name__ == "__main__":
    main()
