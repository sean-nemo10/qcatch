"""web/server.py — FastAPI アプリ組み立て & 起動"""

from __future__ import annotations

import logging
import os
import secrets
import sys
import threading
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from core import storage
from core.storage import (
    check_recurring,
    promote_longterm_tasks,
    save_data,
    save_data_bg,
)
from web import deps
from web.routers import (
    blog,
    chat,
    checklists,
    config,
    diary,
    flashcards,
    lang,
    recurring,
    sync,
    tasks,
)

# localhost HTTP で OAuth2 を通すために必要（本番環境では設定しない）
if os.environ.get("HOST", "127.0.0.1") in ("127.0.0.1", "localhost"):
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

# ── 認証設定（deps.py の共有ヘルパーを使用） ─────────────────────────────────

from web.deps import (  # noqa: E402  (deps は下で import される前にここで必要)
    AUTH_REQUIRED,
    GOOGLE_EMAIL,
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    _AUTH_ENABLED,
    make_session_token,
    verify_session,
)

# 認証不要なパス
_PUBLIC_PATHS = {"/login", "/favicon.ico", "/manifest.json", "/sw.js"}


def _render_login_page(error: str = "") -> str:
    err_html = ""
    if error == "1":
        err_html = '<p class="err">ユーザー名またはパスワードが違います</p>'
    elif error == "unauthorized":
        err_html = '<p class="err">このアカウントはアクセスできません</p>'

    password_block = ""
    if _AUTH_ENABLED:
        password_block = """
    <form method="post" action="/login">
      <label>ユーザー名</label>
      <input name="username" type="text" autocomplete="username" autofocus required>
      <label>パスワード</label>
      <input name="password" type="password" autocomplete="current-password" required>
      <button type="submit">ログイン</button>
    </form>"""

    google_block = ""
    if GOOGLE_EMAIL:
        divider = '<div class="divider">または</div>' if _AUTH_ENABLED else ""
        google_block = f"""{divider}
    <a href="/api/auth/login" class="google-btn">
      <svg width="18" height="18" viewBox="0 0 18 18"><path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z"/><path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z"/><path fill="#FBBC05" d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z"/><path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z"/></svg>
      Googleでログイン
    </a>"""

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ZzzMemo — ログイン</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f0f13;color:#e2e8f0;font-family:"Segoe UI",sans-serif;
    display:flex;align-items:center;justify-content:center;min-height:100vh}}
  .card{{background:#1a1a2e;border:1px solid #2a2a3e;border-radius:16px;
    padding:40px 36px;width:100%;max-width:360px}}
  h1{{font-size:22px;margin-bottom:28px;color:#818cf8;text-align:center}}
  label{{display:block;font-size:13px;color:#94a3b8;margin-bottom:6px}}
  input{{width:100%;background:#0f0f1a;border:1px solid #2a2a3e;color:#e2e8f0;
    border-radius:8px;padding:10px 14px;font-size:15px;margin-bottom:18px}}
  input:focus{{outline:none;border-color:#818cf8}}
  button[type=submit]{{width:100%;background:#818cf8;color:#fff;border:none;border-radius:8px;
    padding:12px;font-size:15px;font-weight:600;cursor:pointer}}
  button[type=submit]:hover{{background:#6366f1}}
  .google-btn{{display:flex;align-items:center;justify-content:center;gap:10px;
    width:100%;background:#fff;color:#3c4043;border:1px solid #dadce0;border-radius:8px;
    padding:11px;font-size:15px;font-weight:500;text-decoration:none;cursor:pointer}}
  .google-btn:hover{{background:#f8f9fa}}
  .divider{{text-align:center;color:#4a5568;font-size:13px;margin:16px 0;
    position:relative}}
  .divider::before,.divider::after{{content:"";position:absolute;top:50%;
    width:42%;height:1px;background:#2a2a3e}}
  .divider::before{{left:0}}.divider::after{{right:0}}
  .err{{color:#f87171;font-size:13px;text-align:center;margin-bottom:14px}}
</style>
</head>
<body>
<div class="card">
  <h1>ZzzMemo</h1>
  {err_html}
  {password_block}
  {google_block}
</div>
</body>
</html>"""


# ── パス解決 ──────────────────────────────────────────────────────────────────

if getattr(sys, "frozen", False):
    _BASE_DIR = Path(sys.executable).parent
else:
    _BASE_DIR = Path(__file__).parent.parent

_STATIC_DIR = _BASE_DIR / "web" / "static"

# ── ログ設定 ──────────────────────────────────────────────────────────────────


def _setup_logging(base_dir: Path) -> logging.Logger:
    log_file = base_dir / "data" / "app.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(fmt)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    logger = logging.getLogger("ZzzMemo")
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


deps.logger = _setup_logging(_BASE_DIR)


# ── 自動同期ジョブ ────────────────────────────────────────────────────────────


def _recurring_check_job() -> None:
    try:
        added = check_recurring(deps.app_data)
        if added:
            save_data_bg(deps.app_data)
            deps.logger.info(f"定期タスク生成: {len(added)}件 — {added}")
    except Exception as e:
        deps.logger.error(f"定期タスクチェックエラー: {e}", exc_info=True)


def _auto_sync_job() -> None:
    from core import google_sync

    if not google_sync.is_authenticated():
        return
    try:
        pushed = google_sync.push_all(deps.app_data)
        pulled = google_sync.pull_all(deps.app_data)
        if pushed or pulled:
            save_data_bg(deps.app_data)
        deps.logger.info(f"自動同期完了: push={pushed} pull={pulled}")
    except Exception as e:
        deps.logger.error(f"自動同期エラー: {e}", exc_info=True)


# ── ライフスパン ──────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Google client_secret.json を環境変数から復元（Fly.io 用）
    _secret_json = os.environ.get("GOOGLE_CLIENT_SECRET_JSON", "")
    if _secret_json:
        secret_path = _BASE_DIR / "data" / "client_secret.json"
        secret_path.parent.mkdir(parents=True, exist_ok=True)
        secret_path.write_text(_secret_json, encoding="utf-8")

    deps.app_data, stats = storage.initialize()
    promoted = promote_longterm_tasks(deps.app_data)
    if promoted:
        save_data(deps.app_data)
    deps.logger.info(
        f"起動完了 — 移行:{stats['migrated']} 吸い上げ:{stats['siphoned']} "
        f"定期:{stats['recurring']} アーカイブ:{stats['archived']} 長期昇格:{promoted}"
    )

    scheduler = None
    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler()
        cfg = deps.load_config()
        interval_min = cfg.get("sync_interval_minutes", 30)
        scheduler.add_job(_auto_sync_job, "interval", minutes=interval_min)
        scheduler.add_job(_recurring_check_job, "cron", hour="*", minute=5)
        scheduler.start()
        deps.logger.info(
            f"スケジューラ起動 — 自動同期:{interval_min}分ごと / 定期タスク:毎時5分"
        )
    except ImportError:
        deps.logger.warning("apscheduler 未インストール。自動同期は無効です。")

    yield

    if scheduler:
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            pass


# ── FastAPI アプリ ────────────────────────────────────────────────────────────

app = FastAPI(title="ZzzMemo", lifespan=lifespan)

_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def session_auth_middleware(request: Request, call_next):
    path = request.url.path
    if AUTH_REQUIRED and path not in _PUBLIC_PATHS and not path.startswith("/static/"):
        if not verify_session(request):
            if path.startswith("/api/"):
                return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
            return RedirectResponse(url="/login", status_code=302)
    return await call_next(request)


# ── 認証エンドポイント ─────────────────────────────────────────────────────────


@app.get("/login", response_class=HTMLResponse)
def login_page(error: str = ""):
    return HTMLResponse(_render_login_page(error))


@app.post("/login")
def login_submit(username: str = Form(...), password: str = Form(...)):
    from web.deps import _AUTH_USER, _AUTH_PASS

    user_ok = secrets.compare_digest(username.encode(), _AUTH_USER.encode())
    pass_ok = secrets.compare_digest(password.encode(), _AUTH_PASS.encode())
    if _AUTH_ENABLED and not (user_ok and pass_ok):
        return RedirectResponse(url="/login?error=1", status_code=303)
    resp = RedirectResponse(url="/", status_code=303)
    resp.set_cookie(
        SESSION_COOKIE,
        make_session_token(),
        httponly=True,
        secure=AUTH_REQUIRED,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
    )
    return resp


@app.get("/logout")
def logout():
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie(SESSION_COOKIE)
    return resp


# 静的ファイル
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


# ── ルーター登録 ──────────────────────────────────────────────────────────────

app.include_router(tasks.router)
app.include_router(recurring.router)
app.include_router(checklists.router)
app.include_router(chat.router)
app.include_router(diary.router)
app.include_router(blog.router)
app.include_router(flashcards.router)
app.include_router(lang.router)
app.include_router(sync.router)
app.include_router(config.router)


# ── サーバー起動 ──────────────────────────────────────────────────────────────


def run(port: int | None = None, open_browser: bool | None = None) -> None:
    import uvicorn

    host = os.environ.get("HOST", "127.0.0.1")
    port = port or int(os.environ.get("PORT", "5000"))
    if open_browser is None:
        open_browser = host in ("127.0.0.1", "localhost")

    if open_browser:
        url = f"http://localhost:{port}"

        def _open():
            import time

            time.sleep(1.2)
            webbrowser.open(url)

        threading.Thread(target=_open, daemon=True).start()

    print(f"[ZzzMemo] サーバー起動 → {host}:{port}")
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="warning",
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
