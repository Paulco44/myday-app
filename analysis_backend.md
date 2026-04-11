# MyDay App — Backend Analysis

## Overview

MyDay is a personal ADHD-focused task and workflow management system built as a pnpm monorepo with two distinct apps:

1. **Python FastAPI + Jinja2 app** (`myday-python-api`) — The primary task manager, served at `/task-manager` (port 8000). Server-rendered HTML via Jinja2 templates.
2. **React + Vite Kanban app** (`myday-kanban`) — A drag-and-drop Kanban board frontend (port 23345), backed by an Express 5 API (port 8080) at `/api`.

The two apps share the same underlying task/project data concepts but are deployed as separate services. The Python app is the "brain" (full task lifecycle, daily flow, Notion integration), while the React Kanban handles the drag-and-drop board view with optimistic UI updates.

---

## 1. Navigation Structure and Page Flow

### Python FastAPI App (`/task-manager`)

All routes are prefixed with `BASE = "/task-manager"`.

#### Primary Navigation Pages

| Route | Template | Purpose |
|---|---|---|
| `GET /task-manager` | `index.html` | Home/dashboard — project list, total/today/doing task counts |
| `GET /task-manager/morning-checkin` | `morning_checkin.html` | Morning ritual entry point |
| `GET /task-manager/my-day` | `my_day.html` | Central daily execution hub |
| `GET /task-manager/focus` | `focus.html` | Focus Mode — single-task timer view |
| `GET /task-manager/close-day` | `close_day.html` | Evening Reset / Close Day |
| `GET /task-manager/kanban` | `kanban.html` | Kanban board (Python/Jinja version) |
| `GET /task-manager/tasks-page` | `tasks.html` | Full task list with filtering |
| `GET /task-manager/projects-list` | `projects_list.html` | Project management list |
| `GET /task-manager/projects/{id}` | `project_detail.html` | Project detail + Notion export |
| `GET /task-manager/inbox` | `inbox.html` | Meeting Inbox (unarchived items) |
| `GET /task-manager/inbox/archived` | `inbox.html` | Archived inbox items |
| `GET /task-manager/inbox/{id}` | `inbox_detail.html` | Single inbox item triage |
| `GET /task-manager/meetings` | `meetings.html` | Meeting-centric view of inbox items grouped by date |
| `GET /task-manager/notes` | `notes.html` | Notes list + Notion export |
| `GET /task-manager/notes/{id}` | `note_detail.html` | Note detail + Notion export |
| `GET /task-manager/cop-admin` | `cop_initiatives.html` | Community of Practice admin |
| `GET /task-manager/cop-import` | `cop_import.html` | CoP CSV bulk import |
| `GET /task-manager/integrations/notion` | `integrations_notion.html` | Notion integration settings |

**Total: 18 distinct HTML views/pages** in the Python app.

### React Kanban App

Served at `/` (port 23345). Single-page React application — the board is the primary and only view.

---

## 2. The Daily Workflow: Morning → Focus → Evening

### Step 1: Morning Check-In (`/task-manager/morning-checkin`)

**GET** — Loads all `todo`/`backlog` tasks ordered by priority DESC, due_date ASC.

**Template receives:** `tasks` (candidate tasks to flag), `base`

**POST** — Accepts:
- `energy_today` (hidden field from card selection) — stored in `DailyLog.energy_today`
- `brain_dump` (multiline textarea) — each non-empty line → new `InboxItem` with `source="morning_checkin"`, `source_type="brain_dump"`
- `win_ids[]` (checkboxes, max 3) — sets `today_flag=True`, `today_category="win"`
- `nice_ids[]` (checkboxes, max 2) — sets `today_flag=True`, `today_category="nice"`

**On submit:** Marks `DailyLog.has_morning_checkin=True`, clears flags from previously-flagged tasks not selected, redirects to `/task-manager/my-day`.

