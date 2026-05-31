"""mcp_server.py — ZzzMemo MCP Server (HTTP backend)

Claude Code (and other MCP clients) read/write ZzzMemo through the deployed
HTTP API (default: https://zzzmemo.fly.dev). This means an AI agent can add a
task with a due date and it is pushed to Google Calendar / Tasks by the same
server that owns the Google credentials — no duplicate events, one source of truth.

Configuration (environment variables, set in .mcp.json "env" or the OS):
  ZZZMEMO_BASE_URL   API base URL (default: https://zzzmemo.fly.dev)
  ZZZMEMO_API_KEY    value of the server's ZZZMEMO_API_KEY secret (X-Api-Key auth)

Setup in .mcp.json:
{
  "mcpServers": {
    "zzzmemo": {
      "command": "C:/Users/seann/AppData/Local/Programs/Python/Python313/python.exe",
      "args": ["C:/dev/ZzzMemo/mcp_server.py"],
      "env": {
        "ZZZMEMO_BASE_URL": "https://zzzmemo.fly.dev",
        "ZZZMEMO_API_KEY": "<your-api-key>"
      }
    }
  }
}

Install: pip install mcp
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from mcp.server.fastmcp import FastMCP

BASE_URL = os.environ.get("ZZZMEMO_BASE_URL", "https://zzzmemo.fly.dev").rstrip("/")
API_KEY = os.environ.get("ZZZMEMO_API_KEY", "")

mcp = FastMCP("ZzzMemo")


def _req(method: str, path: str, body: dict | None = None) -> dict | list:
    """Call the ZzzMemo HTTP API. Returns parsed JSON ({} on 204)."""
    url = BASE_URL + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["X-Api-Key"] = API_KEY
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {e.code}: {detail}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"接続失敗 ({BASE_URL}): {e.reason}") from None


def _resolve_end(start: str, end_time: str) -> str:
    """end_time が時刻のみ ("HH:MM:SS") の場合は start の日付を補う。
    既に日付付き ("...T...") ならそのまま返す。"""
    if "T" in end_time:
        return end_time
    date_part = start.split("T")[0]
    return f"{date_part}T{end_time}"


# ── Tasks ─────────────────────────────────────────────────────────────


@mcp.tool()
def get_tasks(status: str = "todo") -> str:
    """タスクを取得する。status: inbox / todo / done / trashed / longterm
    （カンマ区切りで複数指定可: "inbox,todo"）"""
    data = _req("GET", f"/api/tasks?status={urllib.parse.quote(status)}")
    return json.dumps(data.get("tasks", []), ensure_ascii=False, indent=2)


@mcp.tool()
def add_task(
    text: str,
    category: str = "",
    importance: str = "medium",
    due_date: str = "",
    end_time: str = "",
) -> str:
    """新しいタスクを追加する。due_date を付けると Google Calendar / Tasks へ自動同期される。

    category: 仕事 / プライベート / 買い物 / 学習 / その他（空ならAIが後で分類）
    importance: high / medium / low
    due_date: 終日タスクは "YYYY-MM-DD"、時刻指定は "YYYY-MM-DDTHH:MM:SS"（任意）
      - 時刻あり → Google Calendar の予定として作成
      - 時刻なし → Google Tasks（ToDo）として作成
    end_time: 終了時刻 "YYYY-MM-DDTHH:MM:SS"（任意）。指定すると
      「15:00〜16:00」のような幅を持つ Calendar 予定になる。
      時刻だけ "HH:MM:SS" でも可（due_date と同じ日付になる）。
    """
    body: dict = {"text": text, "importance": importance}
    if category:
        body["category"] = category
        body["status"] = "todo"  # 分類済みは todo として登録
    else:
        body["auto_classify"] = True  # 未分類はサーバー側でAI分類
    if due_date:
        start = due_date if "T" in due_date else due_date + "T00:00:00"
        body["due_date"] = start
        if end_time:
            body["due_end"] = _resolve_end(start, end_time)
    task = _req("POST", "/api/tasks", body)
    dest = ""
    if due_date:
        if "T" in due_date or end_time:
            dest = " → Calendar"
        else:
            dest = " → Google Tasks"
    return f"タスクを追加しました: {text}{dest}\nid: {task.get('id', '')}"


@mcp.tool()
def update_task(
    task_id: str,
    text: str = "",
    category: str = "",
    due_date: str = "",
    end_time: str = "",
) -> str:
    """既存タスクを更新する。due_date / end_time を変更すると Google 側にも即反映される。
    due_date に "clear" を渡すと期日を外し、Google の予定/ToDo も削除する。
    end_time に "clear" を渡すと終了時刻だけ外す（予定はゼロ幅に戻る）。"""
    body: dict = {}
    if text:
        body["text"] = text
    if category:
        body["category"] = category
    if due_date == "clear":
        body["due_date"] = None
    elif due_date:
        body["due_date"] = due_date if "T" in due_date else due_date + "T00:00:00"
    if end_time == "clear":
        body["due_end"] = None
    elif end_time:
        # due_date が同時指定ならそれを基準、なければ end_time の日付をそのまま使う
        base = body.get("due_date") or end_time
        body["due_end"] = _resolve_end(base, end_time)
    if not body:
        return "変更内容がありません"
    _req("PATCH", f"/api/tasks/{task_id}", body)
    return f"更新しました: {task_id}"


@mcp.tool()
def complete_task(task_id: str) -> str:
    """タスクを完了にする。"""
    _req("PATCH", f"/api/tasks/{task_id}", {"status": "done"})
    return f"完了: {task_id}"


@mcp.tool()
def get_task_summary() -> str:
    """inbox / todo のタスク件数サマリーを返す。"""
    data = _req("GET", "/api/tasks?status=inbox,todo")
    summary: dict[str, int] = {}
    for t in data.get("tasks", []):
        summary[t["status"]] = summary.get(t["status"], 0) + 1
    return json.dumps(summary, ensure_ascii=False)


# ── Calendar ──────────────────────────────────────────────────────────


@mcp.tool()
def get_calendar_events(days: int = 7) -> str:
    """今日から days 日分の Google Calendar の予定を取得する。
    タスクを追加する前に既存予定を確認して重複を避けるのに使う。"""
    data = _req("GET", f"/api/calendar/events?days={int(days)}")
    if not data.get("authenticated", True):
        return "Google 未認証です。ZzzMemo の設定タブから Google ログインしてください。"
    return json.dumps(data.get("events", []), ensure_ascii=False, indent=2)


# ── Diary ─────────────────────────────────────────────────────────────


@mcp.tool()
def get_diary(date_str: str = "") -> str:
    """日記を取得する。date_str: YYYY-MM-DD（省略時は今日）"""
    if not date_str:
        from datetime import date

        date_str = date.today().isoformat()
    try:
        entry = _req("GET", f"/api/diary/{date_str}")
    except RuntimeError as e:
        if "404" in str(e):
            return f"{date_str} の日記はありません"
        raise
    return json.dumps(entry, ensure_ascii=False, indent=2)


@mcp.tool()
def get_recent_diaries(days: int = 7) -> str:
    """最近 N 日分の日記一覧を取得する（本文含む）。"""
    listing = _req("GET", "/api/diary")
    dates = listing.get("dates", [])[:days]
    entries = [_req("GET", f"/api/diary/{d}") for d in dates]
    return json.dumps(entries, ensure_ascii=False, indent=2)


@mcp.tool()
def save_diary(date_str: str, content: str) -> str:
    """日記を保存する（上書き）。date_str: YYYY-MM-DD"""
    _req("POST", "/api/diary", {"date_str": date_str, "content": content})
    return f"{date_str} の日記を保存しました"


# ── Blog ──────────────────────────────────────────────────────────────


@mcp.tool()
def get_blog_posts() -> str:
    """ブログ記事一覧（タイトル・タグ・更新日・プレビュー）を取得する。"""
    data = _req("GET", "/api/blog")
    return json.dumps(data.get("posts", []), ensure_ascii=False, indent=2)


@mcp.tool()
def get_blog_post(post_id: str) -> str:
    """ブログ記事の全文を取得する。"""
    try:
        post = _req("GET", f"/api/blog/{post_id}")
    except RuntimeError as e:
        if "404" in str(e):
            return f"記事が見つかりません: {post_id}"
        raise
    return json.dumps(post, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run()
