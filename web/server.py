"""web/server.py — FastAPI アプリ組み立て & 起動"""

from __future__ import annotations

import logging
import os
import sys
import threading
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core import storage
from core.storage import promote_longterm_tasks, save_data, save_data_bg
from web import deps
from web.routers import (
    blog,
    chat,
    checklists,
    config,
    diary,
    flashcards,
    lang,
    sync,
    tasks,
)

# localhost HTTP で OAuth2 を通すために必要（本番環境では設定しない）
if os.environ.get("HOST", "127.0.0.1") in ("127.0.0.1", "localhost"):
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

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
        scheduler.start()
        deps.logger.info(f"自動同期スケジューラ起動（{interval_min}分ごと）")
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
