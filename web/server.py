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

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.models import (
    AppData,
    BlogPost,
    Category,
    ChecklistItem,
    ChecklistTemplate,
    DiaryEntry,
    FlashCard,
    Importance,
    RecurringRule,
    Task,
)
from core import storage
from core.storage import (
    load_blog,
    load_data,
    load_diary,
    load_flashcards,
    promote_longterm_tasks,
    save_blog_bg,
    save_data,
    save_data_bg,
    save_diary_bg,
    save_flashcards_bg,
    siphon_inbox,
    sm2_update,
)

# localhost HTTP で OAuth2 を通すために必要
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

# パス解決
if getattr(sys, "frozen", False):
    _BASE_DIR = Path(sys.executable).parent
else:
    _BASE_DIR = Path(__file__).parent.parent

_STATIC_DIR = _BASE_DIR / "web" / "static"
_CONFIG_FILE = _BASE_DIR / "qcatch_config.json"

CATEGORIES: list[Category] = ["仕事", "プライベート", "買い物", "学習", "その他"]

app = FastAPI(title="qcatch")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 静的ファイル配信 ──────────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/", response_class=FileResponse)
def index():
    return FileResponse(str(_STATIC_DIR / "index.html"))


@app.get("/manifest.json")
def manifest():
    return FileResponse(
        str(_STATIC_DIR / "manifest.json"), media_type="application/manifest+json"
    )


@app.get("/sw.js")
def service_worker():
    return FileResponse(
        str(_STATIC_DIR / "sw.js"),
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )


# ── 起動イベント ──────────────────────────────────────────────────────────────

_app_data: AppData = AppData()


@app.on_event("startup")
def startup():
    global _app_data
    _app_data, stats = storage.initialize()
    promoted = promote_longterm_tasks(_app_data)
    if promoted:
        save_data(_app_data)
    print(
        f"[qcatch] 起動完了 — 移行:{stats['migrated']} 吸い上げ:{stats['siphoned']} "
        f"定期:{stats['recurring']} アーカイブ:{stats['archived']} 長期昇格:{promoted}"
    )


# ── リクエスト/レスポンス スキーマ ───────────────────────────────────────────


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


class ChecklistIn(BaseModel):
    name: str
    items: list[str] = []
    due_date: Optional[datetime] = None


class ChecklistPatch(BaseModel):
    name: Optional[str] = None
    due_date: Optional[datetime] = None  # None を明示的に送ると期日クリア


class ChecklistItemPatch(BaseModel):
    item_index: int
    done: Optional[bool] = None
    text: Optional[str] = None


class ChecklistReset(BaseModel):
    reset: bool = True


class RecurringIn(BaseModel):
    text: str
    category: Optional[Category] = None
    frequency: str  # daily | weekly | monthly
    days_of_week: list[int] = []
    day_of_month: Optional[int] = None


class RecurringPatch(BaseModel):
    text: Optional[str] = None
    category: Optional[Category] = None
    frequency: Optional[str] = None
    days_of_week: Optional[list[int]] = None
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
    google_tasklist_map: Optional[dict] = None  # {"仕事": "hurry", ...}


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
    status = body.status if body.status in ("inbox", "longterm") else "inbox"
    task = Task(
        text=body.text,
        category=body.category,
        due_date=body.due_date,
        importance=body.importance or "medium",
        status=status,
    )
    _app_data.tasks.append(task)
    save_data_bg(_app_data)
    return task.model_dump()


@app.patch("/api/tasks/{task_id}")
def update_task(task_id: str, body: TaskPatch):
    """タスクのステータス・カテゴリを変更。"""
    task = _find_task(task_id)
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
    save_data_bg(_app_data)
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
    save_data_bg(_app_data)
    return {"updated": updated}


class BulkTaskItem(BaseModel):
    text: str
    category: Optional[Category] = None
    due_date: Optional[datetime] = None