**Four visible sections (all on one scroll):**
1. Energy Check — 4 card options: ⚡ High energy / 🌊 In the flow / 😴 Low energy / 🌪 A bit scattered
2. Brain Dump — large textarea, each line → Inbox item
3. Pick Your 3 Wins — selectable task cards (max 3), become `today_category="win"`
4. Nice-To-Dos — remaining tasks (max 2), become `today_category="nice"`

---

### Step 2: My Day (`/task-manager/my-day`)

The central daily execution hub. Computes and passes to `my_day.html`:

#### Focus State Buckets
- `now_task` — single task with `is_now=True` OR `focus_state="now"` (not done)
- `next_task` — single task with `focus_state="next"` (not done)
- `later_today_tasks` — tasks with `focus_state="later_today"` or no focus_state, capped at `TODAY_VISIBLE_CAP=4`
- `later_today_overflow` — count of hidden overflow tasks

#### Time Block Buckets (Today's active tasks)
- `morning_tasks` — `time_block="morning"`
- `afternoon_tasks` — `time_block="afternoon"`
- `evening_tasks` — `time_block="evening"`
- `unblocked_today` — no time_block assigned

#### Wins/Nice-Tos Tracking
- `wins_tasks` — flagged tasks with `today_category="win"`, status todo/doing
- `nice_tasks` — flagged tasks with `today_category="nice"`, status todo/doing
- `done_wins` — wins already marked done today

#### Stats
- `streak` — consecutive days with `started=True` or completed task (computed via `compute_streak()`)
- `completed_today` — tasks completed since midnight today
- `overdue_count` — tasks with `due_date < today` and not done
- `today_started` — bool, whether DailyLog.started = True
- `inbox_today` — counts of today's inbox items by status (total/new/reviewing/promoted/archived/unreviewed)

#### Suggestions
- Up to `SUGGESTIONS_CAP=7` tasks: overdue first, then due-today, then high-priority no-date
- Excludes tasks already in today's list

#### CoP Panel
- `cop_initiatives` — CoPInitiatives where `leader` contains "Paul" and current month's `active_<month>` field is True
- `current_month_name` — e.g. "April"

#### Constants passed to template
- `must_do_cap=6`, `today_total`, `focus_states`, `time_blocks`, `energy_tags`

---

### Step 3: Focus Mode (`/task-manager/focus`)

**GET** — Looks up task with `focus_state="now"` and not done.

**Template receives:** `now_task` (or None), `base`

**UI behavior:**
- If `now_task` exists: shows task title prominently, energy tag/time block, timer options (timer is JS-side with SVG countdown ring)
- If no `now_task`: shows friendly message + link back to My Day
- Timer durations: 20/25/30/45 minutes (selectable, default 20)
- Controls: Start Focus, Done, Pause, Stop

**POST `/task-manager/focus/complete`** — Accepts `task_id`, `duration_minutes`. Updates `task.updated_at`, calls `mark_today_started()`. Returns JSON `{status: "ok", task_id, duration}`.

---

### Step 4: Close Day (`/task-manager/close-day`)

**GET** — Loads all `today_flag=True` tasks, splits into:
- `wins_done` / `wins_incomplete`
- `nice_done` / `nice_incomplete`
- Computes `score_pct` (% of wins completed)
- `already_closed` — bool from DailyLog.day_closed

**Template receives:** all the above + `now_hour` (for time-of-day context), `base`

**POST** — For each incomplete task:
- `action="backlog"` → sets `status="todo"`, clears `is_today`, clears flags
- `action="rollover"` (default) → keeps `is_today=True`, clears `today_flag` and category

Sets `DailyLog.day_closed=True`, redirects to My Day.

---

## 3. All Routes — Complete Reference

### HTML UI Routes

| Method | Route | Template | Key Data |
|---|---|---|---|
| GET | `/task-manager` | `index.html` | projects, total_tasks, today_count, doing_count |
| GET/POST | `/task-manager/morning-checkin` | `morning_checkin.html` | tasks (todo/backlog by priority) |
| GET | `/task-manager/my-day` | `my_day.html` | Full daily dashboard (see §2) |
| POST | `/task-manager/my-day/start-today` | — redirect | Marks DailyLog.started |
| GET | `/task-manager/focus` | `focus.html` | now_task |
| POST | `/task-manager/focus/complete` | — JSON | Updates task, marks started |
| GET/POST | `/task-manager/close-day` | `close_day.html` | Wins/nice split, score_pct |
| GET | `/task-manager/kanban` | `kanban.html` | columns (by status), wip_limit, now_task_id |
| GET | `/task-manager/tasks-page` | `tasks.html` | tasks (filterable), projects |
| POST | `/task-manager/tasks-page` | — redirect | Create task from form |
| POST | `/task-manager/tasks-page/{id}/delete` | — redirect | Delete task |
| GET | `/task-manager/tasks/{id}/edit` | `task_edit.html` | task, projects, focus_states, time_blocks, energy_tags |
| POST | `/task-manager/tasks/{id}/edit` | — redirect | Full task update |
| POST | `/task-manager/tasks/{id}/quick-edit` | — JSON | Title/priority/due_date/description only |
| POST | `/task-manager/tasks/{id}/status` | — redirect | Update status (Kanban moves) |
| POST | `/task-manager/tasks/{id}/set-today` | — redirect | Set is_today=True, assign focus_state/time_block |
| POST | `/task-manager/tasks/{id}/unset-today` | — redirect | Remove from today |
| POST | `/task-manager/tasks/{id}/focus-state` | — redirect | Update focus_state (enforces single now/next) |
| POST | `/task-manager/tasks/{id}/time-block` | — redirect | Update time_block |
| POST | `/task-manager/tasks/{id}/set-now` | — JSON | Set is_now=True (clears others) — Kanban feature |
| POST | `/task-manager/tasks/{id}/clear-now` | — JSON | Clear is_now flag |
| POST | `/task-manager/tasks/{id}/start-focus` | — redirect | Set is_now + redirect to /focus |
| POST | `/task-manager/tasks/quick-add` | — JSON | FAB / 'N' key quick task creation |
| GET | `/task-manager/projects-list` | `projects_list.html` | projects (with tasks via joinedload) |
| POST | `/task-manager/projects-list/new` | — redirect | Create project |
| POST | `/task-manager/projects/{id}/archive` | — redirect | Archive project |
| POST | `/task-manager/projects/{id}/activate` | — redirect | Reactivate project |
| GET | `/task-manager/projects/{id}` | `project_detail.html` | project, tasks, export_targets |
| POST | `/task-manager/projects/{id}/export-to-notion` | — redirect | Push project to Notion |
| GET/POST | `/task-manager/cop-admin` | `cop_initiatives.html` | All CoP initiatives + create form |
| POST | `/task-manager/cop-admin/{id}/delete` | — redirect | Delete initiative |
| GET/POST | `/task-manager/cop-import` | `cop_import.html` | Bulk CSV import for CoP data |
| GET | `/task-manager/inbox` | `inbox.html` | Active (non-archived) inbox items |
| GET | `/task-manager/inbox/archived` | `inbox.html` | Archived inbox items |
| GET | `/task-manager/inbox/{id}` | `inbox_detail.html` | Single inbox item detail + promote forms |
| GET | `/task-manager/meetings` | `meetings.html` | Inbox items grouped by date |
| POST | `/task-manager/inbox/{id}/promote-task` | — redirect | Promote inbox → Task |
| POST | `/task-manager/inbox/{id}/promote-project` | — redirect | Promote inbox → Project (+ optional first task) |
| POST | `/task-manager/inbox/{id}/promote-note` | — redirect | Promote inbox → NoteItem |
| POST | `/task-manager/inbox/{id}/archive` | — redirect | Archive inbox item |
| GET | `/task-manager/notes` | `notes.html` | All notes + export targets |
| GET | `/task-manager/notes/{id}` | `note_detail.html` | Note detail + export form |
| POST | `/task-manager/notes/{id}/export-to-notion` | — redirect | Push note to Notion |
| GET | `/task-manager/integrations/notion` | `integrations_notion.html` | Notion import/export configuration |
| POST | `/task-manager/integrations/notion/sources` | — redirect | Add Notion import source |
| POST | `/task-manager/integrations/notion/sources/{id}/delete` | — redirect | Remove Notion source |
| POST | `/task-manager/integrations/notion/import` | — redirect | Run Notion import → InboxItems |
| POST | `/task-manager/integrations/notion/export-targets` | — redirect | Add Notion export target |
| POST | `/task-manager/integrations/notion/export-targets/{id}/delete` | — redirect | Remove export target |
| POST | `/task-manager/integrations/notion/export-targets/{id}/set-default` | — redirect | Set default export target |

### JSON/REST API Routes

| Method | Route | Purpose |
|---|---|---|
| GET | `/task-manager/tasks` | List tasks (filterable by status, project_id, is_today, focus_state) |
| POST | `/task-manager/tasks` | Create task (JSON body) |
| PUT | `/task-manager/tasks/{id}` | Full task update (JSON body) |
| DELETE | `/task-manager/tasks/{id}` | Delete task |
| GET | `/task-manager/projects` | List projects |
| POST | `/task-manager/projects` | Create project (JSON body) |
| GET | `/task-manager/cop-initiatives` | List CoP initiatives |
| POST | `/task-manager/cop-initiatives` | Create initiative |
| PUT | `/task-manager/cop-initiatives/{id}` | Update initiative |
| DELETE | `/task-manager/cop-initiatives/{id}` | Delete initiative |
| POST | `/task-manager/inbox/ingest/whisper` | Ingest Whisper meeting notes → InboxItem |
| GET | `/task-manager/healthz` | Health check |

---

## 4. Data Model (models.py)

### Core Models

#### `Task` (tasks table)
The central model. Fields:
- `id`, `title`, `description`
- `project_id` (FK → projects, nullable)
- `owner` (string, default "me")
- `status` — values: `backlog | todo | doing | waiting | done`
- `priority` — values: `low | medium | high`
- `due_date`, `created_at`, `updated_at`, `completed_at`
- `is_today` (bool) — in today's list
- `is_now` (bool) — the single NOW task (Kanban-driven)
- `focus_state` (string) — `now | next | later_today | later | None`
- `time_block` (string) — `morning | afternoon | evening | None`
- `energy_tag` (string) — `creative | admin | social | low_energy | None`
- `energy_type` (varchar 20) — legacy/alternate energy field
- `time_estimate_minutes` (int, nullable)
- `today_flag` (bool) — flagged in morning check-in
- `today_category` (varchar 10) — `"win" | "nice"` (set during morning check-in)
- `source_type` (string) — `self | meeting | inbox | etc.`
- `source_ref` (string, nullable)
- Relationships: `project`, `subtasks`, `task_tags`

#### `Project` (projects table)
- `id`, `name`, `description`, `is_active`
- `source_ref`, `imported_at` (provenance)
- `notion_page_id`, `notion_url`, `exported_at`, `last_synced_at` (Notion export tracking)
- Relationships: `tasks`, `recurring_tasks`

#### `Subtask` (subtasks table)
- `id`, `task_id` (FK → tasks), `title`, `is_done`, `created_at`, `completed_at`
- Purpose: micro-steps (2–5 min chunks) within a task

#### `Tag` / `TaskTag`
- Many-to-many label system for tasks

#### `RecurringTask`
- Template for recurring tasks: `recurrence_type` (daily/weekly/monthly) + `recurrence_rule` (e.g. "Fri", "1st_mon")

#### `Settings`
- Single-row config: `morning_ritual_time` (default "08:30"), `wip_limit_doing` (default 3), `default_priority`

#### `DailyLog` (daily_logs table)
One row per calendar day. Tracks show-up behavior for streak computation:
- `date` (unique), `started` (bool), `started_at`
- `has_completed_task` (bool)
- `has_morning_checkin` (bool)
- `energy_today` — `high | flow | low | scattered`
- `day_closed` (bool) — Evening Reset completed

#### `NoteItem` (note_items table)
Saved reference notes (promoted from inbox or created directly):
- `title`, `content`, `summary`
- `source` — `whisper | notion | self`
- `external_id`, `external_url`
- `linked_inbox_id` (soft FK to inbox_items)
- `notion_page_id`, `notion_url`, `exported_at`, `last_synced_at`

#### `InboxItem` (inbox_items table)
Meeting notes / captured content awaiting triage:
- `source` (whisper/notion/morning_checkin), `source_type` (meeting/brain_dump)
- `title`, `raw_content`, `summary`, `suggested_actions_json`
- `status` — `new | reviewing | promoted | archived`
- `linked_task_id`, `linked_project_id`, `linked_note_id`, `linked_note_url`

#### `CoPInitiative` (cop_initiatives table)
Community of Practice organizational plan tracking:
- `effort`, `topic`, `topic_description`, `subtopic`, `type_of_effort`
- `focus_market`, `leader`, `cop_collaboration`, `notes`
- `active_jan` through `active_dec` — 12 boolean month flags

#### `NotionSource` (notion_sources table)
Configured Notion import sources:
- `name`, `source_type` (page/database), `notion_id`
- `import_mode` (inbox/linked_note), `is_active`, `last_imported_at`

#### `NotionExportTarget` (notion_export_targets table)
Configured Notion export destinations:
- `name`, `notion_id`, `target_type` (page/database), `is_default`

---

## 5. Schemas (schemas.py)

Pydantic v2 schemas for the JSON API layer:

| Schema | Purpose |
|---|---|
| `ProjectCreate` | Create: name, description, is_active |
| `ProjectRead` | Read: id + all fields |
| `TaskCreate` | Create: title + optional project_id, owner, status, priority, due_date, is_today, source_type, source_ref, focus_state, time_block, energy_tag |
| `TaskUpdate` | Partial update: all TaskCreate fields + completed_at, all optional |
| `TaskRead` | Full read response including timestamps |
| `NoteItemRead` | Read notes with source provenance fields |
| `NotionSourceCreate` | Add import source: name, source_type, notion_id, import_mode, is_active |
| `NotionSourceRead` | Read with id, timestamps |
| `WhisperIngest` | Webhook payload: title, raw_content, summary, suggested_actions[], external_id, source_created_at |
| `InboxItemRead` | Full inbox item read |
| `CoPInitiativeCreate` | All CoP fields + 12 month booleans |
| `CoPInitiativeUpdate` | All fields optional (partial update) |
| `CoPInitiativeRead` | Full read response |

Note: No NoteItemCreate schema exists — notes are created only by promoting InboxItems (via `inbox_promote_note`).

---

## 6. Design Principles and ADHD Requirements

Derived from all attached_assets design prompts (consolidated):

### Foundational Principles
1. **External brain, not a list** — Capture → structure → schedule. No raw endless lists.
2. **Time must be visual** — Tasks live in time blocks (Morning/Afternoon/Evening). Timers combat time blindness. SVG countdown ring in Focus Mode.
3. **Micro-steps over big tasks** — Each task breakable into 2–5 min subtasks. Easy add/check UI.
4. **Now / Next / Later** — Primary view shows: 1 Now, 1 Next, capped Later Today (3–6 max). Backlogs are collapsed or on separate screens.
5. **Immediate feedback, gentle rewards** — Quick visual feedback on completion (progress bar, color shift, confetti via canvas-confetti). Streaks based on show-up, not perfection.
6. **Non-shaming language** — No "failure." Phrases: "Moved to Later", "We'll try again tomorrow", "Touched today", "You showed up."
7. **Low cognitive load** — Fewer choices per screen, strong defaults, minimal required fields. Quick-add FAB + 'N' key shortcut.
8. **Energy-based structure** — Tags: `creative | admin | social | low_energy`. Flexible time blocks, not rigid hourly schedules.
9. **ADHD-friendly UI** — Clear hierarchy, limited palette, obvious affordances, minimal motion. No looping/flashing animations.
10. **Consistency over perfection** — Emphasize "you showed up today" and partial progress.

