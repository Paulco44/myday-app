# Workspace

## Overview
This project is a pnpm workspace monorepo designed to act as an external brain for managing tasks, notes, and projects, with a strong focus on ADHD-friendly principles. It aims to provide a structured and visual approach to time and task management, moving away from traditional endless lists. The system emphasizes breaking down tasks into micro-steps, visualizing time, and providing immediate, non-shaming feedback. Key capabilities include daily flow management (Morning Check-In, Focus Mode, Evening Reset), robust task and project tracking with micro-steps and energy tags, and integration with external tools like Whisper for meeting notes and Notion for structured exports. The project combines TypeScript-based Kanban functionality with a Python FastAPI service for task management, built on a PostgreSQL/SQLite and Drizzle/SQLAlchemy backend.

## User Preferences
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

## System Architecture
The project is structured as a pnpm workspace monorepo. It comprises a Kanban board frontend (React + Vite) and backend (Express 5), and a Task Manager service (FastAPI) with Jinja2 templating.

**UI/UX Decisions:**
- **Daily Flow:** Morning Check-In for task parsing, Focus Mode with visual countdown timers (25/15/45 min options), and Evening Reset for non-judgmental progress review.
- **Task Visualization:** Tasks have micro-steps, 'Now / Next / Later' states, and energy tags (`creative`, `admin`, `social`, `low_energy`).
- **Visual Rules:** Primary focus area per screen, calm neutral background with at most two accent colors, no looping/flashing animations, short and gentle completion feedback.
- **Cognitive Load:** Default focus block of 25 min (fixed choices), routine templates, and a brain-dump parser.
- **ADHD UI/UX Layer:**
    - Dual-theme system (Light Stone/Indigo, Dark ADHD High-Signal) persisting via `localStorage`.
    - Integrated brown noise generation via Web Audio API.
    - Global Lexend font and specific typography settings (`line-height: 1.75`, `letter-spacing: 0.025em`).
    - Progressive disclosure for task metadata.
    - Confetti animation on task completion.
    - SVG Countdown Ring in Focus Mode.
    - Floating Action Button (FAB) and 'N' key for quick task addition with a modal and toast confirmation.

**Technical Implementations:**
- **Monorepo Tool:** pnpm workspaces.
- **Languages:** TypeScript (Node.js 24) for Kanban, Python 3.11 for Task Manager.
- **Package Managers:** pnpm (JS), uv/pip (Python).
- **API Frameworks:** Express 5 (Kanban), FastAPI (Task Manager).
- **Databases:** PostgreSQL + Drizzle ORM (Kanban), PostgreSQL + SQLAlchemy (Task Manager) — both services now share the same PostgreSQL instance. SQLite (`app.db`) is kept as a migration source backup only.
- **Validation:** Zod (JS), Pydantic v2 (Python).
- **API Codegen:** Orval from OpenAPI spec.
- **Build:** esbuild (CJS bundle).
- **TypeScript Configuration:** All TS packages extend `tsconfig.base.json` with `composite: true`, enabling typechecking from the root with `emitDeclarationOnly`.

**Feature Specifications:**
- **Daily Flow:** Morning Check-In (brain-dump to tasks, 3 Must-Do + Nice-to-Do), Focus Mode (single active task, timer, controls), Evening Reset (Planned vs. Done comparison, roll-over).
- **Tasks & Data Model:** Tasks with micro-steps (2-5 min), Now/Next/Later states, capped Today list (3-6 max), Energy tags.
- **Habit Tracking:** Tracks show-up (opened Focus Mode, completed micro-step, Morning Check-In), streak based on show-up, not perfection.
- **Meeting Inbox:** Ingests Whisper-derived meeting notes via a JSON endpoint (`POST /task-manager/inbox/ingest/whisper`), UI for reviewing, promoting to Tasks/Projects/Notes, or archiving. Promotion of inbox items always sets task `focus_state="later"`.
- **Notion Export:** One-directional export of NoteItems and Projects to Notion pages/databases. Configuration of export targets, `notion_client.py` utility functions for block handling and page creation. Export UI provides "Send to Notion" button with destination selection and "Open in Notion" link.

**System Design Choices:**
- Services are deployed with specific path prefixes and ports: `/` for Kanban frontend (23345), `/api` for Kanban API (8080), `/task-manager` for FastAPI Task Manager (8000).
- PostgreSQL is shared by both the Kanban (Drizzle) and Task Manager (SQLAlchemy) services. Task Manager tables are prefixed separately (`tasks`, `projects`, `inbox_items`, etc.) and do not conflict with Kanban tables (`columns`, `cards`). The `migrate_sqlite_to_postgres.py` script in `artifacts/myday-python-api/` was used for the one-time data migration.
- The Jinja2-templated Kanban view (`/task-manager/kanban`) is deprecated — it now 301-redirects to the React Kanban at `/`. All Python template nav links point directly to `/`.
- **Kanban ↔ Task Manager bridge (3.1 followup):** `tasks.card_id` (INTEGER) and `cards.task_id` (INTEGER) are nullable FK columns linking the two data models. `POST /task-manager/tasks/{id}/push-to-kanban` creates a card in the appropriate Kanban column and links the two records. When a Kanban card is moved to a "Done" column, the Express API's PATCH handler automatically updates the linked task's status to "done". When a card is deleted, its linked task's `card_id` is cleared. The Task Manager task list shows a "📋 Kanban" badge for linked tasks and a "📋 Board" button for unlinked ones. Kanban cards with a linked task show a yellow "Task #N" chip.
- API endpoints are provided for all core functionalities, including task, project, and inbox management, with auto-generated Swagger UI.
- Models (SQLAlchemy) include Project, Task, Subtask, Tag, TaskTag, RecurringTask, Settings, DailyLog, CoPInitiative, NoteItem, and InboxItem.

## External Dependencies
- **Notion API:** For one-directional export of notes and projects.
- **Whisper (implied):** For generating meeting notes ingested into the system's inbox.
- **Google Fonts:** For loading the Lexend font.
- **canvas-confetti CDN (`@1.9.2`):** For confetti animations on task completion.