@app.post("/api/tasks/bulk", status_code=201)
def bulk_add_tasks(items: list[BulkTaskItem]):
    """複数タスクを一括追加。category が設定されていれば todo、なければ inbox。"""
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
        _app_data.tasks.append(task)
        added += 1
    if added:
        save_data_bg(_app_data)
    return {"added": added}


@app.get("/api/dashboard-order")
def get_dashboard_order():
    """ダッシュボードの手動並び順を返す。"""
    return {"order": _app_data.dashboard_order}


class DashboardOrderIn(BaseModel):
    order: list[str]


@app.post("/api/dashboard-order")
def set_dashboard_order(body: DashboardOrderIn):
    """ダッシュボードの手動並び順を保存する。"""
    # 存在するタスクIDのみ保持
    valid_ids = {t.id for t in _app_data.tasks}
    _app_data.dashboard_order = [i for i in body.order if i in valid_ids]
    save_data_bg(_app_data)
    return {"ok": True}


@app.get("/api/tasks-order")
def get_tasks_order():
    """タスクタブの手動並び順を返す。"""
    return {"order": _app_data.tasks_order}


@app.post("/api/tasks-order")
def set_tasks_order(body: DashboardOrderIn):
    """タスクタブの手動並び順を保存する。"""
    valid_ids = {t.id for t in _app_data.tasks}
    _app_data.tasks_order = [i for i in body.order if i in valid_ids]
    save_data_bg(_app_data)
    return {"ok": True}


@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: str):
    """タスクを完全削除（ゴミ箱からの完全削除用）。"""
    idx = _find_task_idx(task_id)
    _app_data.tasks.pop(idx)
    save_data_bg(_app_data)


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
            if s.due_date and not task.due_date:  # AIが検出した場合のみ上書き
                task.due_date = s.due_date

    ai.update_few_shot(_app_data)
    save_data_bg(_app_data)
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
    save_data_bg(_app_data)
    return checklist.model_dump()


@app.patch("/api/checklists/{checklist_id}")
def patch_checklist(checklist_id: str, body: ChecklistPatch):
    """チェックリストの名前・期日を更新。"""
    cl = _find_checklist(checklist_id)
    if body.name is not None:
        cl.name = body.name
    if "due_date" in body.model_fields_set:
        cl.due_date = body.due_date
    save_data_bg(_app_data)
    return cl.model_dump()


@app.patch("/api/checklists/{checklist_id}/items")
def update_checklist_item(checklist_id: str, body: ChecklistItemPatch):
    """チェックリストのアイテムを更新（完了状態またはテキスト）。"""
    cl = _find_checklist(checklist_id)
    if body.item_index < 0 or body.item_index >= len(cl.items):
        raise HTTPException(400, "item_index が範囲外です")
    if body.done is not None:
        cl.items[body.item_index].done = body.done
    if body.text is not None and body.text.strip():
        cl.items[body.item_index].text = body.text.strip()
    save_data_bg(_app_data)
    return cl.model_dump()


@app.post("/api/checklists/{checklist_id}/reset")
def reset_checklist(checklist_id: str):
    """チェックリストの全アイテムを未完了にリセット。"""
    cl = _find_checklist(checklist_id)
    for item in cl.items:
        item.done = False
    save_data_bg(_app_data)
    return cl.model_dump()


@app.post("/api/checklists/{checklist_id}/items")
def add_checklist_item(checklist_id: str, body: TaskIn):
    """チェックリストにアイテムを追加。"""
    cl = _find_checklist(checklist_id)
    cl.items.append(ChecklistItem(text=body.text))
    save_data_bg(_app_data)
    return cl.model_dump()


@app.delete("/api/checklists/{checklist_id}/items/{item_index}", status_code=204)
def delete_checklist_item(checklist_id: str, item_index: int):
    """チェックリストのアイテムを削除。"""
    cl = _find_checklist(checklist_id)
    if item_index < 0 or item_index >= len(cl.items):
        raise HTTPException(400, "item_index が範囲外です")
    cl.items.pop(item_index)
    save_data_bg(_app_data)


