# qcatch — PWA・アーキテクチャ・セキュリティ・UI 改善相談

## 現在の状態（2026-03-22）

FastAPI (Python) + Vanilla JS SPA（単一 index.html、ビルドステップなし）として実装済み。
ローカルサーバー（`http://localhost:5000`）でのみ動作する個人用タスク管理アプリ。

### 実装済みの技術的特徴
- SSE Streaming チャット（Gemini 2.5 Flash Function Calling → 最終テキストのみストリーム）
- BroadcastChannel による複数タブ間同期
- バックグラウンドスレッド保存（threading.Lock + daemon Thread）
- 優先度スコアリング（フロントエンドで計算: カテゴリ重み + 滞留日数×2 + 期日ボーナス100）
- Service Worker（`sw.js`）+ `manifest.json` による PWA 基盤（実装済み・後述の問題あり）
- 朝のブリーフィング専用 SSE エンドポイント（/api/chat/briefing）
- 30日アーカイブ自動化
- Gemini によるカテゴリ提案・サブタグ分割提案

### 技術スタック
- Python 3.10 / FastAPI / uvicorn / Pydantic v2 / google-genai SDK
- データ: `tasks.json`（JSON ファイル、SQLite なし、意図的）
- フロントエンド: 単一 index.html（CSS + HTML + JS インライン、no build）

---

## 質問1: PWA インストールアイコンが Chrome に表示されない

### 実装内容
- `/manifest.json` を FastAPI の `FileResponse` で配信（`application/manifest+json`）
- `/sw.js` を FastAPI の `FileResponse` で配信（`Service-Worker-Allowed: /` ヘッダーあり）
- `icon-192.png` を純 Python（struct + zlib）で生成済み
- `manifest.json` に `icons` フィールドあり（purpose: "any maskable"）
- `index.html` の `<head>` に `<link rel="manifest" href="/manifest.json">` あり
- SW は DevTools > Application > Service Workers で "activated and is running" を確認済み

### 観察されている問題
Chrome のアドレスバー右端に ⊕（インストール）アイコンが出ない。

**質問:**
1. `localhost` での PWA インストール要件として、Chrome が「インストール可能」と判定するために満たすべき条件の完全なリストを教えてください（HTTPS 要件の localhost 例外、manifest の必須フィールドなど）。
2. DevTools > Application > Manifest パネルで確認すべき警告・エラーの典型的な原因は？
3. `purpose: "any maskable"` を1つのアイコンに両方指定するのは正しいですか？`"any"` と `"maskable"` を別エントリに分けるべきですか？
4. Chrome の「インストール基準」チェックリストを自動で確認する方法はありますか？（Lighthouse の PWA スコアなど）

---

## 質問2: アーキテクチャ上の懸念点

### 現状の課題
- `index.html` が1ファイルに CSS・HTML・JS を全部詰め込んでいる（現在 ~1700行）
- `tasks.json` にすべてのデータを格納（タスクが増えると毎回全件書き込み）
- API キーを localStorage に保存（env 変数のフォールバックあり）

**質問:**
1. 単一 index.html を維持しながら保守性を上げる現実的な方法はありますか？（外部 JS/CSS ファイルへの分割、Service Worker でのキャッシュを考慮した場合）
2. `tasks.json` の全件書き込みがボトルネックになり始めるタスク数の目安は？その際の移行先（SQLite など）への移行コストを最小化する方法は？
3. API キーの localStorage 保管についてのリスク評価と、ローカル専用アプリにとって現実的な代替案を教えてください。

---

## 質問3: セキュリティ

### 現状
- `localhost:5000` のみで動作、外部公開なし
- FastAPI に認証なし（localhost なので意図的）
- Gemini API キーを localStorage + env 変数で管理
- XSS 対策として `esc()` 関数（HTML エンティティエスケープ）をフロントエンドに実装

**質問:**
1. ローカル専用 FastAPI アプリにおいて「やっておくべき最低限のセキュリティ対策」は何ですか？（CORS 設定、レートリミット、入力バリデーションなど）
2. `innerHTML` に `esc()` でエスケープした文字列を挿入するパターンは十分安全ですか？見落としがちな XSS の穴はありますか？
3. API キーが localStorage に入っている状態で、同一ブラウザの別タブ（悪意ある外部サイト）から読み取られるリスクはありますか？（localhost のため現実的なリスクは低いと思いますが確認したい）

---

## 質問4: UI/UX 改善

### 現状の UI 課題
- タスクが増えてきたときのスクロール体験が長い（カテゴリ折りたたみがない）
- ダッシュボードとタスクタブで情報が重複している（使い分けが不明確）
- モバイル（スマートフォン）での操作性未確認

**質問:**
1. タスク一覧でカテゴリセクションを折りたたみ可能にする場合、状態（開閉）を localStorage に永続化すべきですか？ページリロードのたびに全展開に戻るほうが良いですか？
2. 「ダッシュボード」と「タスクタブ」の情報が重複している問題に対する UX 的な解決策を教えてください。（例: ダッシュボードを「今日のフォーカス」に特化、タスクタブを全件管理に特化など）
3. PWA としてスマートフォンのホーム画面から起動した場合（standalone モード）、タッチ操作に最適化するために最低限変更すべき CSS/JS は何ですか？

---

## 期待する回答形式

- 各質問に対して「結論を先に」述べてください
- コードが必要な場合は、このスタック（FastAPI + Vanilla JS + 単一 index.html）に合った最小限のコードスニペットで
- 「やらなくてよいこと」も明示してください（過剰実装の防止）
