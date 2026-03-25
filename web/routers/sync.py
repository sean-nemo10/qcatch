"""web/routers/sync.py — /api/auth/*, /api/sync/*, /api/calendar/*, /api/tasks/{id}/sync"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from core.storage import save_data_bg
from web import deps

router = APIRouter()


class CalendarEventIn(BaseModel):
    title: str
    start_dt: str
    end_dt: str
    description: Optional[str] = ""


# ── /api/auth ─────────────────────────────────────────────────────────────────


@router.get("/api/auth/status")
def auth_status():
    from core import google_sync

    authenticated = google_sync.is_authenticated()
    has_secrets = google_sync.CLIENT_SECRETS_FILE.exists()
    return {"authenticated": authenticated, "has_client_secrets": has_secrets}


@router.get("/api/auth/login")
def auth_login():
    from core import google_sync

    try:
        url = google_sync.get_auth_url()
        return RedirectResponse(url)
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))


@router.get("/api/auth/callback")
def auth_callback(request: Request):
    from core import google_sync

    try:
        google_sync.handle_callback(str(request.url))
        return RedirectResponse(url="/?auth=success")
    except Exception as e:
        return RedirectResponse(url=f"/?auth=error&msg={str(e)[:100]}")


@router.post("/api/auth/logout", status_code=204)
def auth_logout():
    from core import google_sync

    google_sync.revoke_credentials()


@router.get("/api/auth/tasklists")
def get_tasklists():
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


# ── /api/sync ─────────────────────────────────────────────────────────────────


@router.post("/api/sync/push")
def sync_push():
    from core import google_sync

    try:
        count = google_sync.push_all(deps.app_data)
        save_data_bg(deps.app_data)
        deps.logger.info(f"sync push: {count} 件")
        return {"pushed": count}
    except RuntimeError as e:
        deps.logger.warning(f"sync push 失敗（未認証）: {e}")
        raise HTTPException(401, str(e))
    except Exception as e:
        deps.logger.error(f"sync push エラー: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@router.post("/api/sync/pull")
def sync_pull():
    from core import google_sync

    try:
        count = google_sync.pull_all(deps.app_data)
        if count:
            save_data_bg(deps.app_data)
        deps.logger.info(f"sync pull: {count} 件更新")
        return {"pulled": count}
    except RuntimeError as e:
        deps.logger.warning(f"sync pull 失敗（未認証）: {e}")
        raise HTTPException(401, str(e))
    except Exception as e:
        deps.logger.error(f"sync pull エラー: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@router.post("/api/sync")
def sync_all():
    from core import google_sync

    try:
        pushed = google_sync.push_all(deps.app_data)
        pulled = google_sync.pull_all(deps.app_data)
        if pushed or pulled:
            save_data_bg(deps.app_data)
        deps.logger.info(f"sync all: push={pushed} pull={pulled}")
        return {"pushed": pushed, "pulled": pulled}
    except RuntimeError as e:
        deps.logger.warning(f"sync all 失敗（未認証）: {e}")
        raise HTTPException(401, str(e))
    except Exception as e:
        deps.logger.error(f"sync all エラー: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@router.post("/api/calendar/add_event")
def add_calendar_event(body: CalendarEventIn):
    from core import google_sync

    if not google_sync.is_authenticated():
        raise HTTPException(
            401, "Google認証が必要です。設定タブからログインしてください。"
        )
    try:
        start_dt = datetime.fromisoformat(body.start_dt)
        end_dt = datetime.fromisoformat(body.end_dt)
        event_id = google_sync.add_calendar_event(
            body.title, start_dt, end_dt, body.description or ""
        )
        deps.logger.info(f"カレンダーイベント追加: {body.title} ({body.start_dt})")
        return {"ok": True, "event_id": event_id}
    except RuntimeError as e:
        raise HTTPException(401, str(e))
    except Exception as e:
        deps.logger.error(f"カレンダーイベント追加エラー: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@router.post("/api/tasks/{task_id}/sync")
def sync_single_task(task_id: str):
    from core import google_sync

    task = deps.find_task(task_id)
    try:
        updates = google_sync.push_task(task)
        for k, v in updates.items():
            setattr(task, k, v)
        save_data_bg(deps.app_data)
        return task.model_dump()
    except RuntimeError as e:
        raise HTTPException(401, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))
