"""core/chat.py — 会話型UI: Gemini Function Calling"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from typing import Optional

import json
import sys
from pathlib import Path

from core.models import AppData, Category, Task
from core import storage

CATEGORIES: list[Category] = ["仕事", "プライベート", "買い物", "学習", "その他"]

if getattr(sys, "frozen", False):
    _BASE_DIR = Path(sys.executable).parent
else:
    _BASE_DIR = Path(__file__).parent.parent

_HISTORY_FILE = _BASE_DIR / "data" / "chat_history.json"

# 会話履歴（起動時にファイルから復元）
_history: list[dict] = []  # {"role": "user"|"model", "text": str}


def _load_history() -> None:
    global _history
    if _HISTORY_FILE.exists():
        try:
            _history = json.loads(_HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            _history = []


def _save_history() -> None:
    try:
        _HISTORY_FILE.write_text(
            json.dumps(_history[-20:], ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def clear_history() -> None:
    global _history
    _history = []
    _save_history()


_load_history()


# ── システムプロンプト ────────────────────────────────────────────────────────


_WEEKDAY_JA = ["月", "火", "水", "木", "金", "土", "日"]


def _calendar_status_line() -> str:
    try:
        from core import google_sync

        if google_sync.is_authenticated():
            return "- Google Calendar: 連携済み（予定の確認・追加が可能）"
    except Exception:
        pass
    return (
        "- Google Calendar: 未連携（設定タブから認証すると予定の確認・追加ができます）"
    )


def _build_system_prompt(data: AppData) -> str:
    today = date.today()
    today_str = f"{today.year}年{today.month}月{today.day}日（{_WEEKDAY_JA[today.weekday()]}曜日）"
    todo_count = sum(1 for t in data.tasks if t.status == "todo")
    inbox_count = sum(1 for t in data.tasks if t.status == "inbox")
    longterm_count = sum(1 for t in data.tasks if t.status == "longterm")
    done_today = sum(
        1
        for t in data.tasks
        if t.status == "done"
        and t.completed_at
        and t.completed_at.date() == date.today()
    )
    cl_active = sum(1 for cl in data.checklists if any(not i.done for i in cl.items))
    rec_count = len(data.recurring)

    return (
        f"今日の日付: {today_str}\n\n"
        "あなたはタスク管理の思考パートナーです。日本語で返答してください。\n\n"
        "【返答の原則】\n"
        "- タスクの一覧をそのまま箇条書きで返すのは禁止。ダッシュボードと同じ情報を出すだけでは価値がない。\n"
        "- パターン・優先順位・懸念点・今日のフォーカスを分析して、洞察のある返答をすること。\n"
        "- 「なぜそれが重要か」「次に何をすべきか」を必ず含めること。\n"
        "- タスクIDは内部処理にのみ使用し、ユーザーへの返答には絶対に含めないこと。\n"
        "- タスクを完了する際は先に get_tasks でIDを確認してから complete_task を使うこと。\n"
        "- 期日・重要度・カテゴリの変更は先に get_tasks でIDを確認してから update_task を使うこと。\n"
        "- 状況を把握したい場合は get_analysis を使うと滞留・傾向・優先度の分析データが得られる。\n"
        "- get_tasks で status=done は絶対に指定しないこと。完了タスクは原則として参照しない。\n"
        "- 今日/今週の予定を聞かれたら get_calendar_events を使うこと（Calendar 連携済みの場合のみ）。\n\n"
        "【現在の概況】\n"
        f"- Inbox（未分類）: {inbox_count} 件\n"
        f"- Todo（分類済み）: {todo_count} 件\n"
        f"- 長期タスク（カウント対象外）: {longterm_count} 件\n"
        f"- 本日完了: {done_today} 件\n"
        f"- アクティブなチェックリスト: {cl_active} 件\n"
        f"- 定期タスクルール: {rec_count} 件\n" + _calendar_status_line()
    )


# ── ツール定義 ────────────────────────────────────────────────────────────────


def _build_tools():
    from google.genai import types

    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_tasks",
                description="タスク一覧を取得する。完了タスク（done）は取得不可。",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "status": types.Schema(
                            type=types.Type.STRING,
                            description="todo（デフォルト）/ inbox / longterm / all（todo+inbox+longtermの合計）",
                        ),
                        "category": types.Schema(
                            type=types.Type.STRING,
                            description="仕事 / プライベート / 買い物 / 学習 / その他",
                        ),
                    },
                ),
            ),
            types.FunctionDeclaration(
                name="add_task",
                description="新しいタスクを追加する。「明日」「来週金曜」などの相対表現は今日の日付を基準にISO 8601形式に変換してdue_dateに設定する。",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "text": types.Schema(
                            type=types.Type.STRING, description="タスクの内容"
                        ),
                        "category": types.Schema(
                            type=types.Type.STRING,
                            description="カテゴリ（任意）: 仕事 / プライベート / 買い物 / 学習 / その他",
                        ),
                        "due_date": types.Schema(
                            type=types.Type.STRING,
                            description="期日（ISO 8601形式: YYYY-MM-DDTHH:MM:SS）。「明日」「来週」等は今日の日付を基準に計算して設定する。任意。",
                        ),
                    },
                    required=["text"],
                ),
            ),
            types.FunctionDeclaration(
                name="complete_task",
                description="タスクを完了にする。先に get_tasks でIDを確認してから使うこと。",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "task_ids": types.Schema(
                            type=types.Type.ARRAY,
                            items=types.Schema(type=types.Type.STRING),
                            description="完了にするタスクIDのリスト（IDの先頭8文字でも可）",
                        ),
                    },
                    required=["task_ids"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_checklists",
                description="チェックリスト一覧と進捗を取得する",
                parameters=types.Schema(type=types.Type.OBJECT, properties={}),
            ),
            types.FunctionDeclaration(
                name="get_summary",
                description="タスク全体の概要サマリーを取得する",
                parameters=types.Schema(type=types.Type.OBJECT, properties={}),
            ),
            types.FunctionDeclaration(
                name="get_analysis",
                description="タスクのパターン・滞留・傾向・優先度の分析データを取得する。状況把握や優先順位付けに使う。",
                parameters=types.Schema(type=types.Type.OBJECT, properties={}),
            ),
            types.FunctionDeclaration(
                name="get_recent_diaries",
                description="過去の日記エントリを取得する。振り返りや来週の計画立案に使う。",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "days": types.Schema(
                            type=types.Type.INTEGER,
                            description="取得する日数（デフォルト7、最大30）",
                        ),
                    },
                ),
            ),
            types.FunctionDeclaration(
                name="update_task",
                description=(
                    "タスクの期日・重要度・カテゴリを変更する。"
                    "先に get_tasks でIDを確認してから使うこと。"
                    "「〇〇の期日を明日に変更して」「△△を高優先度にして」などに使う。"
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "task_id": types.Schema(
                            type=types.Type.STRING,
                            description="変更するタスクのID（先頭8文字でも可）",
                        ),
                        "due_date": types.Schema(
                            type=types.Type.STRING,
                            description=(
                                "新しい期日（ISO 8601形式: YYYY-MM-DDTHH:MM:SS）。"
                                "「明日」「来週金曜」等は今日の日付を基準に変換して設定する。"
                                "期日を削除する場合は 'clear' を指定する。"
                            ),
                        ),
                        "importance": types.Schema(
                            type=types.Type.STRING,
                            description="重要度: high / medium / low",
                        ),
                        "category": types.Schema(
                            type=types.Type.STRING,
                            description="カテゴリ: 仕事 / プライベート / 買い物 / 学習 / その他",
                        ),
                    },
                    required=["task_id"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_calendar_events",
                description=(
                    "Google Calendar から今日以降の予定を取得する。"
                    "「今日の予定は？」「今週のスケジュールを教えて」などに使う。"
                    "Google Calendar 連携済みの場合のみ使用可能。"
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "days": types.Schema(
                            type=types.Type.INTEGER,
                            description="取得日数。1=今日のみ、7=今後1週間、14=今後2週間（最大30）",
                        ),
                    },
                ),
            ),
            types.FunctionDeclaration(
                name="prepare_calendar_event",
                description=(
                    "ユーザーが時間帯のカレンダー予定（ミーティング・アポイント等）を追加したい場合に使う。"
                    "確認画面を表示し、ユーザーが内容を確認・修正してから追加できる。"
                    "タイトル・開始日時が揃っている場合のみ呼び出すこと。"
                    "情報が不足している場合はユーザーに質問して補完してから呼び出すこと。"
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "title": types.Schema(
                            type=types.Type.STRING,
                            description="イベントのタイトル",
                        ),
                        "start_dt": types.Schema(
                            type=types.Type.STRING,
                            description="開始日時 ISO 8601形式 (YYYY-MM-DDTHH:MM:SS)",
                        ),
                        "end_dt": types.Schema(
                            type=types.Type.STRING,
                            description="終了日時 ISO 8601形式。省略時は開始から1時間後。",
                        ),
                        "description": types.Schema(
                            type=types.Type.STRING,
                            description="イベントの説明（任意）",
                        ),
                    },
                    required=["title", "start_dt"],
                ),
            ),
        ]
    )


# ── 関数実行 ──────────────────────────────────────────────────────────────────


def _execute_fn(name: str, args: dict, data: AppData) -> tuple[str, list[dict]]:
    """関数を実行して (結果テキスト, UIアクション) を返す。"""
    actions: list[dict] = []

    if name == "get_tasks":
        status = args.get("status", "todo")
        category = args.get("category")
        tasks = data.tasks
        if status == "all":
            # 完了・削除済みは含めない
            tasks = [t for t in tasks if t.status not in ("done", "trashed")]
        elif status in ("done", "trashed"):
            # 完了・削除済みは参照禁止
            return (
                "完了タスクは原則として参照しません。todo / inbox / longterm を指定してください。",
                actions,
            )
        else:
            tasks = [t for t in tasks if t.status == status]
        if category:
            tasks = [t for t in tasks if t.category == category]
        if not tasks:
            return "該当するタスクはありません。", actions
        # IDはcomplete_task呼び出し用。ユーザーへの返答には含めないようsystem_promptで指示済み
        lines = [
            f"- [id:{t.id[:8]}] [{t.category or '未分類'}] {t.text}"
            + (f" [期日:{t.due_date.strftime('%Y/%m/%d')}]" if t.due_date else "")
            for t in tasks[:30]
        ]
        note = "※IDは内部処理専用。ユーザーへの返答にはタスク名のみ使うこと。"
        return f"{note}\n{len(tasks)} 件:\n" + "\n".join(lines), actions

    elif name == "add_task":
        text = args.get("text", "").strip()
        if not text:
            return "タスクの内容が空です。", actions
        category = args.get("category")
        if category not in CATEGORIES:
            category = None
        due_date = None
        due_date_str = args.get("due_date", "")
        if due_date_str:
            try:
                due_date = datetime.fromisoformat(due_date_str)
            except (ValueError, TypeError):
                pass
        task = Task(
            text=text,
            status="todo" if category else "inbox",
            category=category,
            due_date=due_date,
        )
        data.tasks.append(task)
        storage.save_data(data)
        actions.append({"type": "refresh"})
        due_str = f"（期日: {due_date.strftime('%Y/%m/%d')}）" if due_date else ""
        return f"「{text}」を追加しました{due_str}。", actions

    elif name == "complete_task":
        task_ids = args.get("task_ids", [])
        completed = []
        now = datetime.now()
        for tid in task_ids:
            for task in data.tasks:
                if task.id == tid or task.id.startswith(tid):
                    task.status = "done"
                    task.completed_at = now
                    completed.append(task.text)
                    break
        if completed:
            storage.save_data(data)
            actions.append({"type": "refresh"})
            return f"完了にしました: {' / '.join(completed)}", actions
        return (
            "該当するタスクIDが見つかりませんでした。get_tasks でIDを確認してください。",
            actions,
        )

    elif name == "get_checklists":
        if not data.checklists:
            return "チェックリストはありません。", actions
        parts = []
        for cl in data.checklists:
            done = sum(1 for i in cl.items if i.done)
            total = len(cl.items)
            remaining = [i.text for i in cl.items if not i.done]
            due = f" 期日:{cl.due_date.strftime('%Y/%m/%d')}" if cl.due_date else ""
            snippet = "、".join(remaining[:5]) + ("…" if len(remaining) > 5 else "")
            parts.append(f"「{cl.name}」{done}/{total}完了{due}\n  残り: {snippet}")
        actions.append({"type": "switch_tab", "tab": "checklists"})
        return "\n\n".join(parts), actions

    elif name == "get_summary":
        todo = [t for t in data.tasks if t.status == "todo"]
        inbox_count = sum(1 for t in data.tasks if t.status == "inbox")
        done_today = sum(
            1
            for t in data.tasks
            if t.status == "done"
            and t.completed_at
            and t.completed_at.date() == date.today()
        )
        cat_counts = Counter(t.category for t in todo if t.category)
        cat_str = " / ".join(f"{k}:{v}" for k, v in cat_counts.most_common())
        return (
            f"Inbox: {inbox_count}件 | Todo: {len(todo)}件 ({cat_str}) | 本日完了: {done_today}件\n"
            f"チェックリスト: {len(data.checklists)}件 | 定期タスク: {len(data.recurring)}件"
        ), actions

    elif name == "get_analysis":
        from datetime import timedelta

        now = datetime.now()
        week_ago = now - timedelta(days=7)
        todo = [t for t in data.tasks if t.status == "todo"]
        inbox_count = sum(1 for t in data.tasks if t.status == "inbox")

        # 滞留タスク（7日以上 todo のまま）
        stuck = [t for t in todo if t.created_at and (now - t.created_at).days >= 7]
        oldest = (
            max(todo, key=lambda t: (now - t.created_at).days, default=None)
            if todo
            else None
        )

        # カテゴリ分布
        cat_dist = Counter(t.category or "未分類" for t in todo)

        # 今週の完了数
        done_week = sum(
            1
            for t in data.tasks
            if t.status == "done" and t.completed_at and t.completed_at >= week_ago
        )
        done_today_count = sum(
            1
            for t in data.tasks
            if t.status == "done"
            and t.completed_at
            and t.completed_at.date() == date.today()
        )

        # 期日切れチェックリスト
        overdue_cls = [
            cl
            for cl in data.checklists
            if cl.due_date and cl.due_date < now and any(not i.done for i in cl.items)
        ]

        lines = [
            f"【タスク分析】",
            f"Todo 合計: {len(todo)} 件 / Inbox 未分類: {inbox_count} 件",
            f"滞留タスク（7日以上）: {len(stuck)} 件",
        ]
        if oldest:
            age = (now - oldest.created_at).days
            lines.append(
                f"最古のタスク: 「{oldest.text}」（{age}日前、{oldest.category or '未分類'}）"
            )
        if stuck:
            lines.append(
                "滞留中のタスク例: " + " / ".join(f"「{t.text}」" for t in stuck[:5])
            )
        lines.append(
            "カテゴリ分布: "
            + " / ".join(f"{k}:{v}件" for k, v in cat_dist.most_common())
        )
        lines.append(f"今週完了: {done_week} 件 / 本日完了: {done_today_count} 件")
        if overdue_cls:
            lines.append(
                f"期日切れチェックリスト: {len(overdue_cls)} 件 — "
                + " / ".join(f"「{cl.name}」" for cl in overdue_cls[:3])
            )
        return "\n".join(lines), actions

    elif name == "get_recent_diaries":
        days = min(int(args.get("days", 7)), 30)
        diary_data = storage.load_diary()
        if not diary_data.entries:
            return "日記エントリはまだありません。", actions
        from datetime import timedelta

        cutoff = (date.today() - timedelta(days=days)).isoformat()
        recent = {
            k: v
            for k, v in sorted(diary_data.entries.items(), reverse=True)
            if k >= cutoff
        }
        if not recent:
            return f"直近{days}日間の日記エントリはありません。", actions
        parts = [
            f"【{k}】\n{v.content[:300]}{'…' if len(v.content) > 300 else ''}"
            for k, v in recent.items()
        ]
        return (
            f"直近{days}日間の日記（{len(recent)}件）:\n\n" + "\n\n".join(parts),
            actions,
        )

    elif name == "update_task":
        task_id = args.get("task_id", "").strip()
        if not task_id:
            return (
                "タスクIDが指定されていません。get_tasks でIDを確認してください。",
                actions,
            )

        target = next(
            (t for t in data.tasks if t.id == task_id or t.id.startswith(task_id)),
            None,
        )
        if not target:
            return (
                "該当するタスクIDが見つかりませんでした。get_tasks でIDを確認してください。",
                actions,
            )

        changes = []

        due_date_str = args.get("due_date")
        if due_date_str is not None:
            if due_date_str.lower() == "clear":
                target.due_date = None
                changes.append("期日を削除")
            else:
                try:
                    target.due_date = datetime.fromisoformat(due_date_str)
                    changes.append(
                        f"期日を {target.due_date.strftime('%Y/%m/%d')} に変更"
                    )
                except (ValueError, TypeError):
                    return (
                        "期日の形式が正しくありません（YYYY-MM-DDTHH:MM:SS 形式）。",
                        actions,
                    )

        importance = args.get("importance")
        if importance is not None:
            if importance not in ("high", "medium", "low"):
                return (
                    "重要度は high / medium / low のいずれかで指定してください。",
                    actions,
                )
            target.importance = importance
            label = {"high": "高", "medium": "中", "low": "低"}[importance]
            changes.append(f"重要度を「{label}」に変更")

        category = args.get("category")
        if category is not None:
            if category not in CATEGORIES:
                return (
                    f"カテゴリは {' / '.join(CATEGORIES)} のいずれかで指定してください。",
                    actions,
                )
            target.category = category
            if target.status == "inbox":
                target.status = "todo"
            changes.append(f"カテゴリを「{category}」に変更")

        if not changes:
            return (
                "変更内容が指定されていません（due_date / importance / category のいずれかを指定してください）。",
                actions,
            )

        storage.save_data(data)
        actions.append({"type": "refresh"})
        return f"「{target.text}」を更新しました: {' / '.join(changes)}", actions

    elif name == "get_calendar_events":
        days = max(1, min(int(args.get("days", 1)), 30))
        try:
            from core import google_sync

            events = google_sync.get_calendar_events(days=days)
        except RuntimeError as e:
            return str(e), actions
        except Exception as e:
            return f"カレンダー取得エラー: {e}", actions

        if not events:
            label = "今日" if days == 1 else f"今後{days}日間"
            return f"{label}の予定はありません。", actions

        _WEEKDAY_JA_SHORT = ["月", "火", "水", "木", "金", "土", "日"]
        lines = []
        for ev in events:
            try:
                start_dt = datetime.fromisoformat(ev["start"])
                start_str = (
                    f"{start_dt.month}/{start_dt.day}"
                    f"({_WEEKDAY_JA_SHORT[start_dt.weekday()]}) "
                    f"{start_dt.strftime('%H:%M')}"
                )
            except Exception:
                start_str = ev["start"]
            try:
                end_dt = datetime.fromisoformat(ev["end"])
                end_str = end_dt.strftime("%H:%M")
            except Exception:
                end_str = ev["end"]
            desc = f" — {ev['description'][:60]}" if ev.get("description") else ""
            lines.append(f"- {start_str}〜{end_str} {ev['title']}{desc}")

        label = "今日" if days == 1 else f"今後{days}日間"
        return f"{label}の予定（{len(events)}件）:\n" + "\n".join(lines), actions

    elif name == "prepare_calendar_event":
        from datetime import timedelta

        title = args.get("title", "").strip()
        start_dt_str = args.get("start_dt", "")
        end_dt_str = args.get("end_dt", "")
        description = args.get("description", "")

        if not title or not start_dt_str:
            return "タイトルと開始日時が必要です。", actions
        try:
            start_dt = datetime.fromisoformat(start_dt_str)
        except ValueError:
            return (
                "開始日時の形式が正しくありません（YYYY-MM-DDTHH:MM:SS 形式で指定してください）。",
                actions,
            )

        if end_dt_str:
            try:
                end_dt = datetime.fromisoformat(end_dt_str)
            except ValueError:
                end_dt = start_dt + timedelta(hours=1)
        else:
            end_dt = start_dt + timedelta(hours=1)

        actions.append(
            {
                "type": "calendar_confirm",
                "event": {
                    "title": title,
                    "start_dt": start_dt.isoformat(),
                    "end_dt": end_dt.isoformat(),
                    "description": description,
                },
            }
        )
        return (
            "カレンダー追加の確認画面を表示しました。ユーザーが内容を確認・修正して承認すると追加されます。",
            actions,
        )

    return f"未知の関数: {name}", actions


# ── メイン関数 ────────────────────────────────────────────────────────────────


def _resolve_fn_calls(
    user_message: str,
    data: AppData,
    api_key: str,
) -> tuple[list, list[dict], bool]:
    """
    Function Calling ループを非ストリーミングで回し、
    (最終コンテンツリスト, ui_actions, had_function_calls) を返す。
    最後のモデル応答（テキスト）は contents に含まれない。
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    system_prompt = _build_system_prompt(data)
    tools = _build_tools()

    contents: list = []
    for msg in _history[-10:]:
        contents.append(
            types.Content(role=msg["role"], parts=[types.Part(text=msg["text"])])
        )
    contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

    ui_actions: list[dict] = []
    had_fn = False

    for _ in range(4):
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                tools=[tools],
                system_instruction=system_prompt,
                temperature=0.3,
            ),
        )
        model_content = response.candidates[0].content
        fn_calls = [
            p.function_call
            for p in model_content.parts
            if hasattr(p, "function_call") and p.function_call
        ]

        if not fn_calls:
            if not had_fn:
                # 最初のターンがテキスト直接応答 → contents にモデル応答を追加して終わり
                contents.append(model_content)
            break

        had_fn = True
        contents.append(model_content)
        fn_response_parts = []
        for fc in fn_calls:
            result, actions = _execute_fn(fc.name, dict(fc.args), data)
            ui_actions.extend(actions)
            fn_response_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=fc.name,
                        response={"result": result},
                    )
                )
            )
        contents.append(types.Content(role="user", parts=fn_response_parts))

    return contents, ui_actions, had_fn


