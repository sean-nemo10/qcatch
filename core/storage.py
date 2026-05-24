"""core/storage.py — SQLite バックエンド読み書き・データ移行・定期タスク処理"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

from core.models import (
    AppData,
    BlogData,
    BlogPost,
    Category,
    ChecklistItem,
    ChecklistTemplate,
    DiaryData,
    DiaryEntry,
    FlashCard,
    FlashDeck,
    RecurringRule,
    Task,
)

# パス解決（PyInstaller .exe / 通常実行 両対応）
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent.parent

DATA_DIR = BASE_DIR / "data"
TASKS_FILE = DATA_DIR / "tasks.json"
DIARY_FILE = DATA_DIR / "diary.json"
BLOG_FILE = DATA_DIR / "blog.json"
FLASHCARD_FILE = DATA_DIR / "flashcards.json"
INBOX_FILE = DATA_DIR / "inbox.txt"
SORTED_FILE = DATA_DIR / "sorted_tasks.md"
DONE_FILE = DATA_DIR / "done.txt"
DB_FILE = DATA_DIR / "qcatch.db"

CATEGORIES: list[Category] = ["仕事", "プライベート", "買い物", "学習", "その他"]

DATA_DIR.mkdir(exist_ok=True)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    status TEXT NOT NULL,
    category TEXT,
    tags TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    completed_at TEXT,
    due_date TEXT,
    importance TEXT NOT NULL DEFAULT 'medium',
    google_event_id TEXT,
    google_task_id TEXT
);

CREATE TABLE IF NOT EXISTS checklists (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    due_date TEXT,
    items TEXT NOT NULL DEFAULT '[]',
    parent_id TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS recurring_rules (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    category TEXT,
    frequency TEXT NOT NULL,
    days_of_week TEXT NOT NULL DEFAULT '[]',
    day_of_month INTEGER,
    last_generated_date TEXT
);

CREATE TABLE IF NOT EXISTS ordered_lists (
    list_name TEXT PRIMARY KEY,
    order_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS diary_entries (
    date_str TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    referenced_task_ids TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS blog_posts (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '[]',
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS flashcards (
    id TEXT PRIMARY KEY,
    front TEXT NOT NULL,
    back TEXT NOT NULL,
    example TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    source_ref TEXT NOT NULL DEFAULT '',
    interval INTEGER NOT NULL DEFAULT 1,
    ease REAL NOT NULL DEFAULT 2.5,
    repetitions INTEGER NOT NULL DEFAULT 0,
    lapses INTEGER NOT NULL DEFAULT 0,
    next_review TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS archived_tasks (
    id TEXT PRIMARY KEY,
    task_json TEXT NOT NULL,
    archived_year INTEGER NOT NULL,
    completed_at TEXT NOT NULL
);
"""


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_FILE), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _get_conn()
    with conn:
        conn.executescript(_SCHEMA)
        # 既存DBへの追加カラム（idempotent）
        cols = {
            r["name"] for r in conn.execute("PRAGMA table_info(checklists)").fetchall()
        }
        if "parent_id" not in cols:
            conn.execute("ALTER TABLE checklists ADD COLUMN parent_id TEXT")
        if "sort_order" not in cols:
            conn.execute(
                "ALTER TABLE checklists ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0"
            )
    conn.close()


# ── Row conversion helpers ────────────────────────────────────────────────────


def _task_to_row(t: Task) -> tuple:
    return (
        t.id,
        t.text,
        t.status,
        t.category,
        json.dumps(t.tags),
        t.created_at.isoformat() if t.created_at else None,
        t.completed_at.isoformat() if t.completed_at else None,
        t.due_date.isoformat() if t.due_date else None,
        t.importance,
        t.google_event_id,
        t.google_task_id,
    )


def _row_to_task(r: sqlite3.Row) -> Task:
    return Task(
        id=r["id"],
        text=r["text"],
        status=r["status"],
        category=r["category"],
        tags=json.loads(r["tags"]),
        created_at=datetime.fromisoformat(r["created_at"]) if r["created_at"] else None,
        completed_at=(
            datetime.fromisoformat(r["completed_at"]) if r["completed_at"] else None
        ),
        due_date=datetime.fromisoformat(r["due_date"]) if r["due_date"] else None,
        importance=r["importance"],
        google_event_id=r["google_event_id"],
        google_task_id=r["google_task_id"],
    )


