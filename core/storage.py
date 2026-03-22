"""core/storage.py — tasks.json の読み書き・データ移行・定期タスク処理"""

from __future__ import annotations

import json
import re
import sys
import threading
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from core.models import AppData, Category, RecurringRule, Task

# パス解決（PyInstaller .exe / 通常実行 両対応）
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent.parent

DATA_DIR = BASE_DIR / "data"
TASKS_FILE = DATA_DIR / "tasks.json"
INBOX_FILE = DATA_DIR / "inbox.txt"
SORTED_FILE = DATA_DIR / "sorted_tasks.md"
DONE_FILE = DATA_DIR / "done.txt"

CATEGORIES: list[Category] = ["仕事", "プライベート", "買い物", "学習", "その他"]

DATA_DIR.mkdir(exist_ok=True)


# ── 読み書き ──────────────────────────────────────────────────────────────────


def load_data() -> AppData:
    """tasks.json を読み込む。存在しなければ空の AppData を返す。"""
    if not TASKS_FILE.exists():
        return AppData()
    try:
        raw = TASKS_FILE.read_text(encoding="utf-8")
        return AppData.model_validate_json(raw)
    except Exception:
        return AppData()


_save_lock = threading.Lock()


def save_data(data: AppData) -> None:
    """AppData を tasks.json にアトミック書き込み（tmp → rename）。"""
    with _save_lock:
        tmp = TASKS_FILE.with_suffix(".tmp")
        tmp.write_text(
            data.model_dump_json(indent=2, exclude_none=False),
            encoding="utf-8",
        )
        tmp.replace(TASKS_FILE)


def save_data_bg(data: AppData) -> None:
    """バックグラウンドスレッドで保存（HTTPレスポンスをブロックしない）。"""
    threading.Thread(target=save_data, args=(data,), daemon=True).start()


# ── inbox.txt 吸い上げ ────────────────────────────────────────────────────────

_TS_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\]\s*")


def _parse_inbox_line(line: str) -> Task | None:
    """inbox.txt の1行をパースして Task(status=inbox) を返す。"""
    line = line.strip()
    if not line:
        return None
    m = _TS_RE.match(line)
    if m:
        ts_str = m.group(1)
        text = line[m.end() :].strip()
        # ダブルタイムスタンプ（ソート後に再度inboxに入ったケース）を除去
        text = _TS_RE.sub("", text).strip()
        try:
            created_at = datetime.strptime(ts_str, "%Y-%m-%d %H:%M")
        except ValueError:
            created_at = datetime.now()
    else:
        text = line
        created_at = datetime.now()
    if not text:
        return None
    return Task(text=text, status="inbox", created_at=created_at)


def siphon_inbox(data: AppData) -> int:
    """
    inbox.txt の内容を tasks.json の inbox タスクとして取り込む。
    取り込み後 inbox.txt をクリアする。
    戻り値: 追加されたタスク数。
    """
    if not INBOX_FILE.exists():
        return 0
    content = INBOX_FILE.read_text(encoding="utf-8")
    lines = content.splitlines()
    added = 0
    existing_texts = {t.text for t in data.tasks if t.status == "inbox"}
    for line in lines:
        task = _parse_inbox_line(line)
        if task and task.text not in existing_texts:
            data.tasks.append(task)
            existing_texts.add(task.text)
            added += 1
    if added:
        INBOX_FILE.write_text("", encoding="utf-8")
    return added


# ── 長期タスク自動昇格 ───────────────────────────────────────────────────────


def promote_longterm_tasks(data: AppData, days_threshold: int = 7) -> int:
    """due_date が days_threshold 日以内の longterm タスクを todo に昇格する。"""
    threshold = datetime.now() + timedelta(days=days_threshold)
    promoted = 0
    for task in data.tasks:
        if task.status == "longterm" and task.due_date and task.due_date <= threshold:
            task.status = "todo"
            promoted += 1
    return promoted


# ── 既存データ移行（初回のみ） ────────────────────────────────────────────────


