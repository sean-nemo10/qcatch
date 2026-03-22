"""core/chat.py — 会話型UI: Gemini Function Calling"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from typing import Optional

from core.models import AppData, Category, Task
from core import storage

CATEGORIES: list[Category] = ["仕事", "プライベート", "買い物", "学習", "その他"]

# 会話履歴（サーバーメモリ上、再起動でリセット）
_history: list[dict] = []  # {"role": "user"|"model", "text": str}


def clear_history() -> None:
    global _history
    _history = []


# ── システムプロンプト ────────────────────────────────────────────────────────


def _build_system_prompt(data: AppData) -> str:
    todo_count = sum(1 for t in data.tasks if t.status == "todo")
    inbox_count = sum(1 for t in data.tasks if t.status == "inbox")
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
        "あなたはタスク管理の思考パートナーです。日本語で返答してください。\n\n"
        "【返答の原則】\n"
        "- タスクの一覧をそのまま箇条書きで返すのは禁止。ダッシュボードと同じ情報を出すだけでは価値がない。\n"
        "- パターン・優先順位・懸念点・今日のフォーカスを分析して、洞察のある返答をすること。\n"
        "- 「なぜそれが重要か」「次に何をすべきか」を必ず含めること。\n"
        "- タスクIDは内部処理にのみ使用し、ユーザーへの返答には絶対に含めないこと。\n"
        "- タスクを完了する際は先に get_tasks でIDを確認してから complete_task を使うこと。\n"
        "- 状況を把握したい場合は get_analysis を使うと滞留・傾向・優先度の分析データが得られる。\n\n"
        "【現在の概況】\n"
        f"- Inbox（未分類）: {inbox_count} 件\n"
        f"- Todo（分類済み）: {todo_count} 件\n"
        f"- 本日完了: {done_today} 件\n"
        f"- アクティブなチェックリスト: {cl_active} 件\n"
        f"- 定期タスクルール: {rec_count} 件"
    )


# ── ツール定義 ────────────────────────────────────────────────────────────────


def _build_tools():
    from google.genai import types

    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_tasks",
                description="タスク一覧を取得する",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "status": types.Schema(
                            type=types.Type.STRING,
                            description="todo / inbox / done / all",
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
                description="新しいタスクを追加する",
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
        if status and status != "all":
            tasks = [t for t in tasks if t.status == status]
        if category:
            tasks = [t for t in tasks if t.category == category]
        if not tasks:
            return "該当するタスクはありません。", actions
        # IDはcomplete_task呼び出し用。ユーザーへの返答には含めないようsystem_promptで指示済み
        lines = [
            f"- [id:{t.id[:8]}] [{t.category or '未分類'}] {t.text}" for t in tasks[:30]
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
        task = Task(
            text=text,
            status="todo" if category else "inbox",
            category=category,
        )
        data.tasks.append(task)
        storage.save_data(data)
        actions.append({"type": "refresh"})
        return f"「{text}」を追加しました。", actions

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

    return f"未知の関数: {name}", actions


# ── メイン関数 ────────────────────────────────────────────────────────────────


def chat(user_message: str, data: AppData, api_key: str) -> tuple[str, list[dict]]:
    """
    ユーザーメッセージを Gemini Function Calling で処理する。
    Returns: (ai_response_text, ui_actions)
    ui_actions 例: [{"type": "refresh"}, {"type": "switch_tab", "tab": "checklists"}]
    """
    global _history

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return "google-genai が未インストールです: pip install google-genai", []

    client = genai.Client(api_key=api_key)
    system_prompt = _build_system_prompt(data)
    tools = _build_tools()

    # 会話履歴 → types.Content リスト
    contents: list = []
    for msg in _history[-10:]:
        contents.append(
            types.Content(role=msg["role"], parts=[types.Part(text=msg["text"])])
        )
    contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

    ui_actions: list[dict] = []
    final_text = ""

    # Function Calling ループ（最大5ターン）
    for _ in range(5):
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
        contents.append(model_content)

        # Function Call を抽出
        fn_calls = [
            p.function_call
            for p in model_content.parts
            if hasattr(p, "function_call") and p.function_call
        ]

        if not fn_calls:
            final_text = response.text or ""
            break

        # 各関数を実行してレスポンスを追加
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

    # 履歴更新（テキストのみ保存）
    _history.append({"role": "user", "text": user_message})
    _history.append({"role": "model", "text": final_text})
    if len(_history) > 20:
        _history = _history[-20:]

    return final_text or "（応答がありませんでした）", ui_actions