@app.delete("/api/checklists/{checklist_id}", status_code=204)
def delete_checklist(checklist_id: str):
    idx = _find_checklist_idx(checklist_id)
    _app_data.checklists.pop(idx)
    save_data_bg(_app_data)


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
    save_data_bg(_app_data)
    return rule.model_dump()


@app.patch("/api/recurring/{rule_id}")
def update_recurring(rule_id: str, body: RecurringPatch):
    rule = next((r for r in _app_data.recurring if r.id == rule_id), None)
    if rule is None:
        raise HTTPException(404, "定期ルールが見つかりません")
    if body.text is not None and body.text.strip():
        rule.text = body.text.strip()
    if "category" in body.model_fields_set:
        rule.category = body.category
    if body.frequency is not None:
        if body.frequency not in ("daily", "weekly", "monthly"):
            raise HTTPException(400, "frequency は daily / weekly / monthly のいずれか")
        rule.frequency = body.frequency
    if body.days_of_week is not None:
        rule.days_of_week = body.days_of_week
    if body.day_of_month is not None:
        rule.day_of_month = body.day_of_month
    save_data_bg(_app_data)
    return rule.model_dump()


@app.delete("/api/recurring/{rule_id}", status_code=204)
def delete_recurring(rule_id: str):
    idx = next((i for i, r in enumerate(_app_data.recurring) if r.id == rule_id), None)
    if idx is None:
        raise HTTPException(404, "定期ルールが見つかりません")
    _app_data.recurring.pop(idx)
    save_data_bg(_app_data)


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
    save_data_bg(_app_data)
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
    save_data_bg(_app_data)
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


@app.post("/api/chat/briefing")
def chat_briefing_endpoint(body: ChatIn):
    """朝のブリーフィング: 直近24h完了実績 + todo タスクをコンテキストにした専用SSE。"""
    import json
    from core import chat as chat_mod

    api_key = body.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            400, "GEMINI_API_KEY が設定されていません。設定タブで入力してください。"
        )

    def generate():
        try:
            for event in chat_mod.briefing_stream(_app_data, api_key):
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
    if body.google_tasklist_map is not None:
        cfg["google_tasklist_map"] = body.google_tasklist_map
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


# ── /api/diary ────────────────────────────────────────────────────────────────


class DiaryEntryIn(BaseModel):
    date_str: str
    content: str
    referenced_task_ids: list[str] = []


@app.get("/api/diary")
def list_diaries():
    """日記がある日付一覧を返す（降順）。"""
    diary = load_diary()
    return {"dates": sorted(diary.entries.keys(), reverse=True)}


@app.get("/api/diary/{date_str}")
def get_diary(date_str: str):
    """指定日の日記を返す。"""
    diary = load_diary()
    if date_str not in diary.entries:
        raise HTTPException(404, "日記が見つかりません")
    return diary.entries[date_str].model_dump()


@app.post("/api/diary")
def save_diary_entry(body: DiaryEntryIn):
    """日記を保存・更新する。"""
    from datetime import datetime as dt

    diary = load_diary()
    now = dt.now()
    if body.date_str in diary.entries:
        entry = diary.entries[body.date_str]
        entry.content = body.content
        entry.referenced_task_ids = body.referenced_task_ids
        entry.updated_at = now
    else:
        entry = DiaryEntry(
            date_str=body.date_str,
            content=body.content,
            referenced_task_ids=body.referenced_task_ids,
            created_at=now,
            updated_at=now,
        )
        diary.entries[body.date_str] = entry
    save_diary_bg(diary)
    return entry.model_dump()


@app.post("/api/diary/generate/{date_str}")
def generate_diary_draft(date_str: str, body: ChatIn):
    """指定日の完了タスクをもとに日記の下書きをSSEストリーミングで生成する。"""
    import json
    from core import chat as chat_mod

    api_key = body.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(400, "GEMINI_API_KEY が設定されていません")

    # 該当日の完了タスクを取得
    completed = [
        t.model_dump()
        for t in _app_data.tasks
        if t.status == "done"
        and t.completed_at
        and t.completed_at.strftime("%Y-%m-%d") == date_str
    ]

    def generate():
        try:
            for event in chat_mod.diary_draft_stream(completed, date_str, api_key):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── /api/writing/suggest ─────────────────────────────────────────────────────


