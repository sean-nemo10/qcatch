"""web/deps.py — 共有状態・ヘルパー関数。全ルーターがここを参照する。"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import HTTPException

from core.models import AppData, Category, ChecklistTemplate, Task

if TYPE_CHECKING:
    pass

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
