"""mcp_server.py — ZzzMemo MCP Server

Claude Code (and other MCP clients) can read/write ZzzMemo data
directly via SQLite, without the web server running.

Setup in ~/.claude/settings.json:
{
  "mcpServers": {
    "zzzmemo": {
      "command": "python",
      "args": ["<path-to-repo>/mcp_server.py"],
      "type": "stdio"
    }
  }
}

Install: pip install mcp
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import date, datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP

DB_PATH = Path(__file__).parent / "data" / "qcatch.db"

mcp = FastMCP("ZzzMemo")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


# ── Tasks ─────────────────────────────────────────────────────────────


@mcp.tool()
def get_tasks(status: str = "inbox") -> str:
    """タスクを取得する。status: inbox / todo / done / trashed / longterm"""
    conn = _conn()
    rows = conn.execute(
        "SELECT id, text, status, category, tags, due_date, importance, created_at "
        "FROM tasks WHERE status=? ORDER BY created_at DESC",
        (status,),
    ).fetchall()
    conn.close()
    tasks = []
    for r in rows:
        t = dict(r)
        t["tags"] = json.loads(t["tags"] or "[]")
        tasks.append(t)
    return json.dumps(tasks, ensure_ascii=False, indent=2)


@mcp.tool()
def add_task(
    text: str, category: str = "その他", importance: str = "medium", due_date: str = ""
) -> str:
    """新しいタスクを inbox に追加する。
    category: 仕事/プライベート/買い物/学習/その他
    importance: high/medium/low
    due_date: YYYY-MM-DD 形式（任意）
    """
    task_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    due = (due_date + "T00:00:00") if due_date else None
    conn = _conn()
    with conn:
        conn.execute(
            "INSERT INTO tasks (id, text, status, category, tags, created_at, importance, due_date) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (task_id, text, "inbox", category, "[]", now, importance, due),
        )
    conn.close()
    return f"タスクを追加しました: {text}"


@mcp.tool()
def complete_task(task_id: str) -> str:
    """タスクを完了にする。"""
    now = datetime.now().isoformat()
    conn = _conn()
    with conn:
        conn.execute(
            "UPDATE tasks SET status='done', completed_at=? WHERE id=?",
            (now, task_id),
        )
    conn.close()
    return f"完了: {task_id}"


@mcp.tool()
def get_task_summary() -> str:
    """inbox / todo のタスク件数サマリーを返す。"""
    conn = _conn()
    rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM tasks WHERE status IN ('inbox','todo') GROUP BY status"
    ).fetchall()
    conn.close()
    summary = {r["status"]: r["cnt"] for r in rows}
    return json.dumps(summary, ensure_ascii=False)


# ── Diary ─────────────────────────────────────────────────────────────


@mcp.tool()
def get_diary(date_str: str = "") -> str:
    """日記を取得する。date_str: YYYY-MM-DD（省略時は今日）"""
    if not date_str:
        date_str = date.today().isoformat()
    conn = _conn()
    row = conn.execute(
        "SELECT date_str, content, created_at, updated_at FROM diary_entries WHERE date_str=?",
        (date_str,),
    ).fetchone()
    conn.close()
    if row:
        return json.dumps(dict(row), ensure_ascii=False, indent=2)
    return f"{date_str} の日記はありません"


@mcp.tool()
def get_recent_diaries(days: int = 7) -> str:
    """最近 N 日分の日記一覧を取得する（本文含む）。"""
    conn = _conn()
    rows = conn.execute(
        "SELECT date_str, content, updated_at FROM diary_entries "
        "ORDER BY date_str DESC LIMIT ?",
        (days,),
    ).fetchall()
    conn.close()
    return json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=2)


@mcp.tool()
def save_diary(date_str: str, content: str) -> str:
    """日記を保存する（上書き）。date_str: YYYY-MM-DD"""
    now = datetime.now().isoformat()
    conn = _conn()
    with conn:
        conn.execute(
            "INSERT INTO diary_entries (date_str, content, referenced_task_ids, created_at, updated_at) "
            "VALUES (?,?,?,?,?) "
            "ON CONFLICT(date_str) DO UPDATE SET content=excluded.content, updated_at=excluded.updated_at",
            (date_str, content, "[]", now, now),
        )
    conn.close()
    return f"{date_str} の日記を保存しました"


# ── Blog ──────────────────────────────────────────────────────────────


@mcp.tool()
def get_blog_posts() -> str:
    """ブログ記事一覧（タイトル・タグ・更新日のみ）を取得する。"""
    conn = _conn()
    rows = conn.execute(
        "SELECT id, title, tags, created_at, updated_at FROM blog_posts ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    posts = []
    for r in rows:
        p = dict(r)
        p["tags"] = json.loads(p["tags"] or "[]")
        posts.append(p)
    return json.dumps(posts, ensure_ascii=False, indent=2)


@mcp.tool()
def get_blog_post(post_id: str) -> str:
    """ブログ記事の全文を取得する。"""
    conn = _conn()
    row = conn.execute(
        "SELECT id, title, tags, content, created_at, updated_at FROM blog_posts WHERE id=?",
        (post_id,),
    ).fetchone()
    conn.close()
    if row:
        p = dict(row)
        p["tags"] = json.loads(p["tags"] or "[]")
        return json.dumps(p, ensure_ascii=False, indent=2)
    return f"記事が見つかりません: {post_id}"


if __name__ == "__main__":
    mcp.run()