def chat_stream(user_message: str, data: AppData, api_key: str):
    """
    ストリーミング版チャット。Generator[dict, None, None]:
      {"type": "text", "chunk": str}
      {"type": "done", "actions": list}
    """
    global _history

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        yield {"type": "text", "chunk": "google-genai が未インストールです"}
        yield {"type": "done", "actions": []}
        return

    try:
        contents, ui_actions, had_fn = _resolve_fn_calls(user_message, data, api_key)
    except Exception as e:
        yield {"type": "text", "chunk": f"エラー: {e}"}
        yield {"type": "done", "actions": []}
        return

    client = genai.Client(api_key=api_key)
    system_prompt = _build_system_prompt(data)
    final_text = ""

    if had_fn:
        # Function Call 後 → ツールなしでストリーミング最終応答
        try:
            stream = client.models.generate_content_stream(
                model="gemini-2.5-flash",
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.3,
                ),
            )
            for chunk in stream:
                if chunk.text:
                    final_text += chunk.text
                    yield {"type": "text", "chunk": chunk.text}
        except Exception as e:
            yield {"type": "text", "chunk": f"ストリームエラー: {e}"}
    else:
        # 直接テキスト応答（最後の model Content からテキスト取得）
        last = contents[-1]
        text = (
            "".join(p.text for p in last.parts if hasattr(p, "text") and p.text)
            if hasattr(last, "parts")
            else ""
        )
        final_text = text or "（応答がありませんでした）"
        yield {"type": "text", "chunk": final_text}

    _history.append({"role": "user", "text": user_message})
    _history.append({"role": "model", "text": final_text})
    if len(_history) > 20:
        _history = _history[-20:]
    _save_history()

    yield {"type": "done", "actions": ui_actions}


