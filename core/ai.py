"""core/ai.py — AI バックエンド（Gemini / Ollama / Anthropic）"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

from core.models import AppData, Category, Task

CATEGORIES: list[Category] = ["仕事", "プライベート", "買い物", "学習", "その他"]

# few-shot ファイルのパス（storage.py と同じ BASE_DIR 基準）
if getattr(sys, "frozen", False):
    _BASE_DIR = Path(sys.executable).parent
else:
    _BASE_DIR = Path(__file__).parent.parent

_FEW_SHOT_FILE = _BASE_DIR / "data" / "few_shot_examples.json"


# ── few-shot ──────────────────────────────────────────────────────────────────


def _get_few_shot_text() -> str:
    if not _FEW_SHOT_FILE.exists():
        return ""
    try:
        examples = json.loads(_FEW_SHOT_FILE.read_text(encoding="utf-8"))
        lines = ["【過去の分類実績（参考）】"]
        for cat, items in examples.items():
            for item in items:
                lines.append(f"  「{item}」→ {cat}")
        return "\n".join(lines) + "\n\n"
    except Exception:
        return ""


def update_few_shot(data: AppData) -> int:
    """
    tasks.json の todo タスクから few_shot_examples.json を更新する。
    """
    by_cat: dict[str, list[str]] = defaultdict(list)
    for task in data.tasks:
        if task.status == "todo" and task.category:
            text = task.text
            if text not in by_cat[task.category]:
                by_cat[task.category].append(text)
    examples = {cat: items[-3:] for cat, items in by_cat.items() if items}
    _FEW_SHOT_FILE.write_text(
        json.dumps(examples, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return sum(len(v) for v in examples.values())


# ── プロンプト構築 ──────────────────────────────────────────────────────────────


def _build_sort_prompt(tasks_text: str) -> str:
    cats = "・".join(CATEGORIES)
    return (
        f"{_get_few_shot_text()}"
        f"以下のタスクリストを「{cats}」のいずれかに分類してください。\n"
        f"タイムスタンプは [YYYY-MM-DD HH:MM] の形式をそのまま保持してください。\n"
        f"空のカテゴリは省略してください。\n\n"
        f"タスクリスト:\n{tasks_text}\n\n"
        f"以下の JSON 形式のみで返してください（説明文不要）:\n"
        f'{{"tasks": [{{"text": "タスク本文", "category": "カテゴリ"}}]}}'
    )


# ── Gemini ────────────────────────────────────────────────────────────────────


def sort_with_gemini(tasks: list[Task], api_key: str) -> list[Task]:
    """Gemini 2.5 Flash でタスクを分類して返す。"""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise RuntimeError(
            "google-genai が未インストールです: pip install google-genai"
        )

    tasks_text = "\n".join(f"- {t.text}" for t in tasks)
    client = genai.Client(api_key=api_key)

    # 構造化出力を試みる
    try:
        from pydantic import BaseModel
        from typing import Literal

        class _Item(BaseModel):
            text: str
            category: Literal["仕事", "プライベート", "買い物", "学習", "その他"]

        class _Result(BaseModel):
            tasks: list[_Item]

        prompt = (
            _get_few_shot_text()
            + f"以下のタスクを {CATEGORIES} のいずれかに分類してください。\n\n{tasks_text}"
        )
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_Result,
                temperature=0.1,
            ),
        )
        result = _Result.model_validate_json(response.text)
        return _apply_categories(
            tasks, {item.text: item.category for item in result.tasks}
        )
    except Exception:
        pass

    # フォールバック: JSON テキスト出力
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=_build_sort_prompt(tasks_text),
        config=types.GenerateContentConfig(temperature=0.1),
    )
    return _parse_json_response(tasks, response.text)


# ── Ollama ────────────────────────────────────────────────────────────────────


def sort_with_ollama(
    tasks: list[Task], model: str = "phi4", host: str = "http://localhost:11434"
) -> list[Task]:
    try:
        import ollama as ollama_lib
    except ImportError:
        raise RuntimeError("ollama が未インストールです: pip install ollama")

    tasks_text = "\n".join(f"- {t.text}" for t in tasks)
    prompt = (
        f"以下のタスクを 'その他','仕事','プライベート','買い物','学習' に分類し、"
        f"必ず次の JSON 形式のみを返すこと（説明文不要）:\n"
        f'{{"tasks": [{{"text": "...", "category": "..."}}]}}\n\n{tasks_text}'
    )
    response = ollama_lib.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        format="json",
    )
    return _parse_json_response(tasks, response["message"]["content"])


def ollama_is_running(host: str = "http://localhost:11434") -> bool:
    try:
        import urllib.request

        urllib.request.urlopen(host, timeout=1)
        return True
    except Exception:
        return False


# ── Anthropic ─────────────────────────────────────────────────────────────────


def sort_with_anthropic(tasks: list[Task], api_key: str) -> list[Task]:
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic が未インストールです: pip install anthropic")

    tasks_text = "\n".join(f"- {t.text}" for t in tasks)
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        messages=[{"role": "user", "content": _build_sort_prompt(tasks_text)}],
    )
    return _parse_json_response(tasks, message.content[0].text)


# ── スプリット提案 ────────────────────────────────────────────────────────────

SPLIT_THRESHOLD = 5


def suggest_splits(data: AppData, api_key: str) -> list[dict]:
    """
    todo タスクが SPLIT_THRESHOLD 件以上溜まったカテゴリに対し、
    タスク内容に即したサブタグを AI が提案する。
    戻り値: [{"task_id": str, "text": str, "category": str, "suggested_tag": str}]
    """
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise RuntimeError(
            "google-genai が未インストールです: pip install google-genai"
        )

    todo_tasks = [t for t in data.tasks if t.status == "todo"]

    by_cat: dict[str, list] = defaultdict(list)
    for t in todo_tasks:
        by_cat[t.category or "その他"].append(t)

    overloaded = {
        cat: tasks for cat, tasks in by_cat.items() if len(tasks) >= SPLIT_THRESHOLD
    }
    if not overloaded:
        return []

    client = genai.Client(api_key=api_key)
    results = []

    for cat, tasks in overloaded.items():
        tasks_text = "\n".join(f"- id={t.id} text={t.text}" for t in tasks)
        prompt = (
            f"以下は「{cat}」カテゴリのタスク一覧です。\n"
            f"各タスクの内容に合わせて、具体的で短いサブタグ（グループ名）を日本語で提案してください。\n"
            f"サブタグはタスクの実際の内容を反映した具体的な名前にしてください（例: 「qcatchの実装」「家計管理」「資料作成」など）。\n"
            f"自然にグループ化できるタスクだけをまとめてください。無理に全タスクを別グループにしなくていいです。\n"
            f"明確なグループが見当たらないタスクには null を設定してください。\n\n"
            f"{tasks_text}\n\n"
            f"以下の JSON 形式のみで返してください（説明文不要）:\n"
            f'{{"items": [{{"id": "...", "tag": "サブタグ名 or null"}}]}}'
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.2),
        )

        try:
            text = response.text.strip()
            if text.startswith("```"):
                lines = text.splitlines()
                text = "\n".join(
                    lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
                )
            raw = json.loads(text)
            task_map = {t.id: t for t in tasks}
            for item in raw.get("items", []):
                tid = item.get("id", "")
                tag = item.get("tag")
                if tid in task_map and tag and tag not in ("null", None):
                    t = task_map[tid]
                    results.append(
                        {
                            "task_id": tid,
                            "text": t.text,
                            "category": cat,
                            "suggested_tag": str(tag),
                        }
                    )
        except Exception:
            pass

    return results


# ── タグ提案 ──────────────────────────────────────────────────────────────────


def suggest_tags(data: AppData, api_key: str) -> list[dict]:
    """
    todo タスクのカテゴリ変更案を AI が提案する。
    戻り値: [{"id": str, "text": str, "current": str, "suggested": str}]
    """
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise RuntimeError(
            "google-genai が未インストールです: pip install google-genai"
        )

    todo_tasks = [t for t in data.tasks if t.status == "todo"]
    if not todo_tasks:
        return []

    tasks_text = "\n".join(
        f"- id={t.id} category={t.category} text={t.text}" for t in todo_tasks
    )
    prompt = (
        f"以下のタスク一覧のカテゴリが正しいか確認し、変更すべきものだけ提案してください。\n"
        f"カテゴリは {CATEGORIES} のいずれかです。\n"
        f"変更不要なものは含めないでください。\n\n{tasks_text}\n\n"
        f"JSON 形式のみで返してください:\n"
        f'{{"suggestions": [{{"id": "...", "suggested": "カテゴリ"}}]}}'
    )

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.1),
    )

    try:
        raw = json.loads(response.text)
        suggestions = raw.get("suggestions", [])
    except Exception:
        return []

    task_map = {t.id: t for t in todo_tasks}
    result = []
    for s in suggestions:
        tid = s.get("id", "")
        suggested = s.get("suggested", "")
        if tid in task_map and suggested in CATEGORIES:
            t = task_map[tid]
            if suggested != t.category:
                result.append(
                    {
                        "id": tid,
                        "text": t.text,
                        "current": t.category,
                        "suggested": suggested,
                    }
                )
    return result


# ── 共通ヘルパー ──────────────────────────────────────────────────────────────


def _parse_json_response(tasks: list[Task], text: str) -> list[Task]:
    """JSON レスポンスをパースしてカテゴリを適用する。"""
    # コードブロック除去
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        data = json.loads(text)
        items = data.get("tasks", [])
        cat_map = {
            item["text"]: item["category"]
            for item in items
            if "text" in item and "category" in item
        }
        return _apply_categories(tasks, cat_map)
    except Exception:
        return tasks


def _apply_categories(tasks: list[Task], cat_map: dict[str, str]) -> list[Task]:
    """テキストをキーにカテゴリを適用する（部分一致フォールバックあり）。"""
    for task in tasks:
        # 完全一致
        if task.text in cat_map:
            cat = cat_map[task.text]
            if cat in CATEGORIES:
                task.category = cat
                task.status = "todo"
            continue
        # 部分一致（Gemini がテキストを短縮する場合の対策）
        for key, cat in cat_map.items():
            if key in task.text or task.text in key:
                if cat in CATEGORIES:
                    task.category = cat
                    task.status = "todo"
                break
        else:
            task.category = "その他"
            task.status = "todo"
    return tasks