def migrate_from_existing(data: AppData) -> int:
    """
    sorted_tasks.md と done.txt から既存データを移行する。
    tasks.json が空のときだけ実行する（初回移行）。
    戻り値: 移行されたタスク数。
    """
    if data.tasks:
        return 0  # すでにデータあり → スキップ

    migrated = 0

    # sorted_tasks.md → status=todo
    if SORTED_FILE.exists():
        current_cat: Category | None = None
        for line in SORTED_FILE.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            for cat in CATEGORIES:
                if stripped == f"## {cat}":
                    current_cat = cat
                    break
            else:
                if current_cat and stripped.startswith("- "):
                    raw = stripped[2:]
                    m = re.match(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\]\s*(.*)", raw)
                    if m:
                        try:
                            created_at = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M")
                        except ValueError:
                            created_at = datetime.now()
                        text = m.group(2).strip()
                    else:
                        text = raw.strip()
                        created_at = datetime.now()
                    if text:
                        data.tasks.append(
                            Task(
                                text=text,
                                status="todo",
                                category=current_cat,
                                created_at=created_at,
                            )
                        )
                        migrated += 1

    # done.txt → status=done
    if DONE_FILE.exists():
        for line in DONE_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            m = re.match(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\]\s*(.*)", line)
            if m:
                try:
                    completed_at = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M")
                except ValueError:
                    completed_at = datetime.now()
                # テキスト内のダブルタイムスタンプを除去
                text = _TS_RE.sub("", m.group(2)).strip()
            else:
                text = line
                completed_at = datetime.now()
            if text:
                data.tasks.append(
                    Task(
                        text=text,
                        status="done",
                        completed_at=completed_at,
                    )
                )
                migrated += 1

    return migrated


# ── 定期タスク チェック ───────────────────────────────────────────────────────


def check_recurring(data: AppData) -> list[str]:
    """
    定期ルールを評価し、条件を満たすタスクを inbox として追加する。
    戻り値: 今回追加されたタスクテキストのリスト。
    """
    today = date.today()
    added_texts: list[str] = []

    for rule in data.recurring:
        if rule.last_generated_date:
            try:
                last = date.fromisoformat(rule.last_generated_date)
            except ValueError:
                last = date.min
        else:
            last = date.min

        if last >= today:
            continue  # 今日すでに生成済み

        should_add = False
        if rule.frequency == "daily":
            should_add = True
        elif rule.frequency == "weekly":
            if today.weekday() in rule.days_of_week:
                should_add = True
        elif rule.frequency == "monthly":
            if rule.day_of_month is not None and today.day == rule.day_of_month:
                should_add = True

        if should_add:
            data.tasks.append(
                Task(
                    text=rule.text,
                    status="inbox",
                    category=rule.category,
                )
            )
            rule.last_generated_date = today.isoformat()
            added_texts.append(rule.text)

    return added_texts


# ── アーカイブ（古い完了タスクを別ファイルへ退避） ──────────────────────────

ARCHIVE_DAYS = 30


def archive_old_done(data: AppData) -> int:
    """
    completed_at が ARCHIVE_DAYS 日以上前の done タスクを年別アーカイブへ退避する。
    戻り値: 退避したタスク数。
    """
    cutoff = datetime.now() - timedelta(days=ARCHIVE_DAYS)
    to_archive = [
        t
        for t in data.tasks
        if t.status == "done" and t.completed_at and t.completed_at < cutoff
    ]
    if not to_archive:
        return 0

    # 年別にグループ化してアーカイブファイルへ追記
    by_year: dict[int, list] = defaultdict(list)
    for t in to_archive:
        by_year[t.completed_at.year].append(t)

    for year, tasks in by_year.items():
        archive_file = DATA_DIR / f"archive_{year}.json"
        existing: list[dict] = []
        if archive_file.exists():
            try:
                existing = json.loads(archive_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        existing.extend(t.model_dump(mode="json") for t in tasks)
        archive_file.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    archive_ids = {t.id for t in to_archive}
    data.tasks = [t for t in data.tasks if t.id not in archive_ids]
    return len(to_archive)


# ── 起動時の初期化シーケンス ─────────────────────────────────────────────────


def initialize() -> tuple[AppData, dict[str, int]]:
    """
    サーバー起動時に呼ぶ初期化処理。
    1. tasks.json 読み込み
    2. 初回なら既存データ移行
    3. inbox.txt 吸い上げ
    4. 定期タスク チェック

    戻り値: (AppData, {"migrated": n, "siphoned": n, "recurring": n})
    """
    data = load_data()

    migrated = migrate_from_existing(data)
    siphoned = siphon_inbox(data)
    recurring_added = check_recurring(data)
    archived = archive_old_done(data)

    if migrated or siphoned or recurring_added or archived:
        save_data(data)

    return data, {
        "migrated": migrated,
        "siphoned": siphoned,
        "recurring": len(recurring_added),
        "archived": archived,
    }
