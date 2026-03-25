"""
docs/spec_slides.py — ZzzMemo 仕様まとめ + アーキテクチャ評価 PPTX
Usage:
    python docs/spec_slides.py
Output:
    docs/ZzzMemo_spec.pptx
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path.home() / ".claude" / "slides"))
from pptx_theme import *

OUT = pathlib.Path(__file__).parent / "ZzzMemo_spec.pptx"

prs, BLANK = new_presentation()


def add_slide():
    sl = prs.slides.add_slide(BLANK)
    rect(sl, 0, 0, W_IN, H_IN, D_BG)
    return sl


# ─────────────────────────────────────────────────────────────────────────────
# 1. 表紙
# ─────────────────────────────────────────────────────────────────────────────
sl = add_slide()
rect(sl, 0, 0, W_IN, 2.8, D_BAR)

tf = body_box(sl, 0.5, 0.55, 12.3, 1.8)
para(tf, "ZzzMemo", size=52, bold=True, color=D_TEXT)
para(
    tf,
    "パーソナル生産性ハブ  —  仕様まとめ & アーキテクチャ評価",
    size=20,
    color=D_LABEL,
    space_before=6,
)

tf2 = body_box(sl, 0.5, 3.1, 12.3, 3.8)
dark_label(tf2, "概要", space_before=0)
dark_bullet(tf2, "FastAPI + vanilla JS SPA (PWA)  ／  Python 3.13 対応", size=18)
dark_bullet(
    tf2, "タスク管理・日記・語学学習・AI チャット・Google Calendar/Tasks 連携", size=18
)
dark_bullet(tf2, "Gemini 2.5 Flash（Function Calling）を中核 AI として使用", size=18)
dark_bullet(
    tf2, "Windows 11 ローカル運用  ／  ブラウザ + PWA インストール対応", size=18
)

dark_label(tf2, "対象バージョン", space_before=18)
dark_bullet(tf2, "2026-03-25 時点  (commit a65cc24)", size=16, color=D_GREY)


# ─────────────────────────────────────────────────────────────────────────────
# 2. 全体コンセプト
# ─────────────────────────────────────────────────────────────────────────────
sl = add_slide()
dark_title_bar(sl, "全体コンセプト  —  なぜ作ったか・何を解決するか")
dark_two_col_panels(sl)


def left2(tf):
    dark_label(tf, "解決したい課題", space_before=0)
    dark_bullet(tf, "タスクメモが複数ツールに散らばる", size=17)
    dark_bullet(tf, "「とにかく速く書き留める」と「整理する」が両立しない", size=17)
    dark_bullet(tf, "AI に頼みたいが、毎回コンテキストを説明し直すのが面倒", size=17)
    dark_bullet(tf, "Google Calendar/Tasks との同期が手動で面倒", size=17)

    dark_label(tf, "解決アプローチ", space_before=14)
    dark_bullet(tf, "Inbox キャプチャ → AI 分類 → カテゴリ管理 の 3 段フロー", size=17)
    dark_bullet(tf, "CLI add コマンドで瞬時追記（API 通信ゼロ）", size=17)
    dark_bullet(tf, "チャット AI がデータを把握した状態で常駐", size=17)
    dark_bullet(tf, "Google と自動同期（30 分ごとバックグラウンド）", size=17)


def right2(tf):
    dark_label(tf, "5 つのコア体験", space_before=0)
    dark_bullet(tf, "🏠  ホーム  —  全体俯瞰・クイックアクセス", size=17)
    dark_bullet(tf, "📋  ダッシュボード  —  タスク・チェックリスト・定期", size=17)
    dark_bullet(tf, "📔  日記 / ブログ  —  振り返り・AI 提案・分割表示", size=17)
    dark_bullet(tf, "📚  語学  —  英語練習・SM-2 フラッシュカード", size=17)
    dark_bullet(tf, "💬  AI チャット  —  思考パートナー・カレンダー追加", size=17)

    dark_label(tf, "設計思想", space_before=14)
    dark_bullet(tf, "ローカルファースト  —  データは手元に置く", size=17)
    dark_bullet(tf, "シングルユーザー  —  マルチテナント・認証は不要", size=17)
    dark_bullet(tf, "インクリメンタル拡張  —  CLI → Web UI → AI の段階移行", size=17)


two_col_boxes(sl, left2, right2)


# ─────────────────────────────────────────────────────────────────────────────
# 3. 機能マップ
# ─────────────────────────────────────────────────────────────────────────────
sl = add_slide()
dark_title_bar(sl, "機能マップ  —  5 タブの全機能")
dark_two_col_panels(sl)


def left3(tf):
    dark_label(tf, "🏠 ホーム", space_before=0)
    dark_bullet(
        tf,
        "カードグリッド（Inbox / Todo / 優先 / 長期 / チェックリスト / 定期 / 設定）",
        size=16,
    )
    dark_bullet(tf, "矢印キーで選択 → Enter で遷移", size=16)
    dark_bullet(tf, "朝のブリーフィングボタン（AI 要約）", size=16)

    dark_label(tf, "📋 ダッシュボード", space_before=10)
    dark_bullet(tf, "Inbox（未分類）→ カテゴリ振り分けインライン", size=16)
    dark_bullet(tf, "Todo タブ（カテゴリ別・ドラッグ並び替え）", size=16)
    dark_bullet(tf, "重要度（High/Med/Low）・期日（📅）設定", size=16)
    dark_bullet(tf, "一括完了・一括インポート・ゴミ箱", size=16)
    dark_bullet(tf, "チェックリスト（期日+時刻・アイテム CRUD）", size=16)
    dark_bullet(tf, "定期タスク（daily/weekly/monthly 自動生成）", size=16)
    dark_bullet(tf, "長期タスク（カウント対象外・別タブ管理）", size=16)


def right3(tf):
    dark_label(tf, "📔 日記 / ブログ", space_before=0)
    dark_bullet(tf, "日記: 日付ナビ・オートセーブ（1.5 秒デバウンス）", size=16)
    dark_bullet(tf, "ブログ: タイトル・タグ・一覧・削除", size=16)
    dark_bullet(tf, "AI 提案パネル（空→話題提案 / 非空→充実案）", size=16)
    dark_bullet(tf, "分割表示ボタン（⬜ 2 カラム表示）", size=16)

    dark_label(tf, "📚 語学", space_before=10)
    dark_bullet(tf, "英語練習: 完了タスク・日記から 3 問生成（SSE）", size=16)
    dark_bullet(tf, "添削 → 質問・議論（マルチターン）", size=16)
    dark_bullet(tf, "カードに保存（SM-2 フラッシュカード）", size=16)
    dark_bullet(tf, "カード復習: フリップ式・3 評価（忘/難/完）", size=16)

    dark_label(tf, "💬 AI チャット", space_before=10)
    dark_bullet(tf, "Gemini 2.5 Flash Function Calling（SSE ストリーム）", size=16)
    dark_bullet(tf, "タスク取得 / 追加 / 完了 / チェックリスト / 分析", size=16)
    dark_bullet(
        tf, "自然言語でカレンダー予定追加（確認 UI 付き）", size=16, color=D_ACCENT
    )
    dark_bullet(tf, "会話履歴永続化（直近 20 件）", size=16)


two_col_boxes(sl, left3, right3)


# ─────────────────────────────────────────────────────────────────────────────
# 4. タスクのライフサイクル
# ─────────────────────────────────────────────────────────────────────────────
sl = add_slide()
dark_title_bar(sl, "タスクのライフサイクル  —  ステータス遷移と同期")

# ステータスフロー図（テキストベース）
tf_flow = body_box(sl, 0.3, 1.3, 12.7, 1.6)
para(tf_flow, "CLI add  /  チャット add", size=14, color=D_GREY, bold=False)
para(tf_flow, "  ↓", size=14, color=D_GREY)
statuses = [
    ("inbox", D_YELLOW, "Inbox（未分類）"),
    ("→", D_GREY, "  AI sort / 手動分類  →  "),
    ("todo", D_GREEN, "Todo（カテゴリ済み）"),
    ("→", D_GREY, "  完了  →  "),
    ("done", D_TEAL, "Done"),
    ("→", D_GREY, "  30 日後  →  "),
    ("archive", D_GREY, "Archive"),
]
flow_line = body_box(sl, 0.3, 2.5, 12.7, 0.6)
p = flow_line.add_paragraph()
for key, color, label in statuses:
    if key in ("→",):
        run = p.add_run()
        run.text = label
        run.font.color.rgb = D_GREY
        run.font.size = Pt(17)
    else:
        run = p.add_run()
        run.text = f"[ {label} ]"
        run.font.color.rgb = color
        run.font.size = Pt(17)
        run.font.bold = True

# 詳細説明 2カラム
dark_two_col_panels(sl, top=3.2, height=3.9)

tf_l = body_box(sl, 0.35, 3.3, 6.2, 3.7)
dark_label(tf_l, "ステータス詳細", space_before=0)
dark_bullet(tf_l, "inbox    — CLI / チャットで即追記。未分類のバッファ", size=16)
dark_bullet(tf_l, "todo      — カテゴリ割り当て済み。メイン作業キュー", size=16)
dark_bullet(tf_l, "longterm — カウント除外。いつかやる / 参照用", size=16)
dark_bullet(tf_l, "done     — 完了。30 日後に archive_{year}.json へ", size=16)
dark_bullet(tf_l, "trashed  — ゴミ箱。Google 側も削除", size=16)
dark_label(tf_l, "重要度スコア", space_before=10)
dark_bullet(tf_l, "high / medium / low  →  ダッシュボード内ソートに反映", size=16)

tf_r = body_box(sl, 6.8, 3.3, 6.2, 3.7)
dark_label(tf_r, "Google 同期ルール", space_before=0)
dark_bullet(
    tf_r, "due_date に時刻あり → Google Calendar イベント", size=16, color=D_ACCENT
)
dark_bullet(tf_r, "due_date が 00:00    → Google Tasks に登録", size=16, color=D_ACCENT)
dark_bullet(tf_r, "30 分ごとに自動 push + pull（APScheduler）", size=16)
dark_bullet(tf_r, "カテゴリ → Tasks リスト を AI が自動マッチング", size=16)
dark_label(tf_r, "AI チャットからのカレンダー追加（NEW）", space_before=10)
dark_bullet(
    tf_r, "自然言語 → prepare_calendar_event ツール呼び出し", size=16, color=D_GREEN
)
dark_bullet(tf_r, "確認カード表示（タイトル・日時 編集可）", size=16, color=D_GREEN)
dark_bullet(
    tf_r,
    "承認後 → /api/calendar/add_event → 直接 Calendar 挿入",
    size=16,
    color=D_GREEN,
)


# ─────────────────────────────────────────────────────────────────────────────
# 5. AI 機能詳細
# ─────────────────────────────────────────────────────────────────────────────
sl = add_slide()
dark_title_bar(sl, "AI 機能詳細  —  Gemini 2.5 Flash を中核に")
dark_two_col_panels(sl)


def left5(tf):
    dark_label(tf, "チャット（Function Calling）", space_before=0)
    dark_bullet(tf, "モデル: gemini-2.5-flash  /  SSE ストリーミング", size=16)
    dark_bullet(tf, "ツール一覧:", size=16)
    dark_bullet(
        tf,
        "get_tasks（done / trashed は呼び出し禁止）",
        size=15,
        color=D_GREY,
        indent=1,
    )
    dark_bullet(
        tf, "add_task（自然言語期日 → ISO 変換）", size=15, color=D_GREY, indent=1
    )
    dark_bullet(tf, "complete_task / get_checklists", size=15, color=D_GREY, indent=1)
    dark_bullet(
        tf, "get_summary / get_analysis（滞留・傾向）", size=15, color=D_GREY, indent=1
    )
    dark_bullet(
        tf, "get_recent_diaries（振り返り連携）", size=15, color=D_GREY, indent=1
    )
    dark_bullet(tf, "prepare_calendar_event  ← NEW", size=15, color=D_ACCENT, indent=1)
    dark_bullet(tf, "思考パートナー指向プロンプト（箇条書き禁止・洞察優先）", size=16)
    dark_bullet(tf, "Function Calling ループ最大 4 回 → ストリーム最終応答", size=16)

    dark_label(tf, "AI sort（inbox → カテゴリ自動分類）", space_before=10)
    dark_bullet(
        tf, "バックエンド優先順位: --export → --local(Ollama) → config → auto", size=16
    )
    dark_bullet(
        tf, "auto: Ollama 起動中 → Gemini API → Anthropic の順にフォールバック", size=16
    )


def right5(tf):
    dark_label(tf, "朝のブリーフィング", space_before=0)
    dark_bullet(tf, "直近 24h 完了タスク + 現在の todo をコンテキストに", size=16)
    dark_bullet(tf, "今日フォーカスすべき Top 3 と理由を提示", size=16)
    dark_bullet(tf, "会話履歴を使わず毎回独立実行", size=16)

    dark_label(tf, "日記 AI 提案", space_before=10)
    dark_bullet(tf, "空の日記 → その日の完了タスクから話題提案", size=16)
    dark_bullet(tf, "既記入 → 内容充実・深掘りの提案", size=16)
    dark_bullet(tf, "SSE ストリーミングで逐次表示", size=16)

    dark_label(tf, "語学 AI", space_before=10)
    dark_bullet(tf, "英語練習: 完了タスク・日記コンテキストで 3 問生成", size=16)
    dark_bullet(tf, "添削: 文法・表現のフィードバック", size=16)
    dark_bullet(tf, "議論: 添削後のマルチターン深掘り（/api/lang/discuss）", size=16)
    dark_bullet(tf, "「重要」判定 → カード保存ボタンをオレンジ強調", size=16)

    dark_label(tf, "AI タグ提案", space_before=10)
    dark_bullet(tf, "カテゴリ 5 件以上でサブタグ分割を提案", size=16)
    dark_bullet(tf, "→ モーダル確認フロー（ユーザー承認必須）", size=16)


two_col_boxes(sl, left5, right5)


# ─────────────────────────────────────────────────────────────────────────────
# 6. 技術スタック & アーキテクチャ
# ─────────────────────────────────────────────────────────────────────────────
sl = add_slide()
dark_title_bar(sl, "技術スタック & アーキテクチャ")
dark_two_col_panels(sl)


def left6(tf):
    dark_label(tf, "バックエンド", space_before=0)
    dark_bullet(tf, "Python 3.13  /  FastAPI + uvicorn", size=17)
    dark_bullet(tf, "Pydantic v2（モデル定義・バリデーション）", size=17)
    dark_bullet(tf, "APScheduler（30 分ごと自動同期）", size=17)
    dark_bullet(tf, "google-genai v1.x（Gemini API）", size=17)
    dark_bullet(tf, "google-api-python-client（Calendar / Tasks）", size=17)
    dark_bullet(tf, "anthropic SDK（フォールバック AI）", size=17)

    dark_label(tf, "データ層", space_before=10)
    dark_bullet(tf, "SQLite  data/qcatch.db（8 テーブル）", size=17)
    dark_bullet(tf, "inbox.txt — CLI add 専用バッファ（テキスト）", size=17)
    dark_bullet(tf, "chat_history.json — 会話履歴直近 20 件", size=17)
    dark_bullet(tf, "data/token.json — Google OAuth2 トークン", size=17)
    dark_bullet(tf, "30 日アーカイブ → archive_{year}.json", size=17)


def right6(tf):
    dark_label(tf, "フロントエンド", space_before=0)
    dark_bullet(tf, "Vanilla JS  /  ES Modules（16 ファイル）", size=17)
    dark_bullet(tf, "単一 SPA: index.html  /  CSS カスタムプロパティ", size=17)
    dark_bullet(tf, "3 テーマ: Black / Navy / White（localStorage 保存）", size=17)
    dark_bullet(tf, "PWA: manifest.json + Service Worker (qcatch-v13)", size=17)
    dark_bullet(tf, "SSE（Server-Sent Events）でストリーミング受信", size=17)

    dark_label(tf, "CLI（qcatch.py）", space_before=10)
    dark_bullet(tf, "add / prompt / toast / dashboard サブコマンド", size=17)
    dark_bullet(tf, "add は API 通信ゼロ（inbox.txt に即追記）", size=17)
    dark_bullet(tf, "PyInstaller → qcatch.exe（39 MB）/ Windows Search 登録", size=17)

    dark_label(tf, "認証", space_before=10)
    dark_bullet(tf, "Google OAuth2 Web Server Flow（localhost:5000）", size=17)
    dark_bullet(tf, "PKCE 対応 / OAUTHLIB_INSECURE_TRANSPORT=1（localhost）", size=17)


two_col_boxes(sl, left6, right6)


# ─────────────────────────────────────────────────────────────────────────────
# 7. コードベース構成・規模
# ─────────────────────────────────────────────────────────────────────────────
sl = add_slide()
dark_title_bar(sl, "コードベース構成 & 規模（2026-03-25 時点）")
dark_two_col_panels(sl)


def left7(tf):
    dark_label(tf, "ファイル構成", space_before=0)
    files = [
        ("qcatch.py", "CLI エントリポイント（薄いラッパー）", "150"),
        ("web/server.py", "FastAPI ルート全定義", "1,400+"),
        ("web/static/index.html", "SPA 本体（HTML + CSS）", "3,815"),
        ("web/static/js/", "16 ES モジュール", "―"),
        ("core/chat.py", "AI チャット / briefing / lang", "990+"),
        ("core/storage.py", "load / save / migrate / sm2", "441"),
        ("core/google_sync.py", "Google 同期ロジック", "380+"),
        ("core/ai.py", "sort / tag 提案 / split 提案", "―"),
        ("core/models.py", "Pydantic モデル定義", "―"),
    ]
    for fname, desc, lines in files:
        dark_bullet(tf, f"{fname}", size=15, bold=True, color=D_ACCENT, space_before=5)
        dark_bullet(
            tf,
            f"{desc}  （{lines} 行）",
            size=14,
            color=D_GREY,
            indent=1,
            space_before=1,
        )


def right7(tf):
    dark_label(tf, "主要 API エンドポイント（抜粋）", space_before=0)
    endpoints = [
        ("Tasks", "GET/POST /api/tasks, PATCH /{id}, /bulk-complete"),
        ("Diary", "GET/POST /api/diary, GET /{date}"),
        ("Blog", "GET/POST /api/blog, GET/PATCH/DELETE /{id}"),
        ("Flashcards", "GET/POST /api/flashcards, PATCH /{id}/review"),
        ("Lang", "POST /api/lang/practice, /correct, /discuss"),
        ("Writing", "POST /api/writing/suggest"),
        ("Chat", "POST /api/chat/stream, /briefing, /clear"),
        ("Config", "GET/POST /api/config"),
        ("Auth", "GET /api/auth/login, /callback, /status"),
        ("Sync", "POST /api/sync, /sync/push, /sync/pull"),
        ("Calendar", "POST /api/calendar/add_event  ← NEW"),
    ]
    for name, path in endpoints:
        dark_bullet(tf, name, size=15, bold=True, color=D_LABEL, space_before=6)
        dark_bullet(tf, path, size=13, color=D_GREY, indent=1, space_before=1)


two_col_boxes(sl, left7, right7)


# ─────────────────────────────────────────────────────────────────────────────
# 8. アーキテクチャ評価: 強み
# ─────────────────────────────────────────────────────────────────────────────
sl = add_slide()
dark_title_bar(sl, "アーキテクチャ評価  ①  現状の強み")
dark_two_col_panels(sl)


def left8(tf):
    dark_label(tf, "シンプルさが生む速度", space_before=0)
    dark_bullet(tf, "依存関係が少ない: FastAPI + vanilla JS のみ", size=17)
    dark_bullet(tf, "フレームワーク固有の学習コストがほぼゼロ", size=17)
    dark_bullet(tf, "CLI add は重い import なしで瞬時実行", size=17)
    dark_bullet(tf, "SQLite + ファイル保存でデータ管理が透明", size=17)

    dark_label(tf, "AI 統合の柔軟性", space_before=12)
    dark_bullet(tf, "Gemini → Ollama → Anthropic のカスケード構造", size=17)
    dark_bullet(tf, "Function Calling で DB 操作を AI に委譲", size=17)
    dark_bullet(tf, "SSE ストリーミングで UX を損なわずリアルタイム表示", size=17)
    dark_bullet(tf, "モデルの差し替えが容易（定数 1 箇所を変えるだけ）", size=17)


def right8(tf):
    dark_label(tf, "ローカルファーストの信頼性", space_before=0)
    dark_bullet(tf, "クラウド障害でもローカルデータは常に手元にある", size=17)
    dark_bullet(tf, "Google 同期は非同期・失敗しても本体に影響なし", size=17)
    dark_bullet(tf, "バックグラウンド保存で UI スレッドをブロックしない", size=17)

    dark_label(tf, "拡張のしやすさ（現状）", space_before=12)
    dark_bullet(tf, "新機能 = server.py にルート追加 + JS モジュール追加", size=17)
    dark_bullet(tf, "AI ツールの追加が簡単: _build_tools() + _execute_fn()", size=17)
    dark_bullet(tf, "テーマ = CSS 変数 1 セットを追加するだけ", size=17)
    dark_bullet(tf, "PWA インストール済みならブラウザ依存なし", size=17)

    dark_label(tf, "コスト効率", space_before=12)
    dark_bullet(tf, "Gemini 2.5 Flash は高精度・低コスト", size=17)
    dark_bullet(tf, "Ollama フォールバックでオフライン完全動作も可能", size=17)


two_col_boxes(sl, left8, right8)


# ─────────────────────────────────────────────────────────────────────────────
# 9. アーキテクチャ評価: 懸念点・技術的負債
# ─────────────────────────────────────────────────────────────────────────────
sl = add_slide()
dark_title_bar(sl, "アーキテクチャ評価  ②  懸念点 & 技術的負債")
dark_two_col_panels(sl)


def left9(tf):
    dark_label(tf, "🔴 巨大ファイル問題", space_before=0)
    dark_bullet(tf, "server.py が 1,400 行超 — 責務が混在", size=17, color=D_RED)
    dark_bullet(
        tf, "index.html が 3,815 行 — CSS / マークアップが巨大", size=17, color=D_RED
    )
    dark_bullet(
        tf, "chat.py が 990 行 — チャット/briefing/語学が同居", size=17, color=D_RED
    )
    dark_bullet(
        tf, "→ ファイル単体テストが困難、バグ特定に時間がかかる", size=16, color=D_GREY
    )

    dark_label(tf, "🟡 グローバル状態", space_before=12)
    dark_bullet(
        tf, "_app_data がプロセス内グローバル変数（server.py）", size=17, color=D_YELLOW
    )
    dark_bullet(
        tf, "_history がモジュールレベルグローバル（chat.py）", size=17, color=D_YELLOW
    )
    dark_bullet(
        tf, "threading.Lock は使っているが、非同期コードと混在", size=17, color=D_YELLOW
    )
    dark_bullet(tf, "→ マルチプロセス化・テスト分離が難しい", size=16, color=D_GREY)

    dark_label(tf, "🟡 テスト皆無", space_before=12)
    dark_bullet(tf, "ユニットテスト・統合テストが存在しない", size=17, color=D_YELLOW)
    dark_bullet(tf, "リグレッションを手動確認に頼っている", size=17, color=D_YELLOW)


def right9(tf):
    dark_label(tf, "🟡 フロントエンドの断片化", space_before=0)
    dark_bullet(tf, "onclick= 属性 + window.X 割り当ての混在", size=17, color=D_YELLOW)
    dark_bullet(tf, "状態管理が state.js + window 変数に分散", size=17, color=D_YELLOW)
    dark_bullet(
        tf,
        "コンポーネント境界が不明確（JS とインライン HTML が混在）",
        size=17,
        color=D_YELLOW,
    )
    dark_bullet(
        tf, "→ 機能追加のたびに影響範囲の把握が難しくなる", size=16, color=D_GREY
    )

    dark_label(tf, "🟡 エラーハンドリングの粗さ", space_before=12)
    dark_bullet(
        tf, "google_sync.py の except Exception: pass が多い", size=17, color=D_YELLOW
    )
    dark_bullet(
        tf, "同期失敗が静かに握り潰される（ログには出る）", size=17, color=D_YELLOW
    )
    dark_bullet(
        tf, "UI 側のエラー表示が「エラー: ...」のみで詳細なし", size=17, color=D_YELLOW
    )

    dark_label(tf, "🟢 許容できる選択", space_before=12)
    dark_bullet(tf, "シングルユーザー前提 → 認証なしは意図的", size=17, color=D_GREEN)
    dark_bullet(
        tf,
        "ファイルベースデータ → 可読性・外部連携のトレードオフ",
        size=17,
        color=D_GREEN,
    )
    dark_bullet(
        tf, "vanilla JS → ビルドツール不要・メンテ負荷最小", size=17, color=D_GREEN
    )


two_col_boxes(sl, left9, right9)


# ─────────────────────────────────────────────────────────────────────────────
# 10. 今後の拡張可能性
# ─────────────────────────────────────────────────────────────────────────────
sl = add_slide()
dark_title_bar(sl, "今後の拡張可能性  —  アーキテクチャ改善 & 新機能")
dark_two_col_panels(sl)


def left10(tf):
    dark_label(tf, "アーキテクチャ改善（優先度高）", space_before=0)
    dark_bullet(tf, "server.py を Router 単位に分割", size=17, color=D_ACCENT)
    dark_bullet(
        tf,
        "→ tasks.py / diary.py / chat.py / sync.py 等に分離",
        size=16,
        color=D_GREY,
        indent=1,
    )
    dark_bullet(
        tf,
        "chat.py を Chat / Briefing / Lang の 3 モジュールに分割",
        size=17,
        color=D_ACCENT,
    )
    dark_bullet(tf, "index.html の CSS を style.css に外出し", size=17, color=D_ACCENT)
    dark_bullet(
        tf,
        "→ キャッシュ効率向上 + ファイルが読みやすくなる",
        size=16,
        color=D_GREY,
        indent=1,
    )
    dark_bullet(
        tf, "_app_data を依存性注入（FastAPI Depends）に移行", size=17, color=D_ACCENT
    )
    dark_bullet(
        tf,
        "主要関数の pytest 追加（storage / google_sync 優先）",
        size=17,
        color=D_ACCENT,
    )

    dark_label(tf, "AI 機能の強化", space_before=12)
    dark_bullet(tf, "カレンダー予定の読み取り（今日の予定をチャットで確認）", size=17)
    dark_bullet(tf, "タスク優先度の AI 提案（due_date + 重要度の複合判断）", size=17)
    dark_bullet(tf, "週次レビュー自動生成（完了タスク + 日記 → まとめ）", size=17)
    dark_bullet(tf, "AI ツールへの write_diary / update_task 追加", size=17)


def right10(tf):
    dark_label(tf, "UX / 機能拡張", space_before=0)
    dark_bullet(tf, "モバイル対応強化（タッチ操作 / スワイプ）", size=17)
    dark_bullet(tf, "通知機能（期日前リマインダー / Web Push）", size=17)
    dark_bullet(tf, "タスク間リンク（依存関係・サブタスク）", size=17)
    dark_bullet(tf, "検索機能（全文検索 / SQLite FTS5）", size=17)
    dark_bullet(tf, "カレンダービュー（月/週表示）", size=17)
    dark_bullet(tf, "ダークモード OLED（#000000 完全黒）", size=17)

    dark_label(tf, "外部連携拡張", space_before=12)
    dark_bullet(tf, "Notion / Obsidian エクスポート（Markdown）", size=17)
    dark_bullet(tf, "GitHub Issues 連携（技術タスクの同期）", size=17)
    dark_bullet(tf, "Slack / Discord 通知（完了報告・リマインダー）", size=17)
    dark_bullet(tf, "複数デバイス同期（現状: シングルマシン）", size=17)

    dark_label(tf, "長期: アーキテクチャ変更の選択肢", space_before=12)
    dark_bullet(
        tf, "フロント: Preact / Lit（バンドル不要・軽量コンポーネント）", size=17
    )
    dark_bullet(tf, "→ 状態管理の整理が前提条件", size=16, color=D_GREY, indent=1)
    dark_bullet(tf, "バックエンド: 非同期化（FastAPI async + aiosqlite）", size=17)
    dark_bullet(
        tf, "→ Google API 呼び出しのブロッキング解消", size=16, color=D_GREY, indent=1
    )


two_col_boxes(sl, left10, right10)


# ─────────────────────────────────────────────────────────────────────────────
# 11. アーキテクチャ判断: 今のままでいいか？
# ─────────────────────────────────────────────────────────────────────────────
sl = add_slide()
dark_title_bar(sl, "アーキテクチャ判断  —  今のままでいいか？")

tf_main = body_box(sl, 0.4, 1.3, 12.5, 5.8)

dark_label(
    tf_main,
    "結論: 現状維持でよい  —  ただし「肥大化の閾値」に近づいている",
    space_before=0,
)
para(tf_main, "", size=6, color=D_BG)  # spacer

dark_bullet(
    tf_main,
    "✅  シングルユーザー・ローカル運用という前提が変わらない限り、今のスタックは正解",
    size=18,
    color=D_GREEN,
    bold=True,
)
dark_bullet(
    tf_main,
    "　　FastAPI + vanilla JS は「いつでも読める・壊せる」という個人ツールの最大の武器",
    size=16,
    color=D_GREY,
    indent=1,
)

dark_bullet(
    tf_main,
    "✅  AI 機能の拡張（ツール追加・モデル変更）は現状アーキテクチャで十分対応可能",
    size=18,
    color=D_GREEN,
    bold=True,
    space_before=8,
)
dark_bullet(
    tf_main,
    "　　Function Calling パターンが整備済みなので、ツール追加は 30〜50 行の作業",
    size=16,
    color=D_GREY,
    indent=1,
)

dark_bullet(
    tf_main,
    "⚠️  server.py / index.html の巨大化は今すぐの問題ではないが、次の大機能追加時に対処を",
    size=18,
    color=D_YELLOW,
    bold=True,
    space_before=8,
)
dark_bullet(
    tf_main,
    "　　目安: server.py が 2,000 行 or index.html が 5,000 行を超えたら分割を検討",
    size=16,
    color=D_GREY,
    indent=1,
)

dark_bullet(
    tf_main,
    "⚠️  グローバル状態・テストなしは「個人ツール」として許容範囲だが、他者が使う場合は要対処",
    size=18,
    color=D_YELLOW,
    bold=True,
    space_before=8,
)

dark_bullet(
    tf_main,
    "🔵  次に手をつけるなら: chat.py の分割 + server.py の Router 化 が費用対効果が高い",
    size=18,
    color=D_ACCENT,
    bold=True,
    space_before=8,
)
dark_bullet(
    tf_main,
    "　　この 2 つだけでコードの見通しが大幅に改善し、AI ツール追加もより整理しやすくなる",
    size=16,
    color=D_GREY,
    indent=1,
)


# ─────────────────────────────────────────────────────────────────────────────
# 12. まとめ
# ─────────────────────────────────────────────────────────────────────────────
sl = add_slide()
rect(sl, 0, 0, W_IN, 2.4, D_BAR)

tf_title = body_box(sl, 0.5, 0.45, 12.3, 1.7)
para(tf_title, "まとめ", size=38, bold=True, color=D_TEXT)
para(tf_title, "ZzzMemo  —  現状と今後", size=18, color=D_LABEL, space_before=4)

tf_sum = body_box(sl, 0.5, 2.6, 5.9, 4.6)
dark_label(tf_sum, "現在の状態", space_before=0)
dark_bullet(tf_sum, "5 タブ × 完全動作の生産性ハブが完成", size=17)
dark_bullet(tf_sum, "AI チャット（Function Calling）+ Google 双方向同期", size=17)
dark_bullet(tf_sum, "PWA インストール済み・Windows Search 登録済み", size=17)
dark_bullet(
    tf_sum, "自然言語 → カレンダー追加（確認 UI）も実装完了", size=17, color=D_ACCENT
)

dark_label(tf_sum, "アーキテクチャ評価", space_before=12)
dark_bullet(tf_sum, "現状スタックは個人ツールとして最適解", size=17, color=D_GREEN)
dark_bullet(tf_sum, "巨大ファイル・グローバル状態が潜在的負債", size=17, color=D_YELLOW)
dark_bullet(
    tf_sum, "次の大機能追加前に chat.py / server.py 分割を推奨", size=17, color=D_ACCENT
)

tf_next = body_box(sl, 6.8, 2.6, 6.1, 4.6)
dark_label(tf_next, "次のアクション候補", space_before=0)
dark_bullet(
    tf_next, "① カレンダー追加機能の動作確認（未テスト）", size=17, color=D_ACCENT
)
dark_bullet(tf_next, "② server.py を FastAPI Router 単位に分割", size=17)
dark_bullet(tf_next, "③ chat.py を Chat / Briefing / Lang に分割", size=17)
dark_bullet(tf_next, "④ カレンダー読み取り（今日の予定をチャット表示）", size=17)
dark_bullet(tf_next, "⑤ 週次レビュー自動生成", size=17)
dark_bullet(tf_next, "⑥ qcatch Quest Phase 2 の開発", size=17)


# ─────────────────────────────────────────────────────────────────────────────
# 保存
# ─────────────────────────────────────────────────────────────────────────────
prs.save(str(OUT))
print("Saved: " + str(OUT))
