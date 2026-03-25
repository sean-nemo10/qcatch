"""web/routers/tasks.py — /api/tasks, /api/sort, /api/suggest-*, /api/export"""

from __future__ import annotations

import copy
import os
from collections import defaultdict
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from core.models import Category, Importance, Task
from core.storage import save_data_bg
from web import deps

router = APIRouter()


# ── Pydantic スキーマ ─────────────────────────────────────────────────────────


class TaskIn(BaseModel):
    text: str
    category: Optional[Category] = None
    due_date: Optional[datetime] = None
    importance: Optional[Importance] = None
    status: Optional[str] = None  # longterm / inbox (default)


class TaskPatch(BaseModel):
    status: Optional[str] = None
    category: Optional[Category] = None
    tags: Optional[list[str]] = None
    text: Optional[str] = None
    due_date: Optional[datetime] = None
    importance: Optional[Importance] = None


class BulkTaskItem(BaseModel):
    text: str
    category: Optional[Category] = None
    due_date: Optional[datetime] = None


class DashboardOrderIn(BaseModel):
    order: list[str]


class AiKeyIn(BaseModel):
    api_key: Optional[str] = None


class TagSuggestion(BaseModel):
    id: str
    suggested: Category


class ApplyTagsIn(BaseModel):
    suggestions: list[TagSuggestion]


class SplitItem(BaseModel):
    task_id: str
    suggested_tag: str


class ApplySplitsIn(BaseModel):
    splits: list[SplitItem]


# ── /api/tasks ────────────────────────────────────────────────────────────────


@router.get("/api/tasks")
def get_tasks(status: Optional[str] = None):
    from core.storage import siphon_inbox

    siphon_inbox(deps.app_data)
    tasks = deps.app_data.tasks
    if status:
        statuses = status.split(",")
        tasks = [t for t in tasks if t.status in statuses]
    return {"tasks": [t.model_dump() for t in tasks]}


@router.post("/api/tasks", status_code=201)
def add_task(body: TaskIn):
    status = body.status if body.status in ("inbox", "longterm") else "inbox"
    task = Task(
        text=body.text,
        category=body.category,
        due_date=body.due_date,
        importance=body.importance or "medium",
        status=status,
    )
    deps.app_data.tasks.append(task)
    save_data_bg(deps.app_data)
    return task.model_dump()


@router.patch("/api/tasks/{task_id}")
def update_task(task_id: str, body: TaskPatch):
    task = deps.find_task(task_id)
    if body.status:
        if body.status not in ("inbox", "todo", "done", "trashed", "longterm"):
            raise HTTPException(400, "invalid status")
        task.status = body.status
        if body.status == "done":
            task.completed_at = datetime.now()
        elif body.status in ("inbox", "todo", "trashed", "longterm"):
            task.completed_at = None
    if "category" in body.model_fields_set:
        task.category = body.category
    if body.tags is not None:
        task.tags = body.tags
    if body.text is not None and body.text.strip():
        task.text = body.text.strip()
    if "due_date" in body.model_fields_set:
        task.due_date = body.due_date
    if body.importance is not None:
        task.importance = body.importance
    save_data_bg(deps.app_data)
    return task.model_dump()


@router.post("/api/tasks/bulk-complete")
def bulk_complete(ids: list[str]):
    now = datetime.now()
    updated = []
    for tid in ids:
        try:
            task = deps.find_task(tid)
            task.status = "done"
            task.completed_at = now
            updated.append(task.model_dump())
        except HTTPException:
            pass
    save_data_bg(deps.app_data)
    return {"updated": updated}


@router.post("/api/tasks/bulk", status_code=201)
def bulk_add_tasks(items: list[BulkTaskItem]):
    added = 0
    for item in items:
        if not item.text.strip():
            continue
        task = Task(
            text=item.text.strip(),
            category=item.category,
            due_date=item.due_date,
            status="todo" if item.category else "inbox",
        )
        deps.app_data.tasks.append(task)
        added += 1
    if added:
        save_data_bg(deps.app_data)
    return {"added": added}


@router.get("/api/dashboard-order")
def get_dashboard_order():
    return {"order": deps.app_data.dashboard_order}


@router.post("/api/dashboard-order")
def set_dashboard_order(body: DashboardOrderIn):
    valid_ids = {t.id for t in deps.app_data.tasks}
    deps.app_data.dashboard_order = [i for i in body.order if i in valid_ids]
    save_data_bg(deps.app_data)
    return {"ok": True}


@router.get("/api/tasks-order")
def get_tasks_order():
    return {"order": deps.app_data.tasks_order}


