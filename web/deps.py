"""web/deps.py — 共有状態・ヘルパー関数。全ルーターがここを参照する。"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets as _secrets
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request

from core.models import AppData, Category, ChecklistTemplate, Task

if TYPE_CHECKING:
    pass

# ── セッション認証 ────────────────────────────────────────────────────────────

_AUTH_USER = os.environ.get("ZZZMEMO_USER", "")
_AUTH_PASS = os.environ.get("ZZZMEMO_PASS", "")
_AUTH_ENABLED = bool(_AUTH_USER and _AUTH_PASS)
INTERNAL_API_KEY = os.environ.get("ZZZMEMO_API_KEY", "")
GOOGLE_EMAIL = os.environ.get("ZZZMEMO_GOOGLE_EMAIL", "")
SESSION_COOKIE = "zzzmemo_session"
SESSION_MAX_AGE = 90 * 24 * 3600  # 90日

# 認証が何も設定されていない = ローカル開発モード（認証スキップ）
AUTH_REQUIRED = _AUTH_ENABLED or bool(GOOGLE_EMAIL)


def make_session_token() -> str:
    """認証情報から決定論的なセッショントークンを生成（ストレージ不要）。"""
    if _AUTH_ENABLED:
        key = f"{_AUTH_USER}:{_AUTH_PASS}".encode()
    else:
        key = GOOGLE_EMAIL.encode() if GOOGLE_EMAIL else b"zzzmemo-open"
    return hmac.new(key, b"zzzmemo-session-v1", hashlib.sha256).hexdigest()


def verify_session(request: Request) -> bool:
    if not AUTH_REQUIRED:
        return True
    if INTERNAL_API_KEY:
        api_key = request.headers.get("X-Api-Key", "")
        if api_key and _secrets.compare_digest(api_key, INTERNAL_API_KEY):
            return True
    token = request.cookies.get(SESSION_COOKIE, "")
    return _secrets.compare_digest(token, make_session_token())


# ── パス解決 ──────────────────────────────────────────────────────────────────

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent.parent

CONFIG_FILE = BASE_DIR / "qcatch_config.json"
CATEGORIES: list[Category] = ["仕事", "プライベート", "買い物", "学習", "その他"]

# ── 共有状態（lifespan で置き換えられる） ────────────────────────────────────

app_data: AppData = AppData()
logger: logging.Logger = logging.getLogger("ZzzMemo")

# ── ヘルパー ──────────────────────────────────────────────────────────────────


def find_task(task_id: str) -> Task:
    for t in app_data.tasks:
        if t.id == task_id:
            return t
    raise HTTPException(404, "タスクが見つかりません")


def find_task_idx(task_id: str) -> int:
    for i, t in enumerate(app_data.tasks):
        if t.id == task_id:
            return i
    raise HTTPException(404, "タスクが見つかりません")


def find_checklist(checklist_id: str) -> ChecklistTemplate:
    for c in app_data.checklists:
        if c.id == checklist_id:
            return c
    raise HTTPException(404, "チェックリストが見つかりません")


def find_checklist_idx(checklist_id: str) -> int:
    for i, c in enumerate(app_data.checklists):
        if c.id == checklist_id:
            return i
    raise HTTPException(404, "チェックリストが見つかりません")


def load_config() -> dict:
    _DEFAULT = {
        "sort_backend": "auto",
        "ollama_model": "phi4",
        "ollama_host": "http://localhost:11434",
    }
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return {**_DEFAULT, **data}
        except Exception:
            pass
    return dict(_DEFAULT)


def save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )
