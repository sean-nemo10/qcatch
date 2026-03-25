"""core/lang.py — 語学学習ストリーム（練習問題・添削・議論）"""

from __future__ import annotations


def lang_practice_stream(tasks: list, diary_content: str, date_str: str, api_key: str):
    """今日のタスク・日記を素材に英語練習問題をストリーミング生成する。"""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        yield {"type": "text", "chunk": "google-genai が未インストールです"}
        yield {"type": "done", "actions": []}
        return

    task_lines = (
        "\n".join(f"- {t['text']}" for t in tasks[:10])
        if tasks
        else "（今日の完了タスクなし）"
    )
    diary_snippet = diary_content[:300] if diary_content else "（日記なし）"

    context = (
        f"【{date_str}の完了タスク】\n{task_lines}\n\n"
        f"【今日の日記（冒頭）】\n{diary_snippet}"
    )
    system_prompt = (
        "あなたは日本語母語話者向けの英語コーチです。\n"
        "ユーザーの今日の活動（タスク・日記）をもとに、実用的な英語練習問題を3問生成してください。\n\n"
        "【問題の形式】\n"
        "各問題に以下を含めること：\n"
        "- 日本語の文脈（タスクや出来事を元にした状況）\n"
        "- 英語で表現してほしい日本語フレーズ（1〜2文）\n"
        "- ヒント（使うべき動詞や表現のキーワード）\n\n"
        "問題は日常会話・ビジネス英語として自然な表現になるよう設計すること。\n"
        "解答例はまだ出さないこと（ユーザーが書いてから添削する）。"
    )

    try:
        client = genai.Client(api_key=api_key)
        stream = client.models.generate_content_stream(
            model="gemini-2.5-flash",
            contents=[types.Content(role="user", parts=[types.Part(text=context)])],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt, temperature=0.6
            ),
        )
        for chunk in stream:
            if chunk.text:
                yield {"type": "text", "chunk": chunk.text}
    except Exception as e:
        yield {"type": "text", "chunk": f"エラー: {e}"}
    yield {"type": "done", "actions": []}


def lang_correct_stream(user_english: str, context: str, api_key: str):
    """ユーザーが書いた英文を添削・フレーズ提案する。"""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        yield {"type": "text", "chunk": "google-genai が未インストールです"}
        yield {"type": "done", "actions": []}
        return

    prompt = f"【日本語の文脈】\n{context}\n\n【ユーザーが書いた英文】\n{user_english}"
    system_prompt = (
        "あなたは優しく的確な英語コーチです。\n"
        "ユーザーが書いた英文を以下の観点で添削してください：\n\n"
        "1. 文法・語法の修正 — 間違いがあれば具体的に指摘して正しい形を示す\n"
        "2. より自然な表現 — ネイティブが実際に使う自然な言い回しを提案\n"
        "3. 例文 — 修正後の自然な英文を1〜2文提示\n"
        "4. 学習ポイント — この表現で覚えておくべき重要なフレーズや構文を1つ抜き出す\n\n"
        "フィードバックは具体的かつポジティブに。日本語で返答すること。"
    )

    try:
        client = genai.Client(api_key=api_key)
        stream = client.models.generate_content_stream(
            model="gemini-2.5-flash",
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt, temperature=0.4
            ),
        )
        for chunk in stream:
            if chunk.text:
                yield {"type": "text", "chunk": chunk.text}
    except Exception as e:
        yield {"type": "text", "chunk": f"エラー: {e}"}
    yield {"type": "done", "actions": []}


def lang_discuss_stream(
    practice_text: str,
    user_answer: str,
    correction: str,
    follow_up: str,
    history: list,
    api_key: str,
):
    """添削後のフォローアップ議論に答える。history は [{role, content}, ...] のリスト。"""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        yield {"type": "text", "chunk": "google-genai が未インストールです"}
        yield {"type": "done", "actions": []}
        return

    system_prompt = (
        "あなたは優しく的確な英語コーチです。\n"
        "以下のコンテキストを踏まえて、ユーザーのフォローアップ質問や反論に答えてください：\n\n"
        f"【練習問題の文脈】\n{practice_text[:500]}\n\n"
        f"【ユーザーが書いた英文】\n{user_answer}\n\n"
        f"【あなたの添削内容】\n{correction[:500]}\n\n"
        "英語学習の理解が深まるよう、具体的かつポジティブに答えること。日本語で返答すること。"
    )

    contents = []
    for h in history:
        role = h.get("role", "user")
        content_text = h.get("content", "")
        contents.append(types.Content(role=role, parts=[types.Part(text=content_text)]))
    contents.append(types.Content(role="user", parts=[types.Part(text=follow_up)]))

    try:
        client = genai.Client(api_key=api_key)
        stream = client.models.generate_content_stream(
            model="gemini-2.5-flash",
            contents=contents,
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
