# ZzzMemo — Project-Specific Instructions for Gemini CLI

# Global settings inherited from ~/.gemini/GEMINI.md

## Project Context

ZzzMemo is a FastAPI + vanilla JS SPA for personal task management.
- Main entry: `python qcatch.py` (starts uvicorn + opens browser)
- Git root: `C:\dev` (sibling app `remember/` also lives here)
- This folder: `C:\dev\ZzzMemo`

## Architecture Summary

| File | Role |
|---|---|
| `qcatch.py` | Entry point |
| `web/server.py` | FastAPI app shell (~190 lines) + lifespan + router registration |
| `web/deps.py` | Shared state (`app_data`, logger, helpers) |
| `web/routers/` | tasks / checklists / chat / diary / blog / flashcards / lang / sync / config |
| `web/static/index.html` | SPA shell |
| `web/static/js/` | 16 ES modules |
| `core/` | models / storage / ai / chat / writing / lang / google_sync |
| `data/qcatch.db` | SQLite database — DO NOT DELETE |
| `data/app.log` | Application log |

## Critical Constraints

- **Never delete or overwrite `data/`** — contains live task data and logs
- **`add` command must stay instant** — no API calls
- **Data stays in text/SQLite files** — no schema changes without explicit approval
- **Do not touch `<home>/.claude/projects/C--dev-ZzzMemo/memory/`** — Claude's persistent memory

## Git Notes

- Git root is `C:\dev`, not `C:\dev\ZzzMemo`
- Run git commands from `C:\dev` (or `C:\dev\ZzzMemo` — both work since same repo)
- Never `git add .` or `git add -A` from `C:\dev` (home-adjacent repo with whitelist .gitignore)
- Stage files individually: `git add ZzzMemo/web/static/index.html`

## Expected Tasks for Gemini Here

- `git add / commit` when Claude is rate-limited
- Web research about FastAPI, Fly.io, Gemini API, UI patterns
- Checking `data/app.log` for errors
- Saving research output to `<personal-notes-repo>/research/projects/zzzmemo/`

## Claude Memory — Hands Off

Claude stores memory for this project in:
`<home>/.claude/projects/C--dev-ZzzMemo/memory/`

Do not touch these files.
Always write what you changed to `<personal-notes-repo>/logs/gemini-handoff.md` so Shion can brief Claude.
