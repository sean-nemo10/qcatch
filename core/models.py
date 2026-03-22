"""core/models.py — qcatch データモデル定義"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

TaskStatus = Literal["inbox", "todo", "done", "trashed", "longterm"]
Category = Literal["仕事", "プライベート", "買い物", "学習", "その他"]


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


class ChecklistItem(BaseModel):
    text: str
    done: bool = False


class ChecklistTemplate(BaseModel):
    id: str = Field(default_factory=_new_id)
    name: str
    items: list[ChecklistItem] = Field(default_factory=list)
    due_date: Optional[datetime] = None


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
