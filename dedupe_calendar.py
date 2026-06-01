"""dedupe_calendar.py — qcatch_id が重複している Google Calendar イベントを掃除する。

使い方:
    python dedupe_calendar.py          # ドライラン（削除対象を表示するだけ）
    python dedupe_calendar.py --apply  # 実際に重複を削除する

Fly.io 上（fly ssh console 経由）で引数を渡しにくい場合は環境変数でも切替可:
    DEDUPE_APPLY=1 python dedupe_calendar.py

data/token.json の認証情報を使い、同じ qcatch_id を持つイベントを 1 件だけ残して
残りを削除する。残ったイベントは次回同期時にタスクと再リンクされる。
"""

import os
import sys

from core import google_sync


def diag() -> None:
    """カレンダー全イベントを集計し、重複の実態を表示する（読み取りのみ）。"""
    from collections import Counter

    creds = google_sync.get_credentials()
    if not creds:
        raise RuntimeError("Google 認証が必要です。")
    from googleapiclient.discovery import build

    service = build("calendar", "v3", credentials=creds)
    items = []
    page_token = None
    while True:
        resp = (
            service.events()
            .list(
                calendarId="primary",
                singleEvents=True,
                showDeleted=False,
                maxResults=250,
                pageToken=page_token,
            )
            .execute()
        )
        items.extend(resp.get("items", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    with_qid = sum(1 for e in items if google_sync._event_qcatch_id(e))
    print(f"総イベント数: {len(items)}  / qcatch_id 付き: {with_qid}")

    # 内容（summary + 開始時刻）が同一のイベントを重複候補として集計
    key = Counter(
        (
            e.get("summary", ""),
            e.get("start", {}).get("dateTime") or e.get("start", {}).get("date", ""),
        )
        for e in items
    )
    dups = [(k, n) for k, n in key.items() if n > 1]
    dups.sort(key=lambda x: -x[1])
    print(f"内容が同一の重複グループ: {len(dups)} 件")
    for (summary, start), n in dups[:30]:
        print(f"  x{n}  {start}  {summary[:40]}")


def diag_tasks() -> None:
    """Google Tasks 全件を集計し、qcatch_id の重複を表示する（読み取りのみ）。"""
    from collections import defaultdict

    creds = google_sync.get_credentials()
    if not creds:
        raise RuntimeError("Google 認証が必要です。")
    from googleapiclient.discovery import build

    service = build("tasks", "v1", credentials=creds)
    lists = service.tasklists().list(maxResults=100).execute().get("items", [])
    by_qid = defaultdict(list)
    total = 0
    for tl in lists:
        page_token = None
        cnt = 0
        while True:
            resp = (
                service.tasks()
                .list(
                    tasklist=tl["id"],
                    showCompleted=True,
                    showHidden=True,
                    maxResults=100,
                    pageToken=page_token,
                )
                .execute()
            )
            for t in resp.get("items", []):
                cnt += 1
                total += 1
                notes = t.get("notes", "")
                if notes.startswith("qcatch_id:"):
                    qid = notes.split("\n", 1)[0][len("qcatch_id:") :].strip()
                    by_qid[qid].append((tl["title"], t["id"], t.get("title", "")))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        print(f"  リスト「{tl['title']}」: {cnt} 件")

    dups = {q: v for q, v in by_qid.items() if len(v) > 1}
    print(
        f"総タスク数: {total}  / qcatch_id 付き: {sum(len(v) for v in by_qid.values())}"
    )
    print(f"qcatch_id が重複しているグループ: {len(dups)} 件")
    for qid, v in list(dups.items())[:30]:
        print(f"  x{len(v)}  {v[0][2][:40]}")


def main() -> None:
    if "--diag" in sys.argv:
        diag()
        return
    if "--diag-tasks" in sys.argv:
        diag_tasks()
        return
    apply = "--apply" in sys.argv or os.environ.get("DEDUPE_APPLY") == "1"

    cal = google_sync.dedupe_calendar_events(dry_run=not apply)
    tasks = google_sync.dedupe_google_tasks(dry_run=not apply)

    label = "削除した" if apply else "削除対象"
    n_cal = cal["deleted"] if apply else len(cal["deleted_ids"])
    n_tasks = tasks["deleted"] if apply else len(tasks["deleted_ids"])
    print(f"[Calendar] 重複グループ {cal['groups']} 件 / {label} {n_cal} 件")
    print(f"[Tasks]    重複グループ {tasks['groups']} 件 / {label} {n_tasks} 件")
    if not apply and (n_cal or n_tasks):
        print("実際に削除するには: python dedupe_calendar.py --apply")


if __name__ == "__main__":
    main()