@router.post("/api/tasks-order")
def set_tasks_order(body: DashboardOrderIn):
    valid_ids = {t.id for t in deps.app_data.tasks}
    deps.app_data.tasks_order = [i for i in body.order if i in valid_ids]
    save_data_bg(deps.app_data)
    return {"ok": True}


@router.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: str):
    idx = deps.find_task_idx(task_id)
    deps.app_data.tasks.pop(idx)
    save_data_bg(deps.app_data)


# ── /api/sort ─────────────────────────────────────────────────────────────────


@router.post("/api/sort")
def sort_tasks():
    from core import ai

    inbox_tasks = [t for t in deps.app_data.tasks if t.status == "inbox"]
    if not inbox_tasks:
        return {"sorted": 0, "message": "inbox にタスクがありません"}

    cfg = deps.load_config()
    backend = cfg.get("sort_backend", "auto")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

    try:
        if backend == "ollama" or (
            backend == "auto"
            and ai.ollama_is_running(cfg.get("ollama_host", "http://localhost:11434"))
        ):
            sorted_tasks = ai.sort_with_ollama(
                copy.deepcopy(inbox_tasks),
                model=cfg.get("ollama_model", "phi4"),
                host=cfg.get("ollama_host", "http://localhost:11434"),
            )
        elif backend == "gemini" or (backend == "auto" and gemini_key):
            if not gemini_key:
                raise HTTPException(400, "GEMINI_API_KEY が設定されていません")
            sorted_tasks = ai.sort_with_gemini(copy.deepcopy(inbox_tasks), gemini_key)
        elif backend == "anthropic" or (backend == "auto" and anthropic_key):
            if not anthropic_key:
                raise HTTPException(400, "ANTHROPIC_API_KEY が設定されていません")
            sorted_tasks = ai.sort_with_anthropic(
                copy.deepcopy(inbox_tasks), anthropic_key
            )
        else:
            raise HTTPException(400, "利用可能な AI バックエンドがありません")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

    id_to_sorted = {t.id: t for t in sorted_tasks}
    for task in deps.app_data.tasks:
        if task.id in id_to_sorted:
            s = id_to_sorted[task.id]
            task.status = s.status
            task.category = s.category
            if s.due_date and not task.due_date:
                task.due_date = s.due_date

    ai.update_few_shot(deps.app_data)
    save_data_bg(deps.app_data)
    return {"sorted": len(sorted_tasks)}


# ── /api/suggest-tags / apply-tags ───────────────────────────────────────────


@router.post("/api/suggest-tags")
def suggest_tags(body: AiKeyIn = AiKeyIn()):
    from core import ai

    gemini_key = body.api_key or os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        raise HTTPException(400, "GEMINI_API_KEY が設定されていません")
    try:
        suggestions = ai.suggest_tags(deps.app_data, gemini_key)
    except Exception as e:
        raise HTTPException(500, str(e))
    return {"suggestions": suggestions}


@router.post("/api/apply-tags")
def apply_tags(body: ApplyTagsIn):
    applied = 0
    for s in body.suggestions:
        try:
            task = deps.find_task(s.id)
            task.category = s.suggested
            applied += 1
        except HTTPException:
            pass
    save_data_bg(deps.app_data)
    return {"applied": applied}


# ── /api/suggest-splits / apply-splits ───────────────────────────────────────


@router.post("/api/suggest-splits")
def suggest_splits_endpoint(body: AiKeyIn = AiKeyIn()):
    from core import ai

    gemini_key = body.api_key or os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        raise HTTPException(400, "GEMINI_API_KEY が設定されていません")
    try:
        suggestions = ai.suggest_splits(deps.app_data, gemini_key)
    except Exception as e:
        raise HTTPException(500, str(e))
    return {"suggestions": suggestions}


@router.post("/api/apply-splits")
def apply_splits(body: ApplySplitsIn):
    applied = 0
    for s in body.splits:
        try:
            task = deps.find_task(s.task_id)
            task.tags = [s.suggested_tag] + task.tags[1:]
            applied += 1
        except HTTPException:
            pass
    save_data_bg(deps.app_data)
    return {"applied": applied}


# ── /api/export/markdown ─────────────────────────────────────────────────────


@router.get("/api/export/markdown")
def export_markdown():
    todo = [t for t in deps.app_data.tasks if t.status == "todo"]
    by_cat: dict = defaultdict(list)
    for t in todo:
        by_cat[t.category or "未分類"].append(t)

    lines = ["# ZzzMemo タスクリスト\n"]
    for cat, tasks in sorted(by_cat.items()):
        lines.append(f"## {cat}\n")
        for t in tasks:
            sub = f" `{t.tags[0]}`" if t.tags else ""
            lines.append(f"- [ ] {t.text}{sub}")
        lines.append("")

    return PlainTextResponse(
        "\n".join(lines),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=tasks.md"},
    )
