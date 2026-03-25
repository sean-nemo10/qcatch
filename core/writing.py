"""core/writing.py — 文章提案・日記下書き生成ストリーム"""

from __future__ import annotations


def writing_suggest_stream(content: str, mode: str, extra: dict, api_key: str):
    """
    ユーザーが書いた文章に対してAIが提案を返す（テキストを書き換えない）。
    mode: "diary" | "blog"
    extra: diary → {"date": "YYYY-MM-DD"} / blog → {"title": "...", "tags": "..."}
    """
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        yield {"type": "text", "chunk": "google-genai が未インストールです"}
        yield {"type": "done", "actions": []}
        return

    if mode == "diary" and not content.strip():
        # 本文なし → その日の完了タスクから書くべき話題を提案
        tasks = extra.get("tasks", [])
        date_str = extra.get("date", "")
        if not tasks:
            yield {
                "type": "text",
                "chunk": f"{date_str} の完了タスクがまだありません。タスクを完了させるか、直接文章を書き始めてください。",
            }
            yield {"type": "done", "actions": []}
            return
        task_lines = "\n".join(
            f"- [{t.get('category') or '未分類'}] {t['text']}"
            + (" ★重要" if t.get("importance") == "high" else "")
            for t in tasks
        )
        context = f"【{date_str}に完了したタスク一覧】\n{task_lines}"
        system_prompt = (
            "あなたはユーザーの日記執筆を助けるアシスタントです。日本語で返答してください。\n"
            "以下の完了タスクを見て、日記に書く価値のある出来事・体験・気づきをまとめてください。\n\n"
            "【提案の形式】\n"
            "1. 今日のハイライト — 特に書く価値のある出来事（★重要タスクがあれば優先）\n"
            "2. 深掘りできるポイント — 感情や学び、苦労した点など書けそうな切り口\n"
            "3. 書き出しの一文例 — ユーザーがすぐ書き始められる導入文の例\n\n"
            "提案は具体的かつ簡潔に。ユーザーが実際に書く文章はユーザー自身が決める。"
        )
        try:
            client = genai.Client(api_key=api_key)
            stream = client.models.generate_content_stream(
                model="gemini-2.5-flash",
                contents=[types.Content(role="user", parts=[types.Part(text=context)])],
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt, temperature=0.5
                ),
            )
            for chunk in stream:
                if chunk.text:
                    yield {"type": "text", "chunk": chunk.text}
        except Exception as e:
            yield {"type": "text", "chunk": f"エラー: {e}"}
        yield {"type": "done", "actions": []}
        return

    if not content.strip():
        yield {"type": "text", "chunk": "文章を書いてから提案を求めてください。"}
        yield {"type": "done", "actions": []}
        return

    if mode == "diary":
        date_str = extra.get("date", "")
        context = f"以下はユーザーが書いた{date_str}の日記です：\n\n{content}"
        system_prompt = (
            "あなたはユーザーの日記執筆を助けるアシスタントです。日本語で返答してください。\n"
            "ユーザーが自分で書いた文章をそのまま尊重し、書き換えは絶対にしないこと。\n\n"
            "以下の3点を提案してください：\n"
            "1. 内容の充実案 — まだ書いていないかもしれない視点・出来事・感情\n"
            "2. 表現の改善案 — 具体的な箇所を引用した上で、より豊かな表現を提案\n"
            "3. 深める問いかけ — この日記をさらに掘り下げるための自分への問い\n\n"
            "アドバイスは簡潔に。ユーザーの文体を変えるような提案はしないこと。"
        )
    else:  # blog
        title = extra.get("title", "（タイトルなし）")
        tags = extra.get("tags", "")
        context = f"タイトル: {title}\nタグ: {tags}\n\n本文:\n{content}"
        system_prompt = (
            "あなたはユーザーのブログ執筆を助けるエディターです。日本語で返答してください。\n"
            "ユーザーが自分で書いた文章をそのまま尊重し、書き換えは絶対にしないこと。\n\n"
            "以下の3点を提案してください：\n"
            "1. 構成・流れの改善案 — 読者が理解しやすくなる構成のアドバイス\n"
            "2. 追加できる観点 — 記事をより説得力・深みのあるものにする事例・視点\n"
            "3. 表現の改善案 — 具体的な箇所を引用した上で、より伝わりやすい表現を提案\n\n"
            "アドバイスは具体的に。ユーザーの文体を変えるような提案はしないこと。"
        )

    try:
        client = genai.Client(api_key=api_key)
        stream = client.models.generate_content_stream(
            model="gemini-2.5-flash",
            contents=[types.Content(role="user", parts=[types.Part(text=context)])],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.5,
            ),
        )
        for chunk in stream:
            if chunk.text:
                yield {"type": "text", "chunk": chunk.text}
    except Exception as e:
        yield {"type": "text", "chunk": f"エラー: {e}"}

    yield {"type": "done", "actions": []}


def diary_draft_stream(tasks: list, date_str: str, api_key: str):
    """
    完了タスクリストをもとに日記の下書きをストリーミング生成する。
    """
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        yield {"type": "text", "chunk": "google-genai が未インストールです"}
        yield {"type": "done", "actions": []}
        return

    if not tasks:
        yield {
            "type": "text",
            "chunk": "この日の完了タスクが見つかりませんでした。手動で日記を記入してください。",
        }
        yield {"type": "done", "actions": []}
        return

    task_lines = "\n".join(
        f"- [{t.get('category') or '未分類'}] {t['text']}"
        + (" [重要度:高]" if t.get("importance") == "high" else "")
        for t in tasks
    )

    system_prompt = (
        "あなたはユーザーの思考を整理する、優秀なジャーナリングアシスタントです。\n"
        "以下の「今日完了したタスクリスト」をもとに、自然な一人称（私）の日本語で日記の下書きを作成してください。\n\n"
        "【生成のルール】\n"
        "1. タスクをただ箇条書きにするのではなく、一日の流れや頑張りが伝わる自然な文章（物語）にすること。\n"
        "2. 重要度「高」のタスクが含まれている場合は、「特に頑張ったこと」として焦点を当てること。\n"
        "3. 文末に今日の感想を書き込むための一言（例：「今日全体を振り返ると、___だった。」）を空白付きで置くこと。\n"
        "4. 長すぎず、自然に読める長さ（200〜400文字程度）にすること。"
    )
    context = f"【{date_str}に完了したタスク】\n{task_lines}"

    try:
        client = genai.Client(api_key=api_key)
        stream = client.models.generate_content_stream(
            model="gemini-2.5-flash",
            contents=[types.Content(role="user", parts=[types.Part(text=context)])],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.7,
            ),
        )
        for chunk in stream:
            if chunk.text:
                yield {"type": "text", "chunk": chunk.text}
    except Exception as e:
        yield {"type": "text", "chunk": f"エラー: {e}"}

    yield {"type": "done", "actions": []}
