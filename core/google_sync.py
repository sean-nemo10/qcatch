"""core/google_sync.py — Google Calendar / Google Tasks 連携"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

# PyInstaller / 通常実行 両対応
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent.parent

CLIENT_SECRETS_FILE = BASE_DIR / "client_secret.json"
TOKEN_FILE = BASE_DIR / "data" / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
]

REDIRECT_URI = "http://localhost:5000/api/auth/callback"

_pending_flow = None  # get_auth_url() → handle_callback() 間で Flow を保持


# ── 認証 ─────────────────────────────────────────────────────────────────────


def is_authenticated() -> bool:
    return get_credentials() is not None


def get_credentials():
    """token.json からクレデンシャルを取得。期限切れなら自動リフレッシュ。未認証なら None。"""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request as GoogleRequest
    except ImportError:
        return None

    creds = None
    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        except Exception:
            return None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(GoogleRequest())
                TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
            except Exception:
                return None
        else:
            return None
    return creds


def get_auth_url() -> str:
    """OAuth2 認証 URL を生成して返す。"""
    global _pending_flow
    if not CLIENT_SECRETS_FILE.exists():
        raise FileNotFoundError(
            "client_secret.json が見つかりません。"
            "GCP Console でダウンロードしてプロジェクトルートに配置してください。"
        )
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_secrets_file(str(CLIENT_SECRETS_FILE), scopes=SCOPES)
    flow.redirect_uri = REDIRECT_URI
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",  # リフレッシュトークンを確実に取得
    )
    _pending_flow = flow  # code_verifier を引き継ぐため保持
    return auth_url


def handle_callback(authorization_response: str) -> None:
    """OAuth2 コールバック URL を受け取ってトークンを保存する。"""
    global _pending_flow
    import os

    if _pending_flow is None:
        raise RuntimeError("認証フローが見つかりません。再度ログインしてください。")

    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    _pending_flow.fetch_token(authorization_response=authorization_response)
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(_pending_flow.credentials.to_json(), encoding="utf-8")
    _pending_flow = None


def revoke_credentials() -> None:
    """保存済みトークンを削除して未認証状態に戻す。"""
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()


# ── 同期ロジック ─────────────────────────────────────────────────────────────


def _is_time_based(due_date: datetime) -> bool:
    """時刻が 00:00 以外 → Calendar イベント、00:00 → Tasks に同期。"""
    return due_date.hour != 0 or due_date.minute != 0


def push_task(task) -> dict:
    """タスク 1 件を Google に同期。戻り値: Task に適用するフィールド更新辞書。"""
    creds = get_credentials()
    if not creds:
        raise RuntimeError(
            "Google 認証が必要です。/api/auth/login にアクセスしてください。"
        )
    if not task.due_date:
        return {}

    if _is_time_based(task.due_date):
        event_id = _sync_to_calendar(creds, task)
        return {"google_event_id": event_id, "google_task_id": None}
    else:
        task_id = _sync_to_tasks(creds, task)
        return {"google_task_id": task_id, "google_event_id": None}


def delete_from_google(task) -> None:
    """Google 側のイベント/タスクを削除する（ゴミ箱移動時などに呼ぶ）。"""
    creds = get_credentials()
    if not creds:
        return
    if task.google_event_id:
        _delete_calendar_event(creds, task.google_event_id)
    if task.google_task_id:
        _delete_google_task(creds, task.google_task_id)


def push_all(data) -> int:
    """due_date を持つ全タスクを Google に同期。戻り値: 同期したタスク数。"""
    creds = get_credentials()
    if not creds:
        raise RuntimeError("Google 認証が必要です。")

    count = 0
    for task in data.tasks:
        if task.status == "trashed" or not task.due_date:
            continue
        try:
            updates = push_task(task)
            for k, v in updates.items():
                setattr(task, k, v)
            count += 1
        except Exception:
            pass
    return count


def pull_all(data) -> int:
    """Google Tasks の完了状態を qcatch に反映する。戻り値: 変更されたタスク数。"""
    creds = get_credentials()
    if not creds:
        raise RuntimeError("Google 認証が必要です。")

    try:
        from googleapiclient.discovery import build
    except ImportError:
        raise RuntimeError(
            "google-api-python-client が未インストールです。pip install google-api-python-client を実行してください。"
        )

    service = build("tasks", "v1", credentials=creds)
    task_map = {t.id: t for t in data.tasks}
    count = 0

    lists = service.tasklists().list(maxResults=30).execute().get("items", [])
    for tl in lists:
        items = (
            service.tasks()
            .list(
                tasklist=tl["id"], showCompleted=True, showHidden=True, maxResults=100
            )
            .execute()
            .get("items", [])
        )
        for gt in items:
            notes = gt.get("notes", "")
            if not notes.startswith("qcatch_id:"):
                continue
            local_id = notes.replace("qcatch_id:", "").strip()
            local_task = task_map.get(local_id)
            if not local_task:
                continue
            # Google Tasks で完了 → qcatch でも完了
            if gt.get("status") == "completed" and local_task.status != "done":
                local_task.status = "done"
                local_task.completed_at = datetime.now()
                count += 1

    return count


# ── Calendar ─────────────────────────────────────────────────────────────────


def get_calendar_events(days: int = 1) -> list[dict]:
    """今日から days 日分の Google Calendar イベントを取得する。"""
    creds = get_credentials()
    if not creds:
        raise RuntimeError(
            "Google 認証が必要です。/api/auth/login にアクセスしてください。"
        )
    from googleapiclient.discovery import build
    from datetime import timedelta

    service = build("calendar", "v3", credentials=creds)
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)

    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=end.isoformat(),
            maxResults=50,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = []
    for ev in result.get("items", []):
        events.append(
            {
                "title": ev.get("summary", "（タイトルなし）"),
                "start": ev["start"].get("dateTime") or ev["start"].get("date", ""),
                "end": ev["end"].get("dateTime") or ev["end"].get("date", ""),
                "description": ev.get("description", ""),
            }
        )
    return events


def add_calendar_event(
    title: str, start_dt: datetime, end_dt: datetime, description: str = ""
) -> str:
    """Google Calendar にイベントを直接追加する。戻り値: event_id。"""
    creds = get_credentials()
    if not creds:
        raise RuntimeError(
            "Google 認証が必要です。/api/auth/login にアクセスしてください。"
        )
    from googleapiclient.discovery import build

    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)

    service = build("calendar", "v3", credentials=creds)
    body = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Tokyo"},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": "Asia/Tokyo"},
    }
    ev = service.events().insert(calendarId="primary", body=body).execute()
    return ev["id"]


def _sync_to_calendar(creds, task) -> str:
    from googleapiclient.discovery import build

    service = build("calendar", "v3", credentials=creds)

    dt = task.due_date
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt_str = dt.isoformat()

    body = {
        "summary": task.text,
        "description": f"qcatch_id:{task.id}\ncategory:{task.category or ''}",
        "start": {"dateTime": dt_str, "timeZone": "Asia/Tokyo"},
        "end": {"dateTime": dt_str, "timeZone": "Asia/Tokyo"},
    }

    if task.google_event_id:
        try:
            ev = (
                service.events()
                .update(calendarId="primary", eventId=task.google_event_id, body=body)
                .execute()
            )
            return ev["id"]
        except Exception:
            pass  # 削除済みなら新規作成にフォールバック

    ev = service.events().insert(calendarId="primary", body=body).execute()
    return ev["id"]


def _delete_calendar_event(creds, event_id: str) -> None:
    from googleapiclient.discovery import build

    service = build("calendar", "v3", credentials=creds)
    try:
        service.events().delete(calendarId="primary", eventId=event_id).execute()
    except Exception:
        pass


# ── Tasks ────────────────────────────────────────────────────────────────────


def _get_tasklist_map() -> dict:
    """qcatch_config.json から google_tasklist_map を読む。"""
    try:
        import json

        cfg_file = BASE_DIR / "qcatch_config.json"
        if cfg_file.exists():
            cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
            return cfg.get("google_tasklist_map", {})
    except Exception:
        pass
    return {}


def _save_tasklist_map(mapping: dict) -> None:
    """google_tasklist_map を qcatch_config.json に保存（AI マッチ結果のキャッシュ）。"""
    import json

    cfg_file = BASE_DIR / "qcatch_config.json"
    cfg: dict = {}
    if cfg_file.exists():
        try:
            cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    cfg["google_tasklist_map"] = mapping
    cfg_file.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def _ai_match_tasklist(category: str, list_titles: list[str]) -> str | None:
    """AI でカテゴリ名に最も近い既存リスト名を返す。マッチなしなら None。"""
    import os

    prompt = (
        f"Google Tasks のリスト一覧: {list_titles}\n\n"
        f"qcatch のカテゴリ「{category}」に意味が最も近いリストを1つ選んでください。\n"
        "意味が近いものがなければ null と答えてください。\n"
        "リスト名のみを回答してください（説明不要）。"
    )

    # Gemini 優先
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        try:
            from google import genai

            client = genai.Client(api_key=api_key)
            resp = client.models.generate_content(
                model="gemini-2.0-flash", contents=prompt
            )
            answer = resp.text.strip().strip('"').strip("'")
            if answer.lower() != "null" and answer in list_titles:
                return answer
        except Exception:
            pass

    # Anthropic フォールバック
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=50,
                messages=[{"role": "user", "content": prompt}],
            )
            answer = msg.content[0].text.strip().strip('"').strip("'")
            if answer.lower() != "null" and answer in list_titles:
                return answer
        except Exception:
            pass

    return None


def _get_or_create_tasklist(service, category: str | None) -> str:
    mapping = _get_tasklist_map()
    key = category or ""

    lists = service.tasklists().list(maxResults=50).execute().get("items", [])
    title_to_id = {tl["title"]: tl["id"] for tl in lists}

    # 1. 手動マッピングが設定されていれば最優先
    mapped_title = mapping.get(key) or mapping.get("") or None
    if mapped_title and mapped_title in title_to_id:
        return title_to_id[mapped_title]

    # 2. 既に AI マッチ済みのキャッシュがあればそれを使う
    #    （mapping に category キーがあれば既キャッシュ）
    if key in mapping and mapping[key] in title_to_id:
        return title_to_id[mapping[key]]

    # 3. AI でマッチング
    if category and title_to_id:
        matched = _ai_match_tasklist(category, list(title_to_id.keys()))
        if matched:
            # キャッシュとして保存
            mapping[key] = matched
            _save_tasklist_map(mapping)
            return title_to_id[matched]

    # 4. マッチなし → 新規作成
    title = category or "qcatch"
    if title in title_to_id:
        return title_to_id[title]
    new_list = service.tasklists().insert(body={"title": title}).execute()
    return new_list["id"]


def _sync_to_tasks(creds, task) -> str:
    from googleapiclient.discovery import build

    service = build("tasks", "v1", credentials=creds)
    list_id = _get_or_create_tasklist(service, task.category)

    due_str = task.due_date.strftime("%Y-%m-%dT00:00:00.000Z")
    body = {
        "title": task.text,
        "due": due_str,
        "status": "completed" if task.status == "done" else "needsAction",
        "notes": f"qcatch_id:{task.id}",
    }

    if task.google_task_id:
        try:
            t = (
                service.tasks()
                .update(tasklist=list_id, task=task.google_task_id, body=body)
                .execute()
            )
            return t["id"]
        except Exception:
            pass  # 削除済みなら新規作成にフォールバック

    t = service.tasks().insert(tasklist=list_id, body=body).execute()
    return t["id"]


def _delete_google_task(creds, task_id: str) -> None:
    from googleapiclient.discovery import build

    service = build("tasks", "v1", credentials=creds)
    try:
        lists = service.tasklists().list(maxResults=30).execute().get("items", [])
        for tl in lists:
            try:
                service.tasks().delete(tasklist=tl["id"], task=task_id).execute()
                return
            except Exception:
                continue
    except Exception:
        pass
