"""web/routers/flashcards.py — /api/flashcards/*"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.models import FlashCard
from core.storage import (
    load_flashcards,
    save_flashcards,
    save_flashcards_bg,
    sm2_update,
)

router = APIRouter()


class FlashCardIn(BaseModel):
    front: str
    back: str
    example: str = ""
    source: str = "manual"
    source_ref: str = ""


class FlashCardReview(BaseModel):
    quality: int  # 0=忘れた, 1=難しい, 2=完璧


@router.get("/api/flashcards")
def list_flashcards():
    deck = load_flashcards()
    return {"cards": [c.model_dump() for c in deck.cards]}


@router.get("/api/flashcards/due")
def due_flashcards():
    today = date.today().isoformat()
    deck = load_flashcards()
    due = [c for c in deck.cards if c.next_review <= today]
    return {"cards": [c.model_dump() for c in due]}


@router.post("/api/flashcards", status_code=201)
def create_flashcard(body: FlashCardIn):
    deck = load_flashcards()
    card = FlashCard(
        front=body.front,
        back=body.back,
        example=body.example,
        source=body.source,
        source_ref=body.source_ref,
    )
    deck.cards.append(card)
    save_flashcards(deck)
    return card.model_dump()


@router.patch("/api/flashcards/{card_id}/review")
def review_flashcard(card_id: str, body: FlashCardReview):
    deck = load_flashcards()
    card = next((c for c in deck.cards if c.id == card_id), None)
    if not card:
        raise HTTPException(404, "カードが見つかりません")
    sm2_update(card, body.quality)
    save_flashcards_bg(deck)
    return card.model_dump()


@router.delete("/api/flashcards/{card_id}", status_code=204)
def delete_flashcard(card_id: str):
    deck = load_flashcards()
    idx = next((i for i, c in enumerate(deck.cards) if c.id == card_id), None)
    if idx is None:
        raise HTTPException(404, "カードが見つかりません")
    deck.cards.pop(idx)
    save_flashcards_bg(deck)
