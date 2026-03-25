"""web/routers/config.py — /api/config"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from web import deps

router = APIRouter()


class ConfigIn(BaseModel):
    sort_backend: Optional[str] = None
    ollama_model: Optional[str] = None
    ollama_host: Optional[str] = None
    google_tasklist_map: Optional[dict] = None
    sync_interval_minutes: Optional[int] = None


@router.get("/api/config")
def get_config():
    return deps.load_config()


@router.post("/api/config")
def update_config(body: ConfigIn):
    cfg = deps.load_config()
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
    if body.sync_interval_minutes is not None:
        cfg["sync_interval_minutes"] = max(5, body.sync_interval_minutes)
    deps.save_config(cfg)
    return cfg
