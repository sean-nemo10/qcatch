"""web/server.py — FastAPI サーバー・API ルート定義"""

from __future__ import annotations

import copy
import os
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.models import (
    AppData,
    Category,
    ChecklistItem,
    ChecklistTemplate,
    RecurringRule,
    Task,
)
from core import storage
from core.storage import load_data, save_data, siphon_inbox

# パス解決
if getattr(sys, "frozen", False):
    _BASE_DIR = Path(sys.executable).parent
else:
    _BASE_DIR = Path(__file__).parent.parent

_STATIC_DIR = _BASE_DIR / "web" / "static"
_CONFIG_FILE = _BASE_DIR / "qcatch_config.json"

CATEGORIES: list[Category] = ["仕事", "プライベート", "買い物", "学習", "その他"]

app = FastAPI(title="qcatch")

# ── 静的ファイル配信 ──────────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/", response_class=FileResponse)
def index():
    return FileResponse(str(_STATIC_DIR / "index.html"))


# ── 起動イベント ──────────────────────────────────────────────────────────────

_app_data: AppData = AppData()


@app.on_event("startup")
def startup():
    global _app_data
    _app_data, stats = storage.initialize()
    print(
        f"[qcatch] 起動完了 — 移行:{stats['migrated']} 吸い上げ:{stats['siphoned']} 定期:{stats['recurring']}"
    )


# ── リクエスト/レスポンス スキーマ ───────────────────────────────────────────


class TaskIn(BaseModel):
    text: str
    category: Optional[Category] = None


class TaskPatch(BaseModel):
    status: Optional[str] = None
    category: Optional[Category] = None
    tags: Optional[list[str]] = None
    text: Optional[str] = None


class ChecklistIn(BaseModel):
    name: str
    items: list[str] = []
    due_date: Optional[datetime] = None


class ChecklistPatch(BaseModel):
    name: Optional[str] = None
    due_date: Optional[datetime] = None  # None を明示的に送ると期日クリア


class ChecklistItemPatch(BaseModel):
    item_index: int
    done: bool


class ChecklistReset(BaseModel):
    reset: bool = True


class RecurringIn(BaseModel):
    text: str
    category: Optional[Category] = None
    frequency: str  # daily | weekly | monthly
    days_of_week: list[int] = []
    day_of_month: Optional[int] = None


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


class ConfigIn(BaseModel):
    sort_backend: Optional[str] = None
    ollama_model: Optional[str] = None
    ollama_host: Optional[str] = None


# ── /api/tasks ────────────────────────────────────────────────────────────────


@app.get("/api/tasks")
def get_tasks(status: Optional[str] = None):
    """タスク一覧。status パラメータでフィルタ可（カンマ区切り複数可）。"""
    siphon_inbox(_app_data)
    tasks = _app_data.tasks
    if status:
        statuses = status.split(",")
        tasks = [t for t in tasks if t.status in statuses]
    return {"tasks": [t.model_dump() for t in tasks]}


@app.post("/api/tasks", status_code=201)
def add_task(body: TaskIn):
    """タスクを inbox として追加。"""
    task = Task(text=body.text, category=body.category)
    _app_data.tasks.append(task)
    save_data(_app_data)
    return task.model_dump()


@app.patch("/api/tasks/{task_id}")
def update_task(task_id: str, body: TaskPatch):
    """タスクのステータス・カテゴリを変更。"""
    task = _find_task(task_id)
    if body.status:
        if body.status not in ("inbox", "todo", "done", "trashed"):
            raise HTTPException(400, "invalid status")
        task.status = body.status
        if body.status == "done":
            task.completed_at = datetime.now()
        elif body.status in ("inbox", "todo", "trashed"):
            task.completed_at = None
    if body.category is not None:
        task.category = body.category
    if body.tags is not None:
        task.tags = body.tags
    if body.text is not None and body.text.strip():
        task.text = body.text.strip()
    save_data(_app_data)
    return task.model_dump()


@app.post("/api/tasks/bulk-complete")
def bulk_complete(ids: list[str]):
    """複数タスクを一括完了。"""
    now = datetime.now()
    updated = []
    for tid in ids:
        try:
            task = _find_task(tid)
            task.status = "done"
            task.completed_at = now
            updated.append(task.model_dump())
        except HTTPException:
            pass
    save_data(_app_data)
    return {"updated": updated}


@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: str):
    """タスクを完全削除（ゴミ箱からの完全削除用）。"""
    idx = _find_task_idx(task_id)
    _app_data.tasks.pop(idx)
    save_data(_app_data)


# ── /api/sort ─────────────────────────────────────────────────────────────────


