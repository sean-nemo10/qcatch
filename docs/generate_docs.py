#!/usr/bin/env python3
"""
docs/generate_docs.py — qcatch 使い方ガイド (PPTX) を生成する

使い方: python docs/generate_docs.py
出力:   docs/qcatch_guide.pptx

必要: pip install python-pptx
"""

try:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
except ImportError:
    print("python-pptx が必要です。インストール:  pip install python-pptx")
    raise SystemExit(1)

import io, sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = Path(__file__).parent / "qcatch_guide.pptx"

# ── カラーパレット ────────────────────────────────────────────────────────────
CYN    = RGBColor(0x00, 0xB4, 0xD8)
CYN_DK = RGBColor(0x00, 0x77, 0xB6)
DARK   = RGBColor(0x1E, 0x20, 0x2B)
DIM    = RGBColor(0x6C, 0x75, 0x7D)
WHT    = RGBColor(0xFF, 0xFF, 0xFF)
RED    = RGBColor(0xE5, 0x38, 0x35)
GRN    = RGBColor(0x28, 0xA7, 0x45)
YLW    = RGBColor(0xFD, 0xA8, 0x0B)
BG     = RGBColor(0xF0, 0xFB, 0xFF)
CODE   = RGBColor(0x2B, 0x2D, 0x42)
ORG    = RGBColor(0xFF, 0x7F, 0x00)

W, H = Inches(13.33), Inches(7.5)


# ── ヘルパー ─────────────────────────────────────────────────────────────────
def new_slide(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def rect(slide, x, y, w, h, fill):
    shape = slide.shapes.add_shape(1, x, y, w, h)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = fill
    return shape


def tb(slide, text, x, y, w, h, *,
       sz=18, bold=False, color=DARK, italic=False,
       align=PP_ALIGN.LEFT, font="Segoe UI", wrap=True):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.name = font
    run.font.size = Pt(sz)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    return box


def code_block(slide, text, x, y, w, h, sz=13):
    rect(slide, x, y, w, h, CODE)
    tb(slide, text, x + Inches(0.18), y + Inches(0.12),
       w - Inches(0.36), h - Inches(0.24),
       sz=sz, color=CYN, font="Courier New", wrap=False)


def header_bar(slide, title, emoji=""):
    rect(slide, 0, 0, W, Inches(0.85), CYN_DK)
    label = f"{emoji}  {title}" if emoji else title
    tb(slide, label, Inches(0.4), Inches(0.1), W - Inches(0.8), Inches(0.68),
       sz=26, bold=True, color=WHT)


def bullets(slide, items, x, y, w, h, sz=17, color=DARK):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_before = Pt(7)
        run = p.add_run()
        run.text = f"•   {item}"
        run.font.name = "Segoe UI"
        run.font.size = Pt(sz)
        run.font.color.rgb = color


# ── スライド定義 ─────────────────────────────────────────────────────────────

def slide_title(prs):
    s = new_slide(prs)
    rect(s, 0, 0, W, H, DARK)
    rect(s, 0, H - Inches(0.7), W, Inches(0.7), CYN_DK)
    tb(s, "⚡  qcatch", 0, Inches(1.4), W, Inches(1.5),
       sz=64, bold=True, color=CYN, align=PP_ALIGN.CENTER)
    tb(s, "爆速タスクキャッチ & AI 自動整理", 0, Inches(3.1), W, Inches(0.8),
       sz=28, color=WHT, align=PP_ALIGN.CENTER)
    tb(s, "CLI タスク管理ツール  —  Windows Terminal", 0, Inches(3.95), W, Inches(0.6),
       sz=20, color=DIM, align=PP_ALIGN.CENTER)
    tb(s, "python-pptx で自動生成 — docs/generate_docs.py",
       0, H - Inches(0.58), W, Inches(0.4),
       sz=11, color=RGBColor(0x55, 0x66, 0x77), align=PP_ALIGN.CENTER, italic=True)


def slide_concept(prs):
    s = new_slide(prs)
    header_bar(s, "コンセプト", "💡")

    # 2カラムレイアウト
    tb(s, "課題：タスクが頭に浮かんだとき", Inches(0.6), Inches(1.0), Inches(5.8), Inches(0.5),
       sz=18, bold=True, color=RED)
    bullets(s, [
        "メモアプリを開くのが面倒で忘れる",
        "後で「あれ何だっけ？」となる",
        "TODO リストが散在して整理できない",
    ], Inches(0.6), Inches(1.6), Inches(5.8), Inches(2.2), sz=16, color=DARK)

    tb(s, "解決：qcatch の 2 ステップ", Inches(0.6), Inches(3.9), Inches(5.8), Inches(0.5),
       sz=18, bold=True, color=GRN)
    bullets(s, [
        "思いついた瞬間にコマンド 1 本で記録（待ち時間ゼロ）",
        "時間があるときに AI が自動分類して整理",
    ], Inches(0.6), Inches(4.5), Inches(5.8), Inches(1.6), sz=16, color=DARK)

    # フロー図（右カラム）
    rect(s, Inches(7.2), Inches(1.0), Inches(5.7), Inches(5.8), BG)
    tb(s, "思いついた！", Inches(7.4), Inches(1.2), Inches(5.3), Inches(0.5),
       sz=18, bold=True, color=DARK, align=PP_ALIGN.CENTER)

    rect(s, Inches(8.1), Inches(1.85), Inches(3.8), Inches(0.75), CYN_DK)
    tb(s, "qcatch add \"タスク\"", Inches(8.1), Inches(1.85), Inches(3.8), Inches(0.75),
       sz=16, bold=True, color=WHT, align=PP_ALIGN.CENTER, font="Courier New")

    tb(s, "↓  inbox.txt に即保存", Inches(7.4), Inches(2.72), Inches(5.3), Inches(0.45),
       sz=14, color=DIM, align=PP_ALIGN.CENTER)

    rect(s, Inches(8.1), Inches(3.25), Inches(3.8), Inches(0.65), DIM)
    tb(s, "inbox.txt", Inches(8.1), Inches(3.25), Inches(3.8), Inches(0.65),
       sz=15, bold=True, color=WHT, align=PP_ALIGN.CENTER, font="Courier New")

    tb(s, "↓  時間があるとき", Inches(7.4), Inches(4.02), Inches(5.3), Inches(0.4),
       sz=14, color=DIM, align=PP_ALIGN.CENTER)

    rect(s, Inches(8.1), Inches(4.5), Inches(3.8), Inches(0.75), ORG)
    tb(s, "qcatch sort", Inches(8.1), Inches(4.5), Inches(3.8), Inches(0.75),
       sz=16, bold=True, color=WHT, align=PP_ALIGN.CENTER, font="Courier New")

    tb(s, "↓  AI が自動分類", Inches(7.4), Inches(5.37), Inches(5.3), Inches(0.4),
       sz=14, color=DIM, align=PP_ALIGN.CENTER)

    rect(s, Inches(8.1), Inches(5.85), Inches(3.8), Inches(0.65), GRN)
    tb(s, "sorted_tasks.md", Inches(8.1), Inches(5.85), Inches(3.8), Inches(0.65),
       sz=15, bold=True, color=WHT, align=PP_ALIGN.CENTER, font="Courier New")


def slide_add_mode(prs):
    s = new_slide(prs)
    header_bar(s, "爆速メモモード  —  add コマンド", "⚡")

    tb(s, "コマンド例", Inches(0.6), Inches(1.0), Inches(12.0), Inches(0.45),
       sz=17, bold=True, color=CYN_DK)
    code_block(s,
        "python qcatch.py add \"牛乳を買う\"\n"
        "python qcatch.py add \"企画書を月曜までに仕上げる\"\n"
        "python qcatch.py add \"Pythonの非同期処理を調べる\"",
        Inches(0.6), Inches(1.55), Inches(12.0), Inches(1.35), sz=14)

    tb(s, "出力（data/inbox.txt）", Inches(0.6), Inches(3.05), Inches(12.0), Inches(0.45),
       sz=17, bold=True, color=CYN_DK)
    code_block(s,
        "[2026-03-19 22:45] 牛乳を買う\n"
        "[2026-03-19 22:47] 企画書を月曜までに仕上げる\n"
        "[2026-03-19 23:01] Pythonの非同期処理を調べる",
        Inches(0.6), Inches(3.6), Inches(12.0), Inches(1.25), sz=14)

    tb(s, "設計上のポイント", Inches(0.6), Inches(5.0), Inches(12.0), Inches(0.45),
       sz=17, bold=True, color=CYN_DK)
    bullets(s, [
        "API 通信・ファイル読み込み・重い処理は一切なし  ─  待ち時間ゼロで即終了",
        "タイムスタンプ付きで data/inbox.txt に追記。上書き・削除はしない",
        "inbox.txt が存在しない場合は自動作成（data/ フォルダも同様）",
    ], Inches(0.6), Inches(5.5), Inches(12.0), Inches(1.8), sz=15)


def slide_prompt_mode(prs):
    s = new_slide(prs)
    header_bar(s, "対話入力モード  —  prompt コマンド / Windows Search", "🔍")

    tb(s, "Windows Search から qcatch を起動すると…", Inches(0.6), Inches(1.0), Inches(12.0), Inches(0.5),
       sz=18, bold=True, color=DARK)

    code_block(s,
        "\n"
        "  ────────────────────────────────────────\n"
        "  qcatch  ─  タスクをすばやく記録\n"
        "  ────────────────────────────────────────\n"
        "\n"
        "  タスク> 牛乳を買う\n"
        "\n"
        "  ✓ [2026-03-19 22:45] 牛乳を買う\n"
        "  inbox に 3 件のタスクがあります。\n"
        "\n"
        "  [Enter] で閉じる...",
        Inches(0.6), Inches(1.6), Inches(7.8), Inches(4.8), sz=13)

    tb(s, "起動方法", Inches(9.0), Inches(1.6), Inches(4.0), Inches(0.45),
       sz=16, bold=True, color=CYN_DK)
    bullets(s, [
        "Windows Search: 「qcatch」",
        "ダブルクリック: qcatch_add.bat",
        "PowerShell: qcatch prompt",
        "Win+R: qcatch-add",
    ], Inches(9.0), Inches(2.15), Inches(4.0), Inches(2.2), sz=15)

    tb(s, "注意点", Inches(9.0), Inches(4.5), Inches(4.0), Inches(0.45),
       sz=16, bold=True, color=YLW)
    bullets(s, [
        ".bat ファイルは Windows 11 Search に「アプリ」として表示されない",
        "setup.ps1 が python.exe をターゲットにしたショートカットを作成するため正しく認識される",
    ], Inches(9.0), Inches(5.05), Inches(4.0), Inches(2.0), sz=13, color=DIM)


def slide_sort_mode(prs):
    s = new_slide(prs)
    header_bar(s, "AI 自動整理モード  —  sort コマンド", "🤖")

    # 左カラム: コマンドと出力
    tb(s, "① API あり（ANTHROPIC_API_KEY 設定済み）",
       Inches(0.6), Inches(1.0), Inches(6.0), Inches(0.45),
       sz=15, bold=True, color=GRN)
    code_block(s, "python qcatch.py sort", Inches(0.6), Inches(1.55), Inches(6.0), Inches(0.5), sz=13)

    tb(s, "② API なし（Claude.ai / Gemini に手動で貼り付け）",
       Inches(0.6), Inches(2.3), Inches(6.0), Inches(0.45),
       sz=15, bold=True, color=YLW)
    code_block(s, "python qcatch.py sort --export\n# → data/sort_prompt.txt を生成",
               Inches(0.6), Inches(2.85), Inches(6.0), Inches(0.65), sz=13)

    tb(s, "出力: data/sorted_tasks.md", Inches(0.6), Inches(3.7), Inches(6.0), Inches(0.45),
       sz=15, bold=True, color=CYN_DK)
    code_block(s,
        "# タスク整理 (2026-03-19 23:00)\n\n"
        "## 仕事\n"
        "- [22:47] 企画書を月曜までに仕上げる\n\n"
        "## 買い物\n"
        "- [22:45] 牛乳を買う\n\n"
        "## 学習\n"
        "- [23:01] Pythonの非同期処理を調べる",
        Inches(0.6), Inches(4.25), Inches(6.0), Inches(2.8), sz=12)

    # 右カラム: 処理フロー
    rect(s, Inches(7.2), Inches(1.0), Inches(5.8), Inches(6.0), BG)
    tb(s, "sort の処理フロー", Inches(7.4), Inches(1.15), Inches(5.4), Inches(0.45),
       sz=17, bold=True, color=CYN_DK)

    steps = [
        (GRN,  "① inbox.txt を読み込む"),
        (CYN,  "② Claude API にカテゴリ分類を依頼"),
        (CYN,  "③ sorted_tasks.md に追記保存"),
        (ORG,  "④ inbox.txt を archive.txt に移動"),
        (ORG,  "⑤ inbox.txt をクリア"),
    ]
    for i, (col, step) in enumerate(steps):
        ry = Inches(1.75) + i * Inches(0.92)
        rect(s, Inches(7.5), ry, Inches(0.5), Inches(0.65), col)
        tb(s, step, Inches(8.15), ry + Inches(0.1), Inches(4.6), Inches(0.5),
           sz=15, color=DARK)


def slide_file_structure(prs):
    s = new_slide(prs)
    header_bar(s, "ファイル構成", "📁")

    code_block(s,
        "ZzzMemo/\n"
        "├── qcatch.py           # メインスクリプト\n"
        "├── qcatch_add.bat      # ダブルクリック / Win+R 用ランチャー\n"
        "├── setup.ps1           # Windows ランチャー一括セットアップ\n"
        "├── requirements.txt    # anthropic\n"
        "├── README.md\n"
        "├── CLAUDE.md\n"
        "├── windows_setup.md    # Windows Search 連携の参考資料\n"
        "│\n"
        "├── data/               # 実行時データ（自動生成）\n"
        "│   ├── inbox.txt       # 未整理タスク\n"
        "│   ├── sorted_tasks.md # AI 分類済みタスク\n"
        "│   ├── archive.txt     # sort 済みの inbox バックアップ\n"
        "│   └── sort_prompt.txt # --export で生成されるプロンプト\n"
        "│\n"
        "├── docs/               # ドキュメント\n"
        "│   ├── generate_docs.py\n"
        "│   └── qcatch_guide.pptx\n"
        "│\n"
        "└── prompts/            # AI プロンプトテンプレート\n"
        "    └── gemini_questions.md",
        Inches(0.5), Inches(1.0), Inches(12.3), Inches(6.1), sz=12)


def slide_setup(prs):
    s = new_slide(prs)
    header_bar(s, "セットアップ", "⚙")

    for i, (title, code, note) in enumerate([
        ("① パッケージインストール",
         "pip install -r requirements.txt",
         None),
        ("② Windows ランチャー一括登録（PowerShell で実行）",
         r"Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser" + "\n" +
         r".\setup.ps1",
         "PowerShell コマンド・Windows Search ショートカット・Win+R ランチャーをまとめて設定"),
        ("③ API キー設定（sort コマンドを使う場合のみ）",
         '[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")',
         "API キーがない場合は  python qcatch.py sort --export  でプロンプトファイルを生成できます"),
    ]):
        base_y = Inches(1.05) + i * Inches(1.95)
        tb(s, title, Inches(0.6), base_y, Inches(12.1), Inches(0.45),
           sz=16, bold=True, color=DIM)
        code_block(s, code, Inches(0.6), base_y + Inches(0.52), Inches(12.1),
                   Inches(0.78 if "\n" in code else Inches(0.52)), sz=12)
        if note:
            tb(s, note, Inches(0.6), base_y + Inches(1.45), Inches(12.1), Inches(0.4),
               sz=13, color=DIM, italic=True)


def slide_commands(prs):
    s = new_slide(prs)
    header_bar(s, "コマンドリファレンス", "📋")

    rows = [
        ("add",           '"タスクのテキスト"',         "inbox.txt にタイムスタンプ付きで即追記（API通信なし）"),
        ("list",          "",                          "inbox.txt の内容を一覧表示"),
        ("sort",          "",                          "Claude API で分類 → sorted_tasks.md 保存・inbox クリア"),
        ("sort --export", "",                          "API 不使用。分類プロンプトを data/sort_prompt.txt に書き出し"),
        ("prompt",        "",                          "対話入力モード（Windows Search / バッチ起動用）"),
    ]

    hy = Inches(1.05)
    rect(s, Inches(0.4), hy, Inches(12.5), Inches(0.5), CYN_DK)
    for lbl, cx, cw in [("コマンド",  Inches(0.55), Inches(3.2)),
                         ("引数",     Inches(3.9),  Inches(2.8)),
                         ("説明",     Inches(6.9),  Inches(5.8))]:
        tb(s, lbl, cx, hy + Inches(0.07), cw, Inches(0.38), sz=15, bold=True, color=WHT)

    for i, (cmd, arg, desc) in enumerate(rows):
        ry = hy + Inches(0.5) + i * Inches(0.78)
        rect(s, Inches(0.4), ry, Inches(12.5), Inches(0.75), BG if i % 2 == 0 else WHT)
        tb(s, cmd,  Inches(0.55), ry + Inches(0.15), Inches(3.2), Inches(0.45),
           sz=14, bold=True, color=CYN_DK, font="Courier New")
        tb(s, arg,  Inches(3.9),  ry + Inches(0.15), Inches(2.8), Inches(0.45),
           sz=13, color=DIM,  font="Courier New")
        tb(s, desc, Inches(6.9),  ry + Inches(0.15), Inches(5.8), Inches(0.45),
           sz=14, color=DARK)

    tb(s, "使用例", Inches(0.4), Inches(5.6), Inches(12.5), Inches(0.4),
       sz=15, bold=True, color=CYN_DK)
    code_block(s,
        "python qcatch.py add \"買い物: 牛乳、卵\"        # 即記録\n"
        "python qcatch.py list                           # 確認\n"
        "python qcatch.py sort --export                  # APIなしで分類プロンプト生成",
        Inches(0.4), Inches(6.1), Inches(12.5), Inches(1.1), sz=13)


# ── エントリポイント ─────────────────────────────────────────────────────────
def main():
    prs = Presentation()
    prs.slide_width  = W
    prs.slide_height = H

    slide_title(prs)
    slide_concept(prs)
    slide_add_mode(prs)
    slide_prompt_mode(prs)
    slide_sort_mode(prs)
    slide_file_structure(prs)
    slide_setup(prs)
    slide_commands(prs)

    prs.save(OUT)
    print(f"✅ 生成完了: {OUT}  ({len(prs.slides)} スライド)")


if __name__ == "__main__":
    main()
