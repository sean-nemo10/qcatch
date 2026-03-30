# ZzzMemo

**AI-powered personal task manager** — chat with your tasks, sync with Google Calendar, and study English from your daily life.

> 🌐 **Live demo**: [zzzmemo.fly.dev](https://zzzmemo.fly.dev)

---

## What is this?

ZzzMemo is a lightweight alternative to Notion — focused on **speed and AI integration** rather than complexity.

- Type a task in natural language → AI sorts and schedules it
- Chat to manage everything: "Add a meeting tomorrow at 3pm" → done
- Write a diary → AI generates English practice questions from your day
- Syncs with Google Calendar and Google Tasks automatically

Built with FastAPI + vanilla JS. Works as a PWA (installable on mobile).

---

## Features

### Task Management
- **Status**: Inbox / Todo / Long-term / Done / Trash
- **Priority**: High / Medium / Low
- **Due dates**: date picker or natural language ("tomorrow", "next week")
- Drag-and-drop ordering, recurring tasks (daily/weekly/monthly)
- Checklists with deadlines

### AI Chat (powered by Gemini)
Talk to your task list in natural language:

| Say | What happens |
|---|---|
| "What should I do today?" | AI analyzes tasks and advises priorities |
| "Add buy milk to my list" | Task added |
| "Mark the report as done" | Task completed |
| "Change the deadline to Friday" | Due date updated |
| "What's on my calendar today?" | Google Calendar events shown |
| "Add a meeting tomorrow at 3pm" | Calendar event created with confirmation |

### Diary & Blog
- Daily diary with autosave and date navigation
- Blog post management with tags
- AI suggestions: generates topics from completed tasks, or expands what you wrote

### English Learning
- AI generates 3 practice questions from your completed tasks and diary
- Write answers → get AI corrections
- Corrections saved as flashcards (SM-2 spaced repetition)
- Multi-turn discussion with AI tutor

### Google Calendar / Tasks Sync
- Push: ZzzMemo tasks with due dates → Google Calendar or Tasks
- Pull: Completed Google Tasks → reflected in ZzzMemo
- Auto-sync every 30 minutes in the background

---

## Quick Start (self-hosted)

### Requirements
- Python 3.10+
- Gemini API key (free tier: 1500 requests/day) → [Get one here](https://aistudio.google.com/app/apikey)

### Install

```bash
git clone https://github.com/sean-from-japan/ZzzMemo.git
cd ZzzMemo
pip install -r requirements.txt
```

### Set API key

**Windows (PowerShell):**
```powershell
[Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "YOUR_KEY_HERE", "User")
# Restart PowerShell to apply
```

**Mac/Linux:**
```bash
export GEMINI_API_KEY="YOUR_KEY_HERE"
```

### Run

```bash
python qcatch.py
```

Browser opens at `http://localhost:5000` automatically.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python / FastAPI / uvicorn |
| Frontend | Vanilla JS (ES modules, no framework) |
| Database | SQLite |
| AI | Gemini 2.5 Flash (Function Calling + streaming) |
| Hosting | Fly.io |
| Auth | Session cookies + Google OAuth2 |

---

## AI Backend Options (for task sorting)

| Backend | Cost | Setup |
|---|---|---|
| Gemini 2.5 Flash | Free tier available | Set `GEMINI_API_KEY` env var |
| Ollama (local) | Free, offline | Install [Ollama](https://ollama.com), auto-detected |
| Claude Haiku | Paid | Set `ANTHROPIC_API_KEY` env var |

---

## Project Structure

```
ZzzMemo/
├── qcatch.py              # Entry point
├── core/
│   ├── models.py          # Data models
│   ├── storage.py         # Read/write, migrations, SM-2
│   ├── ai.py              # AI sort, tag suggestions
│   ├── chat.py            # Chat + briefing (Function Calling)
│   ├── writing.py         # Diary/blog AI suggestions
│   ├── lang.py            # English practice & corrections
│   └── google_sync.py     # Google Calendar/Tasks sync
├── web/
│   ├── server.py          # FastAPI app
│   ├── deps.py            # Shared state
│   └── routers/           # API routers
└── web/static/
    ├── index.html          # SPA
    └── js/                 # ES modules (17 files)
```

---

## Troubleshooting

**Port 5000 already in use:**
```bash
python qcatch.py --port 5001
```

**Google auth error:**
Download `client_secret.json` from GCP Console → APIs & Services → Credentials → OAuth 2.0 Client IDs, and place it in the project root.

**Gemini API 429 error:**
Rate limit (15 req/min on free tier). No charges — just wait a moment and retry.

---

## License

MIT
