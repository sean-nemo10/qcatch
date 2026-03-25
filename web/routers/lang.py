"""web/routers/lang.py — /api/lang/*"""

from __future__ import annotations

import json
import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.storage import load_diary
from web import deps

router = APIRouter()


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


@router.post("/api/lang/practice")
def lang_practice_endpoint(body: LangPracticeIn):
    from core import lang as lang_mod

    api_key = body.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(400, "GEMINI_API_KEY が設定されていません")

    tasks = [
        {"text": t.text, "category": t.category}
        for t in deps.app_data.tasks
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
            for event in lang_mod.lang_practice_stream(
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


@router.post("/api/lang/correct")
def lang_correct_endpoint(body: LangCorrectIn):
    from core import lang as lang_mod

    api_key = body.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(400, "GEMINI_API_KEY が設定されていません")

    def generate():
        try:
            for event in lang_mod.lang_correct_stream(
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


@router.post("/api/lang/discuss")
def lang_discuss_endpoint(body: LangDiscussIn):
    from core import lang as lang_mod

    api_key = body.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(400, "GEMINI_API_KEY が設定されていません")

    def generate():
        try:
            for event in lang_mod.lang_discuss_stream(
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