def briefing_stream(data: AppData, api_key: str):
    """
    朝のブリーフィング専用ストリーム。会話履歴を使わず独立して実行する。
    直近24h完了タスクと todo タスクをコンテキストに、トップ3を提示する。
    yield フォーマットは chat_stream と同一。
    """
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        yield {"type": "text", "chunk": "google-genai が未インストールです"}
        yield {"type": "done", "actions": []}
        return

    from datetime import timedelta

    now = datetime.now()
    cutoff = now - timedelta(hours=24)

    done_recent = [
        t
        for t in data.tasks
        if t.status == "done" and t.completed_at and t.completed_at >= cutoff
    ]
    todo_tasks = [t for t in data.tasks if t.status == "todo"]

    done_lines = "\n".join(f"- {t.text}" for t in done_recent) or "（なし）"
    todo_lines = (
        "\n".join(
            f"- [{t.category or '未分類'}] {t.text} (作成: {t.created_at.strftime('%Y-%m-%d') if t.created_at else '不明'})"
            for t in todo_tasks
        )
        or "（なし）"
    )

    system_prompt = (
        "あなたは有能なタスク管理アシスタントです。日本語で返答してください。\n"
        "過去24時間の完了タスク（実績）をまず一言で労い、"
        "未完了タスクから『今日絶対に終わらせるべきトップ3』を選んでください。\n"
        "長ったらしい前置きは不要。マークダウンの箇条書きで、"
        "選んだ理由をポジティブかつ簡潔に一言添えること。"
    )
    context = (
        f"【直近24時間で完了したタスク】\n{done_lines}\n\n"
        f"【現在の未完了タスク一覧】\n{todo_lines}"
    )

    try:
        client = genai.Client(api_key=api_key)
        stream = client.models.generate_content_stream(
            model="gemini-2.5-flash",
            contents=[types.Content(role="user", parts=[types.Part(text=context)])],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.4,
            ),
        )
        for chunk in stream:
            if chunk.text:
                yield {"type": "text", "chunk": chunk.text}
    except Exception as e:
        yield {"type": "text", "chunk": f"エラー: {e}"}

    yield {"type": "done", "actions": []}


# writing_suggest_stream / diary_draft_stream → core/writing.py
# lang_practice_stream / lang_correct_stream / lang_discuss_stream → core/lang.py


def chat(user_message: str, data: AppData, api_key: str) -> tuple[str, list[dict]]:
    """非ストリーミング版（後方互換）。"""
    global _history

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return "google-genai が未インストールです: pip install google-genai", []

    contents, ui_actions, had_fn = _resolve_fn_calls(user_message, data, api_key)
    client = genai.Client(api_key=api_key)
    system_prompt = _build_system_prompt(data)
    final_text = ""

    if had_fn:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.3,
            ),
        )
        final_text = response.text or ""
    else:
        last = contents[-1]
        final_text = (
            "".join(p.text for p in last.parts if hasattr(p, "text") and p.text)
            if hasattr(last, "parts")
            else ""
        )

    _history.append({"role": "user", "text": user_message})
    _history.append({"role": "model", "text": final_text})
    if len(_history) > 20:
        _history = _history[-20:]
    _save_history()

    return final_text or "（応答がありませんでした）", ui_actions