### Enforced Limits
- `MUST_DO_CAP = 6` — soft cap on today's task list
- `TODAY_VISIBLE_CAP = 4` — max Later Today tasks shown before "+N more"
- `SUGGESTIONS_CAP = 7` — max suggestions shown
- Only 1 NOW task at a time (enforced server-side via `clear_focus_state()`)
- Only 1 NEXT task at a time (same enforcement)

### Visual/CSS Specifications
**Indigo & Stone Palette (Light):**
```css
--bg: #F5F5F4;
--surface: #FFFFFF;
--text: #1C1917;
--muted: #6B7280;
--accent: #4F46E5;        /* indigo — Now card, streak pill, primary buttons */
--accent-soft: #E0E7FF;
--success: #22C55E;
--success-soft: #DCFCE7;
--warning: #F97316;
--warning-soft: #FFEDD5;
--border-subtle: #E5E7EB;
```

**ADHD High-Signal Dark Theme:**
- Background: `#1A1A1A`
- Primary Accent: `#FFCC00` (Yellow)
- Success: `#2DD4BF` (Teal)

**Typography:**
- Font: Lexend (loaded from Google Fonts)
- `line-height: 1.75`, `letter-spacing: 0.025em`
- Strictly left-aligned text

**Interaction:**
- Dual theme system persisted in localStorage
- Brown noise toggle in global header (Web Audio API)
- Progressive disclosure: task metadata hidden until hover/tap
- Confetti animation on task completion (canvas-confetti CDN)

---

## 7. Energy Management Features

Energy is tracked at two levels:

### Task-level energy
- `energy_tag` — `creative | admin | social | low_energy` (the primary ADHD-aware field)
- `energy_type` — legacy string field (free-form)
- `time_estimate_minutes` — helps match task to available focus block

### Day-level energy
- `DailyLog.energy_today` — set during Morning Check-In: `high | flow | low | scattered`
- Visible on the My Day page to guide task selection

### Energy in UI
- Energy tags are shown near task titles (in focus states and task cards)
- The intention is to help the user choose tasks that match their current energy level
- Suggestions are surfaced based on urgency (overdue → due today → high priority), but energy_tag enables self-selection

---

## 8. Streak and Habit Tracking

`compute_streak(db)` counts consecutive days where `DailyLog.started=True` OR `has_completed_task=True`, walking backwards from today (up to 365 days).

A day counts as "shown up" if:
- User clicked "Start Today" (sets `started=True`)
- User completed Morning Check-In (`has_morning_checkin=True`, also sets `started=True`)
- User used Focus Mode (`mark_today_started()` called)
- User set a task as today (`mark_today_started()` called via `set-today` endpoint)

The streak is displayed on My Day with non-judgmental framing ("4-day streak" with fire icon, using `--accent` background pill).

---

## 9. How the Two Apps Relate

### Python FastAPI App (`/task-manager`)
- **Full task lifecycle**: CRUD, focus states, daily flow, Notion integration
- **Server-rendered HTML**: all views are Jinja2 templates
- **The "brain"**: handles Morning Check-In, My Day, Focus Mode, Evening Reset, Inbox triage
- **Database**: SQLite (`app.db`) via SQLAlchemy
- **Kanban view exists here too** (`/task-manager/kanban`) but is HTML-rendered, not reactive