def _checklist_to_row(c: ChecklistTemplate) -> tuple:
    return (
        c.id,
        c.name,
        c.due_date.isoformat() if c.due_date else None,
        json.dumps([item.model_dump() for item in c.items]),
        c.parent_id,
        c.sort_order,
    )


def _row_to_checklist(r: sqlite3.Row) -> ChecklistTemplate:
    raw_items = json.loads(r["items"])
    keys = r.keys()
    return ChecklistTemplate(
        id=r["id"],
        name=r["name"],
        due_date=datetime.fromisoformat(r["due_date"]) if r["due_date"] else None,
        items=[ChecklistItem(**item) for item in raw_items],
        parent_id=r["parent_id"] if "parent_id" in keys else None,
        sort_order=r["sort_order"] if "sort_order" in keys else 0,
    )


def _recurring_to_row(rec: RecurringRule) -> tuple:
    return (
        rec.id,
        rec.text,
        rec.category,
        rec.frequency,
        json.dumps(rec.days_of_week),
        rec.day_of_month,
        rec.last_generated_date,
    )


def _row_to_recurring(r: sqlite3.Row) -> RecurringRule:
    return RecurringRule(
        id=r["id"],
        text=r["text"],
        category=r["category"],
        frequency=r["frequency"],
        days_of_week=json.loads(r["days_of_week"]),
        day_of_month=r["day_of_month"],
        last_generated_date=r["last_generated_date"],
    )


# ── 読み書き ──────────────────────────────────────────────────────────────────


def load_data() -> AppData:
    """SQLite から AppData を読み込む。"""
    conn = _get_conn()
    try:
        tasks = [
            _row_to_task(r) for r in conn.execute("SELECT * FROM tasks").fetchall()
        ]
        checklists = [
            _row_to_checklist(r)
            for r in conn.execute("SELECT * FROM checklists").fetchall()
        ]
        recurring = [
            _row_to_recurring(r)
            for r in conn.execute("SELECT * FROM recurring_rules").fetchall()
        ]
        dash_row = conn.execute(
            "SELECT order_json FROM ordered_lists WHERE list_name='dashboard'"
        ).fetchone()
        tasks_row = conn.execute(
            "SELECT order_json FROM ordered_lists WHERE list_name='tasks'"
        ).fetchone()
        return AppData(
            tasks=tasks,
            checklists=checklists,
            recurring=recurring,
            dashboard_order=json.loads(dash_row["order_json"]) if dash_row else [],
            tasks_order=json.loads(tasks_row["order_json"]) if tasks_row else [],
        )
    finally:
        conn.close()


_save_lock = threading.Lock()


def save_data(data: AppData) -> None:
    """AppData を SQLite にトランザクション書き込み。"""
    with _save_lock:
        conn = _get_conn()
        with conn:
            conn.execute("DELETE FROM tasks")
            conn.executemany(
                "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                [_task_to_row(t) for t in data.tasks],
            )
            conn.execute("DELETE FROM checklists")
            conn.executemany(
                "INSERT INTO checklists VALUES (?,?,?,?,?,?)",
                [_checklist_to_row(c) for c in data.checklists],
            )
            conn.execute("DELETE FROM recurring_rules")
            conn.executemany(
                "INSERT INTO recurring_rules VALUES (?,?,?,?,?,?,?)",
                [_recurring_to_row(r) for r in data.recurring],
            )
            conn.execute(
                "INSERT OR REPLACE INTO ordered_lists VALUES ('dashboard', ?)",
                (json.dumps(data.dashboard_order),),
            )
            conn.execute(
                "INSERT OR REPLACE INTO ordered_lists VALUES ('tasks', ?)",
                (json.dumps(data.tasks_order),),
            )
        conn.close()


def save_data_bg(data: AppData) -> None:
    """バックグラウンドスレッドで保存（HTTPレスポンスをブロックしない）。"""
    threading.Thread(target=save_data, args=(data,)).start()


# ── 日記 読み書き ─────────────────────────────────────────────────────────────