@app.post("/api/sort")
def sort_tasks():
    """inbox タスクを AI で分類して todo に移動。"""
    from core import ai
    import json

    inbox_tasks = [t for t in _app_data.tasks if t.status == "inbox"]
    if not inbox_tasks:
        return {"sorted": 0, "message": "inbox にタスクがありません"}

    cfg = _load_config()
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

    # 分類結果を元のタスクに適用（ID で照合）
    id_to_sorted = {t.id: t for t in sorted_tasks}
    for task in _app_data.tasks:
        if task.id in id_to_sorted:
            s = id_to_sorted[task.id]
            task.status = s.status
            task.category = s.category

    ai.update_few_shot(_app_data)
    save_data(_app_data)
    return {"sorted": len(sorted_tasks)}


# ── /api/checklists ───────────────────────────────────────────────────────────


@app.get("/api/checklists")
def get_checklists():
    return {"checklists": [c.model_dump() for c in _app_data.checklists]}


@app.post("/api/checklists", status_code=201)
def create_checklist(body: ChecklistIn):
    checklist = ChecklistTemplate(
        name=body.name,
        items=[ChecklistItem(text=t) for t in body.items if t.strip()],
        due_date=body.due_date,
    )
    _app_data.checklists.append(checklist)
    save_data(_app_data)
    return checklist.model_dump()


@app.patch("/api/checklists/{checklist_id}")
def patch_checklist(checklist_id: str, body: ChecklistPatch):
    """チェックリストの名前・期日を更新。"""
    cl = _find_checklist(checklist_id)
    if body.name is not None:
        cl.name = body.name
    if "due_date" in body.model_fields_set:
        cl.due_date = body.due_date
    save_data(_app_data)
    return cl.model_dump()


@app.patch("/api/checklists/{checklist_id}/items")
def update_checklist_item(checklist_id: str, body: ChecklistItemPatch):
    """チェックリストのアイテムを完了/未完了に切り替え。"""
    cl = _find_checklist(checklist_id)
    if body.item_index < 0 or body.item_index >= len(cl.items):
        raise HTTPException(400, "item_index が範囲外です")
    cl.items[body.item_index].done = body.done
    save_data(_app_data)
    return cl.model_dump()


@app.post("/api/checklists/{checklist_id}/reset")
def reset_checklist(checklist_id: str):
    """チェックリストの全アイテムを未完了にリセット。"""
    cl = _find_checklist(checklist_id)
    for item in cl.items:
        item.done = False
    save_data(_app_data)
    return cl.model_dump()


@app.post("/api/checklists/{checklist_id}/items")
def add_checklist_item(checklist_id: str, body: TaskIn):
    """チェックリストにアイテムを追加。"""
    cl = _find_checklist(checklist_id)
    cl.items.append(ChecklistItem(text=body.text))
    save_data(_app_data)
    return cl.model_dump()


@app.delete("/api/checklists/{checklist_id}/items/{item_index}", status_code=204)
def delete_checklist_item(checklist_id: str, item_index: int):
    """チェックリストのアイテムを削除。"""
    cl = _find_checklist(checklist_id)
    if item_index < 0 or item_index >= len(cl.items):
        raise HTTPException(400, "item_index が範囲外です")
    cl.items.pop(item_index)
    save_data(_app_data)


@app.delete("/api/checklists/{checklist_id}", status_code=204)
def delete_checklist(checklist_id: str):
    idx = _find_checklist_idx(checklist_id)
    _app_data.checklists.pop(idx)
    save_data(_app_data)


# ── /api/recurring ────────────────────────────────────────────────────────────


@app.get("/api/recurring")
def get_recurring():
    return {"recurring": [r.model_dump() for r in _app_data.recurring]}


@app.post("/api/recurring", status_code=201)
def create_recurring(body: RecurringIn):
    if body.frequency not in ("daily", "weekly", "monthly"):
        raise HTTPException(400, "frequency は daily / weekly / monthly のいずれか")
    rule = RecurringRule(
        text=body.text,
        category=body.category,
        frequency=body.frequency,
        days_of_week=body.days_of_week,
        day_of_month=body.day_of_month,
    )
    _app_data.recurring.append(rule)
    save_data(_app_data)
    return rule.model_dump()


@app.delete("/api/recurring/{rule_id}", status_code=204)
def delete_recurring(rule_id: str):
    idx = next((i for i, r in enumerate(_app_data.recurring) if r.id == rule_id), None)
    if idx is None:
        raise HTTPException(404, "定期ルールが見つかりません")
    _app_data.recurring.pop(idx)
    save_data(_app_data)


# ── /api/suggest-tags / apply-tags ───────────────────────────────────────────


class AiKeyIn(BaseModel):
    api_key: Optional[str] = None


@app.post("/api/suggest-tags")
def suggest_tags(body: AiKeyIn = AiKeyIn()):
    from core import ai

    gemini_key = body.api_key or os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        raise HTTPException(400, "GEMINI_API_KEY が設定されていません")
    try:
        suggestions = ai.suggest_tags(_app_data, gemini_key)
    except Exception as e:
        raise HTTPException(500, str(e))
    return {"suggestions": suggestions}


