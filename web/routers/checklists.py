"""web/routers/checklists.py — /api/checklists, /api/recurring"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.models import Category, ChecklistItem, ChecklistTemplate, RecurringRule
from core.storage import save_data_bg
from web import deps

router = APIRouter()


# ── Pydantic スキーマ ─────────────────────────────────────────────────────────


class ChecklistIn(BaseModel):
    name: str
    items: list[str] = []
    due_date: Optional[datetime] = None
    parent_id: Optional[str] = None


class ChecklistPatch(BaseModel):
    name: Optional[str] = None
    due_date: Optional[datetime] = None
    parent_id: Optional[str] = None
    sort_order: Optional[int] = None


class ChecklistItemPatch(BaseModel):
    item_index: int
    done: Optional[bool] = None
    text: Optional[str] = None


class TaskIn(BaseModel):
    text: str


class RecurringIn(BaseModel):
    text: str
    category: Optional[Category] = None
    frequency: str  # daily | weekly | monthly
    days_of_week: list[int] = []
    day_of_month: Optional[int] = None


class RecurringPatch(BaseModel):
    text: Optional[str] = None
    category: Optional[Category] = None
    frequency: Optional[str] = None
    days_of_week: Optional[list[int]] = None
    day_of_month: Optional[int] = None


# ── /api/checklists ───────────────────────────────────────────────────────────


@router.get("/api/checklists")
def get_checklists():
    return {"checklists": [c.model_dump() for c in deps.app_data.checklists]}


@router.post("/api/checklists", status_code=201)
def create_checklist(body: ChecklistIn):
    checklist = ChecklistTemplate(
        name=body.name,
        items=[ChecklistItem(text=t) for t in body.items if t.strip()],
        due_date=body.due_date,
        parent_id=body.parent_id,
        sort_order=len(deps.app_data.checklists),
    )
    deps.app_data.checklists.append(checklist)
    save_data_bg(deps.app_data)
    return checklist.model_dump()


@router.patch("/api/checklists/{checklist_id}")
def patch_checklist(checklist_id: str, body: ChecklistPatch):
    cl = deps.find_checklist(checklist_id)
    if body.name is not None:
        cl.name = body.name
    if "due_date" in body.model_fields_set:
        cl.due_date = body.due_date
    if "parent_id" in body.model_fields_set:
        if body.parent_id == checklist_id:
            raise HTTPException(400, "自身を親にできません")
        if body.parent_id:
            parent = deps.find_checklist(body.parent_id)
            cur = parent
            while cur.parent_id:
                if cur.parent_id == checklist_id:
                    raise HTTPException(400, "循環参照になります")
                cur = deps.find_checklist(cur.parent_id)
        cl.parent_id = body.parent_id
    if body.sort_order is not None:
        cl.sort_order = body.sort_order
    save_data_bg(deps.app_data)
    return cl.model_dump()


@router.patch("/api/checklists/{checklist_id}/items")
def update_checklist_item(checklist_id: str, body: ChecklistItemPatch):
    cl = deps.find_checklist(checklist_id)
    if body.item_index < 0 or body.item_index >= len(cl.items):
        raise HTTPException(400, "item_index が範囲外です")
    if body.done is not None:
        cl.items[body.item_index].done = body.done
    if body.text is not None and body.text.strip():
        cl.items[body.item_index].text = body.text.strip()
    save_data_bg(deps.app_data)
    return cl.model_dump()


@router.post("/api/checklists/{checklist_id}/reset")
def reset_checklist(checklist_id: str):
    cl = deps.find_checklist(checklist_id)
    for item in cl.items:
        item.done = False
    save_data_bg(deps.app_data)
    return cl.model_dump()


@router.post("/api/checklists/{checklist_id}/items")
def add_checklist_item(checklist_id: str, body: TaskIn):
    cl = deps.find_checklist(checklist_id)
    cl.items.append(ChecklistItem(text=body.text))
    save_data_bg(deps.app_data)
    return cl.model_dump()


@router.delete("/api/checklists/{checklist_id}/items/{item_index}", status_code=204)
def delete_checklist_item(checklist_id: str, item_index: int):
    cl = deps.find_checklist(checklist_id)
    if item_index < 0 or item_index >= len(cl.items):
        raise HTTPException(400, "item_index が範囲外です")
    cl.items.pop(item_index)
    save_data_bg(deps.app_data)


@router.delete("/api/checklists/{checklist_id}", status_code=204)
def delete_checklist(checklist_id: str):
    idx = deps.find_checklist_idx(checklist_id)
    deps.app_data.checklists.pop(idx)
    save_data_bg(deps.app_data)


# ── /api/recurring ────────────────────────────────────────────────────────────


@router.get("/api/recurring")
def get_recurring():
    return {"recurring": [r.model_dump() for r in deps.app_data.recurring]}


@router.post("/api/recurring", status_code=201)
def create_recurring(body: RecurringIn):
    if body.frequency not in ("daily", "weekly", "monthly"):
        raise HTTPException(400, "frequency は daily / weekly / monthly のいずれか")
    rule = RecurringRule(
        text=body.text,
        category=body.category,
        frequency=body.frequency,
        days_of_week=body.days_of_week,
        day_of_month=body.day_of_month,
    )
    deps.app_data.recurring.append(rule)
    save_data_bg(deps.app_data)
    return rule.model_dump()


@router.patch("/api/recurring/{rule_id}")
def update_recurring(rule_id: str, body: RecurringPatch):
    rule = next((r for r in deps.app_data.recurring if r.id == rule_id), None)
    if rule is None:
        raise HTTPException(404, "定期ルールが見つかりません")
    if body.text is not None and body.text.strip():
        rule.text = body.text.strip()
    if "category" in body.model_fields_set:
        rule.category = body.category
    if body.frequency is not None:
        if body.frequency not in ("daily", "weekly", "monthly"):
            raise HTTPException(400, "frequency は daily / weekly / monthly のいずれか")
        rule.frequency = body.frequency
    if body.days_of_week is not None:
        rule.days_of_week = body.days_of_week
    if body.day_of_month is not None:
        rule.day_of_month = body.day_of_month
    save_data_bg(deps.app_data)
    return rule.model_dump()


@router.delete("/api/recurring/{rule_id}", status_code=204)
def delete_recurring(rule_id: str):
    idx = next(
        (i for i, r in enumerate(deps.app_data.recurring) if r.id == rule_id), None
    )
    if idx is None:
        raise HTTPException(404, "定期ルールが見つかりません")
    deps.app_data.recurring.pop(idx)
    save_data_bg(deps.app_data)