class WritingSuggestIn(BaseModel):
    content: str
    mode: str  # "diary" | "blog"
    extra: dict = {}
    api_key: Optional[str] = None


@app.post("/api/writing/suggest")
def writing_suggest_endpoint(body: WritingSuggestIn):
    """ユーザーが書いた文章に対してAIが提案をSSEストリーミングで返す。
    日記モードで content が空の場合、その日の完了タスクから書くべき話題を提案する。"""
    import json
    from core import chat as chat_mod

    api_key = body.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(400, "GEMINI_API_KEY が設定されていません")

    extra = dict(body.extra)
    # 日記モードで本文が空 → その日の完了タスクを extra に注入
    if body.mode == "diary" and not body.content.strip():
        date_str = extra.get("date", "")
        completed = [
            {"text": t.text, "category": t.category, "importance": t.importance}
            for t in _app_data.tasks
            if t.status == "done"
            and t.completed_at
            and t.completed_at.strftime("%Y-%m-%d") == date_str
        ]
        extra["tasks"] = completed

    def generate():
        try:
            for event in chat_mod.writing_suggest_stream(
                body.content, body.mode, extra, api_key
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── /api/blog ─────────────────────────────────────────────────────────────────


class BlogPostIn(BaseModel):
    title: str
    tags: list[str] = []
    content: str


class BlogPostPatch(BaseModel):
    title: Optional[str] = None
    tags: Optional[list[str]] = None
    content: Optional[str] = None


@app.get("/api/blog")
def list_blog_posts():
    """ブログ記事一覧（降順）。本文は先頭100文字のみ。"""
    blog = load_blog()
    return {
        "posts": [
            {**p.model_dump(exclude={"content"}), "preview": p.content[:100]}
            for p in sorted(blog.posts, key=lambda p: p.updated_at, reverse=True)
        ]
    }


@app.get("/api/blog/{post_id}")
def get_blog_post(post_id: str):
    blog = load_blog()
    post = next((p for p in blog.posts if p.id == post_id), None)
    if not post:
        raise HTTPException(404, "ブログ記事が見つかりません")
    return post.model_dump()


@app.post("/api/blog", status_code=201)
def create_blog_post(body: BlogPostIn):
    blog = load_blog()
    post = BlogPost(title=body.title, tags=body.tags, content=body.content)
    blog.posts.append(post)
    save_blog_bg(blog)
    return post.model_dump()


@app.patch("/api/blog/{post_id}")
def update_blog_post(post_id: str, body: BlogPostPatch):
    from datetime import datetime as dt

    blog = load_blog()
    post = next((p for p in blog.posts if p.id == post_id), None)
    if not post:
        raise HTTPException(404, "ブログ記事が見つかりません")
    if body.title is not None:
        post.title = body.title
    if body.tags is not None:
        post.tags = body.tags
    if body.content is not None:
        post.content = body.content
    post.updated_at = dt.now()
    save_blog_bg(blog)
    return post.model_dump()


@app.delete("/api/blog/{post_id}", status_code=204)
def delete_blog_post(post_id: str):
    blog = load_blog()
    idx = next((i for i, p in enumerate(blog.posts) if p.id == post_id), None)
    if idx is None:
        raise HTTPException(404, "ブログ記事が見つかりません")
    blog.posts.pop(idx)
    save_blog_bg(blog)


# ── /api/flashcards ───────────────────────────────────────────────────────────


class FlashCardIn(BaseModel):
    front: str
    back: str
    example: str = ""
    source: str = "manual"
    source_ref: str = ""


class FlashCardReview(BaseModel):
    quality: int  # 0=忘れた, 1=難しい, 2=完璧


@app.get("/api/flashcards")
def list_flashcards():
    deck = load_flashcards()
    return {"cards": [c.model_dump() for c in deck.cards]}


@app.get("/api/flashcards/due")
def due_flashcards():
    """今日復習すべきカードを返す。"""
    from datetime import date

    today = date.today().isoformat()
    deck = load_flashcards()
    due = [c for c in deck.cards if c.next_review <= today]
    return {"cards": [c.model_dump() for c in due]}


@app.post("/api/flashcards", status_code=201)
def create_flashcard(body: FlashCardIn):
    deck = load_flashcards()
    card = FlashCard(
        front=body.front,
        back=body.back,
        example=body.example,
        source=body.source,
        source_ref=body.source_ref,
    )
    deck.cards.append(card)
    save_flashcards_bg(deck)
    return card.model_dump()


@app.patch("/api/flashcards/{card_id}/review")
def review_flashcard(card_id: str, body: FlashCardReview):
    deck = load_flashcards()
    card = next((c for c in deck.cards if c.id == card_id), None)
    if not card:
        raise HTTPException(404, "カードが見つかりません")
    sm2_update(card, body.quality)
    save_flashcards_bg(deck)
    return card.model_dump()


@app.delete("/api/flashcards/{card_id}", status_code=204)
def delete_flashcard(card_id: str):
    deck = load_flashcards()
    idx = next((i for i, c in enumerate(deck.cards) if c.id == card_id), None)
    if idx is None:
        raise HTTPException(404, "カードが見つかりません")
    deck.cards.pop(idx)
    save_flashcards_bg(deck)


# ── /api/lang ─────────────────────────────────────────────────────────────────


class LangPracticeIn(BaseModel):
    date_str: str
    api_key: Optional[str] = None


class LangCorrectIn(BaseModel):
    user_english: str
    context: str = ""
    api_key: Optional[str] = None


class LangDiscussIn(BaseModel):
    practice_text: str
    user_answer: str
    correction: str
    follow_up: str
    history: list = []
    api_key: Optional[str] = None


@app.post("/api/lang/practice")
def lang_practice_endpoint(body: LangPracticeIn):
    """今日のタスク・日記を素材に英語練習問題をSSEストリーミングで生成する。"""
    import json
    from core import chat as chat_mod

    api_key = body.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(400, "GEMINI_API_KEY が設定されていません")

    tasks = [
        {"text": t.text, "category": t.category}
        for t in _app_data.tasks
        if t.status == "done"
        and t.completed_at
        and t.completed_at.strftime("%Y-%m-%d") == body.date_str
    ]

    diary = load_diary()
    diary_content = ""
    if body.date_str in diary.entries:
        diary_content = diary.entries[body.date_str].content

    def generate():
        try:
            for event in chat_mod.lang_practice_stream(
                tasks, diary_content, body.date_str, api_key
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/lang/correct")
def lang_correct_endpoint(body: LangCorrectIn):
    """ユーザーの英文を添削・フレーズ提案するSSEストリーミング。"""
    import json
    from core import chat as chat_mod

    api_key = body.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(400, "GEMINI_API_KEY が設定されていません")

    def generate():
        try:
            for event in chat_mod.lang_correct_stream(
                body.user_english, body.context, api_key
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/lang/discuss")
def lang_discuss_endpoint(body: LangDiscussIn):
    """添削後のフォローアップ議論をSSEストリーミングで返す。"""
    import json
    from core import chat as chat_mod

    api_key = body.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(400, "GEMINI_API_KEY が設定されていません")

    def generate():
        try:
            for event in chat_mod.lang_discuss_stream(
                body.practice_text,
                body.user_answer,
                body.correction,
                body.follow_up,
                body.history,
                api_key,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── /api/auth (Google OAuth2) ─────────────────────────────────────────────────


@app.get("/api/auth/status")
def auth_status():
    """Google 認証状態を返す。"""
    from core import google_sync

    authenticated = google_sync.is_authenticated()
    has_secrets = google_sync.CLIENT_SECRETS_FILE.exists()
    return {"authenticated": authenticated, "has_client_secrets": has_secrets}


@app.get("/api/auth/login")
def auth_login():
    """Google OAuth2 認証ページにリダイレクトする。"""
    from core import google_sync
    from fastapi.responses import RedirectResponse

    try:
        url = google_sync.get_auth_url()
        return RedirectResponse(url)
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))


@app.get("/api/auth/callback")
def auth_callback(request: Request):
    """OAuth2 コールバック。トークンを保存して SPA に戻る。"""
    from core import google_sync
    from fastapi.responses import RedirectResponse

    try:
        google_sync.handle_callback(str(request.url))
        return RedirectResponse(url="/?auth=success")
    except Exception as e:
        return RedirectResponse(url=f"/?auth=error&msg={str(e)[:100]}")


@app.post("/api/auth/logout", status_code=204)
def auth_logout():
    """保存済みトークンを削除する。"""
    from core import google_sync

    google_sync.revoke_credentials()


@app.get("/api/auth/tasklists")
def get_tasklists():
    """Google Tasks の既存リスト一覧を返す。"""
    from core import google_sync

    creds = google_sync.get_credentials()
    if not creds:
        raise HTTPException(401, "Google 未認証")
    try:
        from googleapiclient.discovery import build

        service = build("tasks", "v1", credentials=creds)
        items = service.tasklists().list(maxResults=50).execute().get("items", [])
        return {"lists": [{"id": tl["id"], "title": tl["title"]} for tl in items]}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── /api/sync (Google 同期) ───────────────────────────────────────────────────


@app.post("/api/sync/push")
def sync_push():
    """due_date を持つ全タスクを Google Calendar / Tasks に同期（push）。"""
    from core import google_sync

    try:
        count = google_sync.push_all(_app_data)
        save_data_bg(_app_data)
        return {"pushed": count}
    except RuntimeError as e:
        raise HTTPException(401, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/sync/pull")
def sync_pull():
    """Google Tasks の完了状態を qcatch に反映（pull）。"""
    from core import google_sync

    try:
        count = google_sync.pull_all(_app_data)
        if count:
            save_data_bg(_app_data)
        return {"pulled": count}
    except RuntimeError as e:
        raise HTTPException(401, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/sync")
def sync_all():
    """push + pull を一括実行する。"""
    from core import google_sync

    try:
        pushed = google_sync.push_all(_app_data)
        pulled = google_sync.pull_all(_app_data)
        if pushed or pulled:
            save_data_bg(_app_data)
        return {"pushed": pushed, "pulled": pulled}
    except RuntimeError as e:
        raise HTTPException(401, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/tasks/{task_id}/sync")
def sync_single_task(task_id: str):
    """単一タスクを Google に同期する。"""
    from core import google_sync

    task = _find_task(task_id)
    try:
        updates = google_sync.push_task(task)
        for k, v in updates.items():
            setattr(task, k, v)
        save_data_bg(_app_data)
        return task.model_dump()
    except RuntimeError as e:
        raise HTTPException(401, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


# ── /api/export ───────────────────────────────────────────────────────────────


@app.get("/api/export/markdown")
def export_markdown():
    """todo タスクをカテゴリ別 Markdown で返す。"""
    from collections import defaultdict

    todo = [t for t in _app_data.tasks if t.status == "todo"]
    by_cat: dict = defaultdict(list)
    for t in todo:
        by_cat[t.category or "未分類"].append(t)

    lines = ["# qcatch タスクリスト\n"]
    for cat, tasks in sorted(by_cat.items()):
        lines.append(f"## {cat}\n")
        for t in tasks:
            sub = f" `{t.tags[0]}`" if t.tags else ""
            lines.append(f"- [ ] {t.text}{sub}")
        lines.append("")

    content = "\n".join(lines)
    from fastapi.responses import PlainTextResponse

    return PlainTextResponse(
        content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=tasks.md"},
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