@app.post("/api/apply-tags")
def apply_tags(body: ApplyTagsIn):
    """承認されたタグ変更を適用。"""
    applied = 0
    for s in body.suggestions:
        try:
            task = _find_task(s.id)
            task.category = s.suggested
            applied += 1
        except HTTPException:
            pass
    save_data(_app_data)
    return {"applied": applied}


# ── /api/suggest-splits / apply-splits ──────────────────────────────────────


@app.post("/api/suggest-splits")
def suggest_splits_endpoint(body: AiKeyIn = AiKeyIn()):
    from core import ai

    gemini_key = body.api_key or os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        raise HTTPException(400, "GEMINI_API_KEY が設定されていません")
    try:
        suggestions = ai.suggest_splits(_app_data, gemini_key)
    except Exception as e:
        raise HTTPException(500, str(e))
    return {"suggestions": suggestions}


@app.post("/api/apply-splits")
def apply_splits(body: ApplySplitsIn):
    """承認されたサブタグを task.tags[0] に書き込む。"""
    applied = 0
    for s in body.splits:
        try:
            task = _find_task(s.task_id)
            task.tags = [s.suggested_tag] + task.tags[1:]
            applied += 1
        except HTTPException:
            pass
    save_data(_app_data)
    return {"applied": applied}


# ── /api/chat ─────────────────────────────────────────────────────────────────


class ChatIn(BaseModel):
    message: str
    api_key: Optional[str] = None  # 設定画面から渡す（env変数の代替）


@app.post("/api/chat")
def chat_endpoint(body: ChatIn):
    from core import chat as chat_mod

    api_key = body.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            400, "GEMINI_API_KEY が設定されていません。設定タブで入力してください。"
        )
    try:
        text, actions = chat_mod.chat(body.message, _app_data, api_key)
    except Exception as e:
        raise HTTPException(500, str(e))
    return {"message": text, "actions": actions}


@app.post("/api/chat/stream")
def chat_stream_endpoint(body: ChatIn):
    """Server-Sent Events でチャット応答をストリーミング。"""
    import json
    from core import chat as chat_mod

    api_key = body.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            400, "GEMINI_API_KEY が設定されていません。設定タブで入力してください。"
        )

    def generate():
        try:
            for event in chat_mod.chat_stream(body.message, _app_data, api_key):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/chat/clear", status_code=204)
def clear_chat():
    from core import chat as chat_mod

    chat_mod.clear_history()


# ── /api/config ───────────────────────────────────────────────────────────────


@app.get("/api/config")
def get_config():
    return _load_config()


@app.post("/api/config")
def update_config(body: ConfigIn):
    cfg = _load_config()
    if body.sort_backend is not None:
        if body.sort_backend not in ("auto", "ollama", "gemini", "anthropic"):
            raise HTTPException(400, "invalid sort_backend")
        cfg["sort_backend"] = body.sort_backend
    if body.ollama_model is not None:
        cfg["ollama_model"] = body.ollama_model
    if body.ollama_host is not None:
        cfg["ollama_host"] = body.ollama_host
    _save_config(cfg)
    return cfg


# ── ヘルパー ──────────────────────────────────────────────────────────────────


def _find_task(task_id: str) -> Task:
    for t in _app_data.tasks:
        if t.id == task_id:
            return t
    raise HTTPException(404, "タスクが見つかりません")


def _find_task_idx(task_id: str) -> int:
    for i, t in enumerate(_app_data.tasks):
        if t.id == task_id:
            return i
    raise HTTPException(404, "タスクが見つかりません")


def _find_checklist(checklist_id: str) -> ChecklistTemplate:
    for c in _app_data.checklists:
        if c.id == checklist_id:
            return c
    raise HTTPException(404, "チェックリストが見つかりません")


def _find_checklist_idx(checklist_id: str) -> int:
    for i, c in enumerate(_app_data.checklists):
        if c.id == checklist_id:
            return i
    raise HTTPException(404, "チェックリストが見つかりません")


def _load_config() -> dict:
    _DEFAULT = {
        "sort_backend": "auto",
        "ollama_model": "phi4",
        "ollama_host": "http://localhost:11434",
    }
    if _CONFIG_FILE.exists():
        try:
            import json

            data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
            return {**_DEFAULT, **data}
        except Exception:
            pass
    return dict(_DEFAULT)


def _save_config(cfg: dict) -> None:
    import json

    _CONFIG_FILE.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── サーバー起動 ──────────────────────────────────────────────────────────────


def run(port: int = 5000, open_browser: bool = True) -> None:
    """uvicorn でサーバーを起動し、ブラウザを開く。"""
    import uvicorn

    url = f"http://localhost:{port}"
    if open_browser:
        # サーバー起動後に少し待ってから開く
        def _open():
            import time

            time.sleep(1.2)
            webbrowser.open(url)

        threading.Thread(target=_open, daemon=True).start()

    print(f"[qcatch] サーバー起動 → {url}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