def load_diary() -> DiaryData:
    """SQLite から DiaryData を読み込む。"""
    conn = _get_conn()
    try:
        rows = conn.execute("SELECT * FROM diary_entries").fetchall()
        entries = {}
        for r in rows:
            e = DiaryEntry(
                date_str=r["date_str"],
                content=r["content"],
                referenced_task_ids=json.loads(r["referenced_task_ids"]),
                created_at=datetime.fromisoformat(r["created_at"]),
                updated_at=datetime.fromisoformat(r["updated_at"]),
            )
            entries[e.date_str] = e
        return DiaryData(entries=entries)
    finally:
        conn.close()


_diary_lock = threading.Lock()


def save_diary(data: DiaryData) -> None:
    """DiaryData を SQLite に書き込む。"""
    with _diary_lock:
        conn = _get_conn()
        with conn:
            conn.execute("DELETE FROM diary_entries")
            conn.executemany(
                "INSERT INTO diary_entries VALUES (?,?,?,?,?)",
                [
                    (
                        e.date_str,
                        e.content,
                        json.dumps(e.referenced_task_ids),
                        e.created_at.isoformat(),
                        e.updated_at.isoformat(),
                    )
                    for e in data.entries.values()
                ],
            )
        conn.close()


def save_diary_bg(data: DiaryData) -> None:
    threading.Thread(target=save_diary, args=(data,)).start()


# ── ブログ 読み書き ───────────────────────────────────────────────────────────


def load_blog() -> BlogData:
    """SQLite から BlogData を読み込む。"""
    conn = _get_conn()
    try:
        rows = conn.execute("SELECT * FROM blog_posts").fetchall()
        posts = [
            BlogPost(
                id=r["id"],
                title=r["title"],
                tags=json.loads(r["tags"]),
                content=r["content"],
                created_at=datetime.fromisoformat(r["created_at"]),
                updated_at=datetime.fromisoformat(r["updated_at"]),
            )
            for r in rows
        ]
        return BlogData(posts=posts)
    finally:
        conn.close()


_blog_lock = threading.Lock()


def save_blog(data: BlogData) -> None:
    with _blog_lock:
        conn = _get_conn()
        with conn:
            conn.execute("DELETE FROM blog_posts")
            conn.executemany(
                "INSERT INTO blog_posts VALUES (?,?,?,?,?,?)",
                [
                    (
                        p.id,
                        p.title,
                        json.dumps(p.tags),
                        p.content,
                        p.created_at.isoformat(),
                        p.updated_at.isoformat(),
                    )
                    for p in data.posts
                ],
            )
        conn.close()


def save_blog_bg(data: BlogData) -> None:
    threading.Thread(target=save_blog, args=(data,)).start()


# ── フラッシュカード 読み書き ──────────────────────────────────────────────────


def load_flashcards() -> FlashDeck:
    conn = _get_conn()
    try:
        rows = conn.execute("SELECT * FROM flashcards").fetchall()
        cards = [
            FlashCard(
                id=r["id"],
                front=r["front"],
                back=r["back"],
                example=r["example"],
                source=r["source"],
                source_ref=r["source_ref"],
                interval=r["interval"],
                ease=r["ease"],
                repetitions=r["repetitions"],
                lapses=r["lapses"],
                next_review=r["next_review"],
                created_at=datetime.fromisoformat(r["created_at"]),
            )
            for r in rows
        ]
        return FlashDeck(cards=cards)
    finally:
        conn.close()


_flash_lock = threading.Lock()


def save_flashcards(deck: FlashDeck) -> None:
    with _flash_lock:
        conn = _get_conn()
        with conn:
            conn.execute("DELETE FROM flashcards")
            conn.executemany(
                "INSERT INTO flashcards VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                [
                    (
                        c.id,
                        c.front,
                        c.back,
                        c.example,
                        c.source,
                        c.source_ref,
                        c.interval,
                        c.ease,
                        c.repetitions,
                        c.lapses,
                        c.next_review,
                        c.created_at.isoformat(),
                    )
                    for c in deck.cards
                ],
            )
        conn.close()


def save_flashcards_bg(deck: FlashDeck) -> None:
    threading.Thread(target=save_flashcards, args=(deck,)).start()


