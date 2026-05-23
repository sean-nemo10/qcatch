"""web/routers/recurring.py — /api/recurring/check (manual trigger).

CRUD for /api/recurring lives in checklists.py (existing).
"""

from __future__ import annotations

from fastapi import APIRouter

from core.storage import check_recurring, save_data_bg
from web import deps

router = APIRouter()


@router.post("/api/recurring/check")
def trigger_check():
    added = check_recurring(deps.app_data)
    if added:
        save_data_bg(deps.app_data)
    return {"added": len(added), "texts": added}
