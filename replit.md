# Workspace

---

## DESIGN CONTRACT — Hard Requirements (apply to every future change)

### Core Principles
1. **External brain, not a list** — capture → structure → schedule. Avoid raw endless lists; always show structure (time, flows, groupings).
2. **Time must be visual** — tasks live in time blocks (Morning / Afternoon / Evening or simple timeline). Use timers to fight time blindness.
3. **Micro-steps over big tasks** — every task must be breakable into 2–5 min subtasks. UI must make adding/checking micro-steps easy.
4. **Now / Next / Later** — primary view shows only: current Now task, one Next, and a capped Today list (3–6 max). Backlogs are collapsed or on separate screens.
5. **Immediate feedback, gentle rewards** — quick visual feedback on every completion (progress bar, color shift, checkmark). Streaks based on show-up, not perfection.
6. **Non-shaming language** — no "failure." Use "Moved to Later", "We'll try again tomorrow", "Touched today", "You showed up."
7. **Low cognitive load** — fewer choices per screen, strong defaults, minimal required fields.
8. **Energy-based structure** — tasks support energy tags: `creative`, `admin`, `social`, `low_energy`. Flexible time blocks, not rigid hour-by-hour.
9. **ADHD-friendly UI** — clear hierarchy, limited palette, obvious affordances, minimal motion. At-a-glance understandability.
10. **Consistency over perfection** — emphasize "you showed up today" and partial progress.

### Required Features (implement in FastAPI/Jinja2 stack, existing routes)

#### 2.1 Daily Flow
- **Morning Check-In**: fast brain-dump field → parse lines into tasks; select up to 3 Must-Do + few Nice-to-Do; place into Morning/Afternoon/Evening slots.
- **Focus Mode** (`/task-manager/focus`): shows ONE active task + visual countdown timer (25/15/45 min choices); Done / Pause / Stop controls; on completion → instant feedback + next suggestion.
- **Evening Reset** (`/task-manager/evening`): Planned vs Touched/Done comparison, non-judgmental; one-tap Roll to Tomorrow or Move to Later; highlight wins including partial progress.

#### 2.2 Tasks & Data Model
- Tasks have **micro-steps** (subtasks, 2–5 min each); easy to add/reorder/complete from task view and Focus Mode.
- **Now / Next / Later Today / Later** state on every task/micro-step.
- Primary Today view shows: Now task + one Next + capped Today list (3–6). Everything else collapsed.
- **Energy tags**: `creative`, `admin`, `social`, `low_energy` — visible near task title.

#### 2.3 Visual Rules
- One primary focus area per screen; secondary info collapsible or on another screen.
- Calm neutral background; at most 2 accent colors (active/focus + success/progress). Never color alone for state — always pair icon or label.
- No looping/flashing animations. Completion feedback: short, one-shot, gentle.
- Non-judgmental copy always.

#### 2.4 Cognitive Load
- Default focus block: 25 min (choices: 15 / 25 / 45 — not free text).
- Routine templates: "Morning Startup", "Weekly Review" — save sets of tasks/steps.
- Brain-dump parser: parse lines into tasks (design to allow AI later).