def sm2_update(card, quality: int):
    """SM-2 アルゴリズム（quality: 0=忘れた, 1=難しい, 2=完璧）"""
    q = [1, 3, 5][max(0, min(2, quality))]
    if q < 3:
        card.interval = 1
        card.repetitions = 0
        card.lapses += 1
    else:
        if card.repetitions == 0:
            card.interval = 1
        elif card.repetitions == 1:
            card.interval = 6
        else:
            card.interval = round(card.interval * card.ease)
        card.repetitions += 1
        card.ease = max(1.3, card.ease + 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    next_date = (date.today() + timedelta(days=card.interval)).isoformat()
    card.next_review = next_date
    return card


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
    inbox.txt の内容を tasks の inbox タスクとして取り込む。
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
    tasks が空のときだけ実行する（初回移行）。
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


# ── アーカイブ（古い完了タスクを archived_tasks テーブルへ退避） ──────────────

ARCHIVE_DAYS = 30


def archive_old_done(data: AppData) -> int:
    """
    completed_at が ARCHIVE_DAYS 日以上前の done タスクを archived_tasks へ退避する。
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

    conn = _get_conn()
    with conn:
        conn.executemany(
            "INSERT OR IGNORE INTO archived_tasks VALUES (?,?,?,?)",
            [
                (
                    t.id,
                    t.model_dump_json(),
                    t.completed_at.year,
                    t.completed_at.isoformat(),
                )
                for t in to_archive
            ],
        )
    conn.close()

    archive_ids = {t.id for t in to_archive}
    data.tasks = [t for t in data.tasks if t.id not in archive_ids]
    return len(to_archive)


# ── JSON → SQLite 一回限りの移行 ─────────────────────────────────────────────


def _migrate_json_to_sqlite() -> int:
    """JSON ファイルから SQLite への一回限りの移行。戻り値: 移行レコード総数。"""
    total = 0

    # tasks.json → tasks, checklists, recurring_rules, ordered_lists
    if TASKS_FILE.exists():
        try:
            app_data = AppData.model_validate_json(
                TASKS_FILE.read_text(encoding="utf-8")
            )
            save_data(app_data)
            total += (
                len(app_data.tasks) + len(app_data.checklists) + len(app_data.recurring)
            )
        except Exception:
            pass

    # diary.json → diary_entries
    if DIARY_FILE.exists():
        try:
            diary = DiaryData.model_validate_json(
                DIARY_FILE.read_text(encoding="utf-8")
            )
            save_diary(diary)
            total += len(diary.entries)
        except Exception:
            pass

    # blog.json → blog_posts
    if BLOG_FILE.exists():
        try:
            blog = BlogData.model_validate_json(BLOG_FILE.read_text(encoding="utf-8"))
            save_blog(blog)
            total += len(blog.posts)
        except Exception:
            pass

    # flashcards.json → flashcards
    if FLASHCARD_FILE.exists():
        try:
            deck = FlashDeck.model_validate_json(
                FLASHCARD_FILE.read_text(encoding="utf-8")
            )
            save_flashcards(deck)
            total += len(deck.cards)
        except Exception:
            pass

    # archive_YYYY.json → archived_tasks
    for archive_file in DATA_DIR.glob("archive_*.json"):
        try:
            records = json.loads(archive_file.read_text(encoding="utf-8"))
            conn = _get_conn()
            with conn:
                for rec in records:
                    t = Task.model_validate(rec)
                    year = t.completed_at.year if t.completed_at else 0
                    conn.execute(
                        "INSERT OR IGNORE INTO archived_tasks VALUES (?,?,?,?)",
                        (
                            t.id,
                            json.dumps(rec),
                            year,
                            t.completed_at.isoformat() if t.completed_at else "",
                        ),
                    )
            conn.close()
            total += len(records)
        except Exception:
            pass

    return total


# ── 起動時の初期化シーケンス ─────────────────────────────────────────────────


def initialize() -> tuple[AppData, dict[str, int]]:
    """
    サーバー起動時に呼ぶ初期化処理。
    1. DB スキーマ作成（初回のみ）
    2. DB が空なら JSON ファイルから移行
    3. AppData 読み込み
    4. 初回なら既存テキストデータ移行
    5. inbox.txt 吸い上げ
    6. 定期タスク チェック
    7. 古い完了タスクのアーカイブ

    戻り値: (AppData, {"migrated": n, "siphoned": n, "recurring": n, "archived": n})
    """
    init_db()

    # DB が空なら JSON ファイルから移行
    conn = _get_conn()
    is_empty = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 0
    conn.close()

    if is_empty:
        _migrate_json_to_sqlite()

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
