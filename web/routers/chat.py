"""web/routers/chat.py — /api/chat/*"""

from __future__ import annotations

import json
import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from web import deps

router = APIRouter()


class ChatIn(BaseModel):
    message: str
    api_key: Optional[str] = None


@router.post("/api/chat")
def chat_endpoint(body: ChatIn):
    from core import chat as chat_mod

    api_key = body.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            400, "GEMINI_API_KEY が設定されていません。設定タブで入力してください。"
        )
    try:
        text, actions = chat_mod.chat(body.message, deps.app_data, api_key)
    except Exception as e:
        raise HTTPException(500, str(e))
    return {"message": text, "actions": actions}


@router.post("/api/chat/stream")
def chat_stream_endpoint(body: ChatIn):
    from core import chat as chat_mod

    api_key = body.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            400, "GEMINI_API_KEY が設定されていません。設定タブで入力してください。"
        )

    def generate():
        try:
            for event in chat_mod.chat_stream(body.message, deps.app_data, api_key):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/api/chat/briefing")
def chat_briefing_endpoint(body: ChatIn):
    from core import chat as chat_mod

    api_key = body.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            400, "GEMINI_API_KEY が設定されていません。設定タブで入力してください。"
        )

    def generate():
        try:
            for event in chat_mod.briefing_stream(deps.app_data, api_key):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/api/chat/clear", status_code=204)
def clear_chat():
    from core import chat as chat_mod

    chat_mod.clear_history()
