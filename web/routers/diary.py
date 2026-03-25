"""web/routers/diary.py — /api/diary/*, /api/writing/suggest"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.models import DiaryEntry
from core.storage import load_diary, save_diary_bg
from web import deps

router = APIRouter()


# ── Pydantic スキーマ ─────────────────────────────────────────────────────────


class DiaryEntryIn(BaseModel):
    date_str: str
    content: str
    referenced_task_ids: list[str] = []


class ChatIn(BaseModel):
    message: str
    api_key: Optional[str] = None


class WritingSuggestIn(BaseModel):
    content: str
    mode: str  # "diary" | "blog"
    extra: dict = {}
    api_key: Optional[str] = None


# ── /api/diary ────────────────────────────────────────────────────────────────


@router.get("/api/diary")
def list_diaries():
    diary = load_diary()
    return {"dates": sorted(diary.entries.keys(), reverse=True)}


@router.get("/api/diary/{date_str}")
def get_diary(date_str: str):
    diary = load_diary()
    if date_str not in diary.entries:
        raise HTTPException(404, "日記が見つかりません")
    return diary.entries[date_str].model_dump()


@router.post("/api/diary")
def save_diary_entry(body: DiaryEntryIn):
    diary = load_diary()
    now = datetime.now()
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


@router.post("/api/diary/generate/{date_str}")
def generate_diary_draft(date_str: str, body: ChatIn):
    from core import writing as writing_mod

    api_key = body.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(400, "GEMINI_API_KEY が設定されていません")

    completed = [
        t.model_dump()
        for t in deps.app_data.tasks
        if t.status == "done"
        and t.completed_at
        and t.completed_at.strftime("%Y-%m-%d") == date_str
    ]

    def generate():
        try:
            for event in writing_mod.diary_draft_stream(completed, date_str, api_key):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── /api/writing/suggest ─────────────────────────────────────────────────────


@router.post("/api/writing/suggest")
def writing_suggest_endpoint(body: WritingSuggestIn):
    from core import writing as writing_mod

    api_key = body.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(400, "GEMINI_API_KEY が設定されていません")

    extra = dict(body.extra)
    if body.mode == "diary" and not body.content.strip():
        date_str = extra.get("date", "")
        completed = [
            {"text": t.text, "category": t.category, "importance": t.importance}
            for t in deps.app_data.tasks
            if t.status == "done"
            and t.completed_at
            and t.completed_at.strftime("%Y-%m-%d") == date_str
        ]
        extra["tasks"] = completed

    def generate():
        try:
            for event in writing_mod.writing_suggest_stream(
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