#### 2.6 ADHD UI/UX Layer (implemented)
- **Dual-theme system**: Light (Stone/Indigo, default) + Dark (ADHD High-Signal: #1A1A1A bg, #FFCC00 accent, #2DD4BF success). Toggle via `🌙 Dark` button in every nav header. Theme persists in `localStorage`. Anti-flicker blocking `<script>` in `<head>` of every template prevents flash.
- **Brown Noise**: `🎧 Noise` button in every nav header. Uses Web Audio API to generate brown noise entirely in-browser (no audio file). Auto-resumes on next page interaction if preference was saved.
- **Lexend font**: Loaded via Google Fonts (`@import`). Applied globally via `font-family` on `body`.
- **Global typography**: `line-height: 1.75`, `letter-spacing: 0.025em`, `text-align: left` (no justify) set on `body`.
- **Progressive disclosure**: Task row meta (energy tag, time block, priority) is hidden with `max-height: 0; opacity: 0` by default and revealed on `:hover` or `.expanded` class.
- **Confetti on task completion**: `canvas-confetti` CDN (`@1.9.2`). Every "Done" / "✓" form fires confetti burst before submitting.
- **SVG Countdown Ring**: Focus Mode timer shows a circular shrinking arc (SVG `stroke-dashoffset` animation) alongside the digital countdown. Ring is r=50, circumference ≈ 314.16px.
- **FAB + N key**: Fixed `+` button (bottom-right, all My Day pages). `N` key opens `<dialog>` quick-add modal. Modal posts to `POST /task-manager/tasks/quick-add` (returns JSON). Shows a toast confirmation. Escape closes the modal.
- **Quick-Add route**: `POST /task-manager/tasks/quick-add` — accepts `title` + `priority` form params, returns `{"status":"ok","task_id":N,"title":"..."}`.

#### 2.5 Habit Tracking
- Track show-up per day (opened Focus Mode, completed micro-step, did Morning Check-In).
- Streak = consecutive show-up days, not perfect completion.
- Display kindly, never as punishment.

---

## Overview

pnpm workspace monorepo using TypeScript, plus a Python FastAPI service. Each package manages its own dependencies.

## Stack

- **Monorepo tool**: pnpm workspaces
- **Node.js version**: 24
- **Python version**: 3.11
- **Package manager**: pnpm (JS), uv/pip (Python)
- **TypeScript version**: 5.9
- **API framework**: Express 5 (Kanban) + FastAPI (Task Manager)
- **Database**: PostgreSQL + Drizzle ORM (Kanban); SQLite + SQLAlchemy (Task Manager)
- **Validation**: Zod (`zod/v4`), `drizzle-zod` (JS); Pydantic v2 (Python)
- **API codegen**: Orval (from OpenAPI spec)
- **Build**: esbuild (CJS bundle)

## Services & Routing

| Path prefix      | Service                         | Port  | Language  |
|------------------|---------------------------------|-------|-----------|
| `/`              | MyDay Kanban (React + Vite)    | 23345 | TypeScript|
| `/api`           | Kanban API (Express)            | 8080  | TypeScript|
| `/task-manager`  | Task Manager (FastAPI)          | 8000  | Python    |

### URLs
- Kanban board: `/`
- Task Manager HTML UI: `/task-manager/tasks-page`
- Task Manager home: `/task-manager/`
- Task Manager REST API: `/task-manager/tasks`, `/task-manager/projects`
- FastAPI auto-docs: `/task-manager/docs`

## Structure

```text
artifacts-monorepo/
├── artifacts/
│   ├── api-server/          # Express API server (Kanban backend)
│   ├── myday-kanban/        # React + Vite frontend (Kanban board)
│   └── myday-python-api/    # FastAPI Task Manager (Python)
│       ├── main.py          # FastAPI app, all routes prefixed /task-manager
│       ├── database.py      # SQLAlchemy engine + session + Base
│       ├── models.py        # SQLAlchemy models (Task, Project, Subtask, Tag, etc.)
│       ├── schemas.py       # Pydantic schemas (TaskCreate, TaskRead, etc.)
│       ├── app.db           # SQLite database file (auto-created)
│       └── templates/       # Jinja2 HTML templates
│           ├── index.html   # Home page
│           └── tasks.html   # Task list + create form
├── lib/
│   ├── api-spec/            # OpenAPI spec + Orval codegen config
│   ├── api-client-react/    # Generated React Query hooks
│   ├── api-zod/             # Generated Zod schemas from OpenAPI
│   └── db/                  # Drizzle ORM schema + DB connection
│       └── src/schema/
│           ├── columns.ts   # Kanban columns table
│           └── cards.ts     # Kanban cards table
└── scripts/                 # Utility scripts
```

## Python Task Manager (FastAPI)

### Models (SQLAlchemy)
- **Project** — id, name, description, is_active
- **Task** — id, title, description, project_id, owner, status, priority, due_date, is_today, source_type, source_ref, focus_state, time_block, energy_tag, created_at, updated_at, completed_at
- **Subtask** — id, task_id, title, is_done, created_at, completed_at
- **Tag** — id, name (unique)
- **TaskTag** — id, task_id, tag_id (many-to-many join)
- **RecurringTask** — id, title, description, project_id, priority, recurrence_type, recurrence_rule, active
- **Settings** — id, morning_ritual_time, wip_limit_doing, default_priority
- **DailyLog** — id, date, started, started_at, has_completed_task, has_morning_checkin
- **CoPInitiative** — id, effort, topic, topic_description, subtopic, type_of_effort, focus_market, leader, cop_collaboration, notes, active_jan…active_dec
- **InboxItem** — id, source, source_type, external_id, title, raw_content, summary, suggested_actions_json, status (new|reviewing|promoted|archived), created_at, reviewed_at, linked_task_id, linked_project_id, linked_note_url

### Meeting Inbox (Phase 1)
Pipeline for Whisper-derived meeting notes before they become tasks.

**Ingest endpoint (POST JSON):** `POST /task-manager/inbox/ingest/whisper`
```json
{
  "title": "Meeting title",
  "raw_content": "Full transcript…",
  "summary": "1–2 sentence summary",
  "suggested_actions": ["Action 1", "Action 2"],
  "external_id": "optional-dedup-id",
  "source_created_at": "2026-03-30T10:30:00"
}
```
**UI routes:**
- `GET /task-manager/inbox` — Inbox list (active items)
- `GET /task-manager/inbox/archived` — Archived notes
- `GET /task-manager/inbox/{id}` — Detail: transcript + summary + suggested actions + promote/archive buttons
- `POST /task-manager/inbox/{id}/promote-task` — Creates a Task with focus_state="later"; marks item as "promoted"
- `POST /task-manager/inbox/{id}/archive` — Archives note without creating a task

**Rules:** Visiting detail page auto-transitions status new → reviewing. Promoting always sets task focus_state="later" (never Now). No auto-task creation on ingest. Designed to be extensible for Notion later.

### API Endpoints
- `GET /task-manager/` — Home page (HTML)
- `GET /task-manager/my-day` — My Day view (HTML)
- `GET /task-manager/morning-checkin` — Brain dump check-in step 1 (HTML)
- `GET /task-manager/kanban` — Kanban board (HTML)
- `GET /task-manager/tasks-page` — Tasks list page (HTML)
- `GET /task-manager/focus` — Focus mode timer (HTML)
- `GET /task-manager/inbox` — Meeting inbox list (HTML)
- `POST /task-manager/tasks-page` — Create task from form (HTML redirect)
- `GET /task-manager/projects` — List projects (JSON)
- `POST /task-manager/projects` — Create project (JSON)
- `GET /task-manager/tasks` — List tasks with optional filters (JSON)
- `POST /task-manager/tasks` — Create task (JSON)
- `PUT /task-manager/tasks/{id}` — Update task (JSON)
- `DELETE /task-manager/tasks/{id}` — Delete task (JSON)
- `POST /task-manager/inbox/ingest/whisper` — Ingest Whisper note (JSON → 201)
- `GET /task-manager/docs` — Swagger UI

### Running
The Python service runs via the "MyDay Task Manager (Python)" workflow: `cd artifacts/myday-python-api && PORT=8000 python main.py`

## TypeScript & Composite Projects

Every TS package extends `tsconfig.base.json` which sets `composite: true`. The root `tsconfig.json` lists all packages as project references. This means:

- **Always typecheck from the root** — run `pnpm run typecheck` (which runs `tsc --build --emitDeclarationOnly`).
- **`emitDeclarationOnly`** — we only emit `.d.ts` files during typecheck; actual JS bundling is handled by esbuild/tsx/vite.
- **Project references** — when package A depends on package B, A's `tsconfig.json` must list B in its `references` array.

## Root Scripts

- `pnpm run build` — runs `typecheck` first, then recursively runs `build` in all packages that define it
- `pnpm run typecheck` — runs `tsc --build --emitDeclarationOnly` using project references
