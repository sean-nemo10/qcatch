"""core/models.py — qcatch データモデル定義"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

TaskStatus = Literal["inbox", "todo", "done", "trashed", "longterm", "wishlist"]
Category = Literal["仕事", "プライベート", "買い物", "学習", "その他"]
Importance = Literal["high", "medium", "low"]


def _new_id() -> str:
    return str(uuid.uuid4())


class Task(BaseModel):
    id: str = Field(default_factory=_new_id)
    text: str
    status: TaskStatus = "inbox"
    category: Optional[Category] = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    due_date: Optional[datetime] = None
    importance: Importance = "medium"
    google_event_id: Optional[str] = None  # Calendar イベント ID
    google_task_id: Optional[str] = None  # Google Tasks タスク ID


class ChecklistItem(BaseModel):
    text: str
    done: bool = False


class ChecklistTemplate(BaseModel):
    id: str = Field(default_factory=_new_id)
    name: str
    items: list[ChecklistItem] = Field(default_factory=list)
    due_date: Optional[datetime] = None
    parent_id: Optional[str] = None  # 階層構造（None=ルート）
    sort_order: int = 0  # 同階層内の表示順


class RecurringRule(BaseModel):
    id: str = Field(default_factory=_new_id)
    text: str
    category: Optional[Category] = None
    frequency: Literal["daily", "weekly", "monthly"]
    days_of_week: list[int] = Field(default_factory=list)  # 0=月, 6=日
    day_of_month: Optional[int] = None
    last_generated_date: Optional[str] = None  # YYYY-MM-DD


class AppData(BaseModel):
    tasks: list[Task] = Field(default_factory=list)
    checklists: list[ChecklistTemplate] = Field(default_factory=list)
    recurring: list[RecurringRule] = Field(default_factory=list)
    dashboard_order: list[str] = Field(default_factory=list)  # タスクIDの手動並び順
    tasks_order: list[str] = Field(default_factory=list)  # タスクタブの手動並び順


class DiaryEntry(BaseModel):
    date_str: str  # YYYY-MM-DD
    content: str
    referenced_task_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class DiaryData(BaseModel):
    entries: dict[str, DiaryEntry] = Field(default_factory=dict)


class BlogPost(BaseModel):
    id: str = Field(default_factory=_new_id)
    title: str
    tags: list[str] = Field(default_factory=list)
    content: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class BlogData(BaseModel):
    posts: list[BlogPost] = Field(default_factory=list)


class FlashCard(BaseModel):
    id: str = Field(default_factory=_new_id)
    front: str  # 日本語の文脈 or 英単語
    back: str  # 英語表現 or 日本語の意味
    example: str = ""  # 例文
    source: str = ""  # "task" | "diary" | "practice" | "manual"
    source_ref: str = ""  # タスクテキスト or 日記日付
    interval: int = 1  # SM-2: 次回復習までの日数
    ease: float = 2.5  # SM-2: 難易度係数
    repetitions: int = 0  # SM-2: 連続正解数
    lapses: int = 0  # SM-2: ミス累計
    next_review: str = Field(  # YYYY-MM-DD
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d")
    )
    created_at: datetime = Field(default_factory=datetime.now)


class FlashDeck(BaseModel):
    cards: list[FlashCard] = Field(default_factory=list)
