# Workspace

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
- **Task** — id, title, description, project_id, owner, status, priority, due_date, is_today, source_type, source_ref, created_at, updated_at, completed_at
- **Subtask** — id, task_id, title, is_done, created_at, completed_at
- **Tag** — id, name (unique)
- **TaskTag** — id, task_id, tag_id (many-to-many join)
- **RecurringTask** — id, title, description, project_id, priority, recurrence_type, recurrence_rule, active
- **Settings** — id, morning_ritual_time, wip_limit_doing, default_priority

### API Endpoints
- `GET /task-manager/` — Home page (HTML)
- `GET /task-manager/tasks-page` — Tasks list page (HTML)
- `POST /task-manager/tasks-page` — Create task from form (HTML redirect)
- `GET /task-manager/projects` — List projects (JSON)
- `POST /task-manager/projects` — Create project (JSON)
- `GET /task-manager/tasks` — List tasks with optional filters: `?status=todo&project_id=1&is_today=true` (JSON)
- `POST /task-manager/tasks` — Create task (JSON)
- `PUT /task-manager/tasks/{id}` — Update task (JSON)
- `DELETE /task-manager/tasks/{id}` — Delete task (JSON)
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