### React Kanban App (`/`)
- **Drag-and-drop board**: React + Vite frontend
- **Express 5 backend** at `/api` with Drizzle ORM + PostgreSQL/SQLite
- **Optimistic updates**: `@dnd-kit/core` handles local state before API mutation
- **API codegen**: Orval generates typed hooks from OpenAPI spec
- **Forms**: react-hook-form + Zod validation

### Key Overlap / Coordination Points
- Both apps track the same conceptual task statuses: `backlog | todo | doing | waiting | done`
- The Python app has an `is_now` flag (set via Kanban → `set-now` endpoint) that feeds the My Day NOW strip
- The React Kanban reads from its own Express API; data is NOT directly shared between the two databases — they are independent services
- Navigation: The monorepo uses path-based routing where `/` → Kanban frontend, `/task-manager` → Python app
- The React Kanban uses project color-coding defined in `app.js` with specific project names (My Day improvements, Cardinal Health, CoP Work, etc.) — these project names must match between apps if cross-referencing

### Deployment Ports
- `/` — Kanban frontend (23345)
- `/api` — Kanban Express API (8080)
- `/task-manager` — FastAPI Task Manager (8000)

---

## 10. Inbox / Meeting Notes Pipeline

The Inbox is the capture layer between external sources and the structured task system:

```
Whisper meeting notes ──→ POST /inbox/ingest/whisper ──→ InboxItem (status=new)
Notion pages/databases ──→ POST /integrations/notion/import ──→ InboxItem (status=new)
Morning brain dump ──→ POST /morning-checkin ──→ InboxItem (source=morning_checkin)
                              ↓
              GET /inbox or /inbox/{id} (status → reviewing)
                              ↓
             ┌────────────────┼────────────────┐
             ↓                ↓                ↓
        promote-task    promote-project   promote-note
        (Task created)  (Project + first  (NoteItem created)
                         task created)
             └────────────────┴────────────────┘
                     status = "promoted"
                              ↓ or
                     status = "archived"
```

---

## 11. Notion Integration Summary

**Import (one-way in):**
- Configure sources: Notion page or database UUIDs
- `POST /integrations/notion/import` fetches content, deduplicates by `external_id`, creates InboxItems
- Import modes: `inbox` (→ InboxItem for triage) or `linked_note` (→ NoteItem directly)

**Export (one-way out):**
- Configure export targets: Notion page or database UUIDs
- Notes: `POST /notes/{id}/export-to-notion`
- Projects: `POST /projects/{id}/export-to-notion`
- Stores back: `notion_page_id`, `notion_url`, `exported_at`, `last_synced_at`

---

## 12. Attached Assets Summary

### Design Prompt Files

| File | Summary |
|---|---|
| `Pasted-I-now-want-to-turn-this-FastAPI-skeleton-into-a-basic-t_1774475873052.txt` | **Phase 1 bootstrap**: Set up SQLite/SQLAlchemy, define core models (Project, Task, Subtask, Tag, RecurringTask, Settings), add CRUD API endpoints, create tasks.html template |
| `Pasted-I-now-want-to-add-two-new-UX-layers-on-top-of-the-exist_1774476417034.txt` | **Phase 2**: Add My Day page (`is_today` tasks + suggestions) and Kanban board (5-column status board with WIP limit) |
| `Pasted-Prompt-Strengthen-Morning-Ritual-Must-Do-Cap-I774486238201.txt` | **Phase 3**: Add "Start Today" flow, soft cap of 5 today tasks, suggestions tuned to overdue/due-today/high-priority order, DailyLog for streak tracking, completed-today count |
| `Pasted-I-want-to-integrate-my-Community-of-Practice-Org-Plan-i_1774530349425.txt` | **Phase 4**: Add CoPInitiative model with 12-month boolean fields, CRUD API + admin UI, inject current-month CoP initiatives into My Day |
| `Pasted-From-now-on-please-treat-the-following-design-principle_1774552196426.txt` | **Master design contract**: Formal declaration of all 10 ADHD design principles + detailed specs for Daily Flow (Morning/Focus/Evening), Now/Next/Later states, energy tags, cognitive load reduction, habit tracking. Establishes these as hard requirements. |
| `Pasted-Here-s-a-prompt-you-can-paste-into-Replit-s-Agent-that-_1774552162732.txt` | Duplicate of master design contract formatted for Replit Agent |
| `Pasted-Morning-Check-In-Redesigned-My-Day-I-want-to-implement-_1774552443019.txt` | **Phase 5**: Add `focus_state`, `time_block`, `energy_tag` fields to Task; Morning Check-In brain-dump flow; redesign My Day around Now/Next/Later + time blocks + energy tags |
| `Pasted-I-want-to-add-a-professional-ADHD-friendly-Focus-Mode-w_1774617860163.txt` | **Phase 6**: CSS variable palette refactor (neutral --bg, --accent, --success, --warning), clarify "Start Today" UX, add Focus Mode with preset timers (20/30/45 min), JS-side countdown + progress bar |
| `Pasted-I-want-you-to-adjust-the-My-Day-UI-and-color-system-bas_1774640099734.txt` | **Phase 7**: Make NOW task visually dominant (full indigo tint), improve stats bar (streak pill in accent color), collapse Suggestions and CoP into accordions, lock in Indigo+Stone CSS variables |
| `Pasted--I-want-to-align-our-current-MVP-with-ADHD-centered-UI-_1774886514816.txt` | **ADHD UI audit request**: Check Lexend font, line-height 1.75, chunked cards (not dense lists), progressive disclosure, color contrast (#1A1A1A / #FFCC00), visual micro-rewards |
| `Pasted-This-is-the-final-updated-Master-Prompt-I-have-moved-th_1774887248887.txt` | **Final ADHD refactor prompt**: Dual-theme system (Light Stone + Dark ADHD High-Signal #1A1A1A/#FFCC00), global Brown Noise toggle, Lexend typography, SVG circular countdown in Focus Mode, FAB + N-key for task add, confetti on completion |
| `Pasted--KANBAN-IMPROVEMENTS-ADHD-ENFP-1775131589942_1775131589943.txt` | **Kanban CSS upgrades**: Priority color left borders on cards, 2-line title truncation, column header tinted backgrounds by status, overdue date red pill, project tag pills, move button opacity, full dark mode adjustments |
| `Pasted-In-style-css-add-at-the-bottom-Move-btn-primary-next-st_1775136464013.txt` | **Kanban JS/CSS v2**: Collapse Kanban move buttons (primary next-state button + "···" dropdown for others), per-project color coding (project names hardcoded), quick-add inline form in each column |
| `Pasted-On-the-Kanban-board-I-need-a-way-to-designate-one-task-_1775144522471.txt` | **is_now feature**: Add `is_now` boolean to Task, add set-now/clear-now API endpoints, show "▶ Set NOW" on Doing column hover, feed NOW task to My Day strip |
| `Pasted-Build-the-Morning-Check-In-page-This-is-a-single-page-g_1775154449807.txt` | **Morning Check-In full redesign**: 4-section scroll page (Energy Check 2x2 grid, Brain Dump textarea, 3 Wins selection, Nice-to-Dos), warm styling with gradient background, "Let's go ✦" submit button |

---

## 13. Key Constants and Configuration

```python
BASE = "/task-manager"            # URL prefix for all routes
MUST_DO_CAP = 6                   # soft cap for today's tasks
TODAY_VISIBLE_CAP = 4             # Later Today tasks visible before "+N more"
SUGGESTIONS_CAP = 7               # max suggestions shown
FOCUS_STATES = ["now", "next", "later_today", "later"]
TIME_BLOCKS = ["morning", "afternoon", "evening"]
ENERGY_TAGS = ["creative", "admin", "social", "low_energy"]
STATUSES = ["backlog", "todo", "doing", "waiting", "done"]
```

Default settings (auto-created on first startup):
- `morning_ritual_time = "08:30"`
- `wip_limit_doing = 3`
- `default_priority = "medium"`
