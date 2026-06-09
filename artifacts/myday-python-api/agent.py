"""
agent.py — MyDay assistant (Phase 0: local conversational brain).

A tool-using agent over the existing MyDay data (tasks, projects, inbox, notes)
plus Notion export. No external integrations yet (email/calendar/chat land in
later phases and normalize into InboxItem, which the agent already reads).

Design notes:
- Tools wrap the SAME logic the HTML routes use, operating directly on the
  SQLAlchemy session (no internal HTTP hop).
- Conversation context is rebuilt from persisted user/assistant text turns each
  request; tool round-trips are ephemeral within a single request.
- Responses stream to the client via Server-Sent Events.
- The static system prompt + tool schema are marked for prompt caching to cut cost.
"""
import json
import os
import re
from datetime import date, datetime, timedelta
from typing import Optional

import anthropic

import models
import notion_client as notion
import ms_graph

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")
MAX_TOKENS = 4096

# Single client; reads ANTHROPIC_API_KEY from the environment (loaded from .env).
_client: Optional[anthropic.Anthropic] = None


def is_configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


# ─── Serializers ──────────────────────────────────────────────────────────────

def _d(dt) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, (date, datetime)):
        return dt.isoformat()
    return str(dt)


def task_to_dict(t: "models.Task", db=None) -> dict:
    project_name = None
    if t.project_id and db is not None:
        p = db.query(models.Project).filter(models.Project.id == t.project_id).first()
        project_name = p.name if p else None
    return {
        "id": t.id,
        "title": t.title,
        "status": t.status,
        "priority": t.priority,
        "due_date": _d(t.due_date),
        "project_id": t.project_id,
        "project_name": project_name,
        "focus_state": t.focus_state,
        "is_today": bool(t.is_today),
        "today_category": t.today_category,
        "energy_tag": t.energy_tag,
        "time_block": t.time_block,
        "assignee": t.assignee,
        "description": t.description,
    }


def project_to_dict(p: "models.Project") -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "is_active": bool(p.is_active),
        "notion_url": p.notion_url,
    }


def inbox_to_dict(i: "models.InboxItem") -> dict:
    return {
        "id": i.id,
        "title": i.title,
        "source": i.source,
        "status": i.status,
        "summary": i.summary,
        "created_at": _d(i.created_at),
        "linked_task_id": i.linked_task_id,
        "linked_project_id": i.linked_project_id,
    }


def note_to_dict(n: "models.NoteItem") -> dict:
    return {
        "id": n.id,
        "title": n.title,
        "summary": n.summary,
        "source": n.source,
        "created_at": _d(n.created_at),
        "notion_url": n.notion_url,
        "exported": n.notion_url is not None,
    }


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return date.fromisoformat(s.strip()[:10])
    except Exception:
        return None


# ─── Tool definitions (Anthropic schema) ───────────────────────────────────────

TOOLS = [
    {
        "name": "get_today_overview",
        "description": "Snapshot of today: energy, what's in focus (now/next), today's tasks, "
                       "overdue count, completed-today count, streak, and unreviewed inbox count. "
                       "Call this first when the user asks what to do today or to prioritize.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_tasks",
        "description": "List tasks, optionally filtered. Use to find tasks before acting on them.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["backlog", "todo", "doing", "waiting", "done", "dropped"]},
                "project_id": {"type": "integer"},
                "query": {"type": "string", "description": "case-insensitive substring match on title"},
                "today_only": {"type": "boolean", "description": "only tasks flagged for today"},
                "limit": {"type": "integer", "default": 25},
            },
        },
    },
    {
        "name": "get_task",
        "description": "Get full detail of one task including its subtasks.",
        "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}}, "required": ["task_id"]},
    },
    {
        "name": "create_task",
        "description": "Create a new task.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "project_id": {"type": "integer"},
                "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                "due_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "energy_tag": {"type": "string", "enum": ["creative", "admin", "social", "low_energy"]},
                "description": {"type": "string"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "update_task",
        "description": "Update fields of an existing task (only provided fields change).",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer"},
                "title": {"type": "string"},
                "status": {"type": "string", "enum": ["backlog", "todo", "doing", "waiting", "done", "dropped"]},
                "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                "due_date": {"type": "string", "description": "ISO date YYYY-MM-DD, or empty string to clear"},
                "description": {"type": "string"},
                "assignee": {"type": "string"},
                "project_id": {"type": "integer"},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "set_task_focus",
        "description": "Set a task's focus for today: 'now' (the single active task), 'next', "
                       "'later_today', or 'later' (removes from today). Enforces a single now/next.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer"},
                "focus_state": {"type": "string", "enum": ["now", "next", "later_today", "later"]},
            },
            "required": ["task_id", "focus_state"],
        },
    },
    {
        "name": "complete_task",
        "description": "Mark a task as done.",
        "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}}, "required": ["task_id"]},
    },
    {
        "name": "list_projects",
        "description": "List projects.",
        "input_schema": {
            "type": "object",
            "properties": {"active_only": {"type": "boolean", "default": True}},
        },
    },
    {
        "name": "get_project",
        "description": "Get a project with its open (non-done) tasks.",
        "input_schema": {"type": "object", "properties": {"project_id": {"type": "integer"}}, "required": ["project_id"]},
    },
    {
        "name": "create_project",
        "description": "Create a new project.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}, "description": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "list_inbox",
        "description": "List inbox items awaiting triage (meeting notes, captures, Notion imports).",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["new", "reviewing", "promoted", "archived"]},
                "limit": {"type": "integer", "default": 25},
            },
        },
    },
    {
        "name": "create_inbox_item",
        "description": "Capture a quick note/idea/worry into the inbox for later triage.",
        "input_schema": {
            "type": "object",
            "properties": {"title": {"type": "string"}, "content": {"type": "string"}},
            "required": ["title"],
        },
    },
    {
        "name": "promote_inbox_to_task",
        "description": "Turn an inbox item into a task.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_id": {"type": "integer"},
                "title": {"type": "string", "description": "optional override; defaults to the item title"},
                "project_id": {"type": "integer"},
            },
            "required": ["item_id"],
        },
    },
    {
        "name": "search_notes",
        "description": "Search saved reference notes by title/content substring.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "default": 25}},
        },
    },
    {
        "name": "create_note",
        "description": "Create a saved reference note. Use this to document progress/decisions. "
                       "Pair with export_note_to_notion to push it to Notion.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string", "description": "full text / markdown of the note"},
                "summary": {"type": "string"},
            },
            "required": ["title", "content"],
        },
    },
    {
        "name": "list_notion_targets",
        "description": "List configured Notion export destinations. Check this before exporting.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "export_note_to_notion",
        "description": "Export a saved note to Notion. If target_id is omitted, uses the default target.",
        "input_schema": {
            "type": "object",
            "properties": {"note_id": {"type": "integer"}, "target_id": {"type": "integer"}},
            "required": ["note_id"],
        },
    },
    {
        "name": "get_calendar_events",
        "description": "Microsoft 365 calendar: meetings for today (or next N days). Metadata only "
                       "(subject, time, organizer). Use to plan around meetings.",
        "input_schema": {
            "type": "object",
            "properties": {"days": {"type": "integer", "default": 1, "description": "1 = solo hoy"}},
        },
    },
    {
        "name": "sync_ms_email",
        "description": "Pull recent Outlook emails into the inbox (deduped). Bodies stay local; "
                       "only metadata is shown unless you read a body explicitly.",
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 25}},
        },
    },
    {
        "name": "list_ms_email",
        "description": "List synced Outlook emails in the inbox (metadata only: subject + sender + time). "
                       "Does NOT include the body — use read_email_body for that.",
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 25}},
        },
    },
    {
        "name": "read_email_body",
        "description": "Read the full body of one synced email by its inbox item id. Only call this when "
                       "the user explicitly asks to read/summarize a specific email (confidentiality).",
        "input_schema": {
            "type": "object",
            "properties": {"item_id": {"type": "integer"}},
            "required": ["item_id"],
        },
    },
    {
        "name": "sync_ms_teams",
        "description": "Pull recent Microsoft Teams chats into the inbox (deduped). Message bodies stay local; "
                       "only metadata is shown unless you read a message explicitly.",
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 25}},
        },
    },
    {
        "name": "list_ms_teams",
        "description": "List synced Teams chats in the inbox (metadata only: topic/sender + time). "
                       "Does NOT include the message body — use read_teams_message for that.",
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 25}},
        },
    },
    {
        "name": "read_teams_message",
        "description": "Read the full body of one synced Teams message by its inbox item id. Only call this when "
                       "the user explicitly asks to read/summarize a specific Teams chat (confidentiality).",
        "input_schema": {
            "type": "object",
            "properties": {"item_id": {"type": "integer"}},
            "required": ["item_id"],
        },
    },
    {
        "name": "get_briefing",
        "description": "Today's proactive briefing: the single main objective + stall radar (tasks sitting too "
                       "long with recommended next action). Use when the user asks for their briefing, what to "
                       "focus on, or what's stuck/stalled.",
        "input_schema": {
            "type": "object",
            "properties": {"refresh": {"type": "boolean", "default": False, "description": "regenerar en vez de usar caché"}},
        },
    },
]


# ─── Tool execution ─────────────────────────────────────────────────────────

def _clear_focus(db, state: str, exclude_id: Optional[int] = None):
    q = db.query(models.Task).filter(models.Task.focus_state == state)
    if exclude_id:
        q = q.filter(models.Task.id != exclude_id)
    for t in q.all():
        t.focus_state = "later_today" if t.is_today else None


def _mark_day_started(db):
    today = date.today()
    log = db.query(models.DailyLog).filter(models.DailyLog.date == today).first()
    if not log:
        log = models.DailyLog(date=today)
        db.add(log)
    if not log.started:
        log.started = True
        log.started_at = datetime.utcnow()


def execute_tool(name: str, args: dict, db) -> dict:
    """Run one tool. Returns a JSON-serializable result dict. Never raises."""
    try:
        return _dispatch(name, args or {}, db)
    except Exception as exc:
        db.rollback()
        return {"error": f"{type(exc).__name__}: {exc}"}


def _dispatch(name: str, a: dict, db) -> dict:
    if name == "get_today_overview":
        today = date.today()
        today_start = datetime(today.year, today.month, today.day)
        active_today = (
            db.query(models.Task)
            .filter(models.Task.is_today == True, models.Task.status != "done")
            .order_by(models.Task.priority.desc())
            .all()
        )
        now_task = db.query(models.Task).filter(
            models.Task.is_now == True, models.Task.status != "done"
        ).first() or next((t for t in active_today if t.focus_state == "now"), None)
        next_task = next((t for t in active_today if t.focus_state == "next"), None)
        overdue = db.query(models.Task).filter(
            models.Task.due_date < today, models.Task.status != "done"
        ).count()
        completed_today = db.query(models.Task).filter(
            models.Task.completed_at >= today_start, models.Task.status == "done"
        ).count()
        log = db.query(models.DailyLog).filter(models.DailyLog.date == today).first()
        unreviewed = db.query(models.InboxItem).filter(
            models.InboxItem.status.in_(["new", "reviewing"])
        ).count()
        return {
            "date": today.isoformat(),
            "energy_today": log.energy_today if log else None,
            "day_started": bool(log.started) if log else False,
            "now_task": task_to_dict(now_task, db) if now_task else None,
            "next_task": task_to_dict(next_task, db) if next_task else None,
            "today_tasks": [task_to_dict(t, db) for t in active_today],
            "today_count": len(active_today),
            "overdue_count": overdue,
            "completed_today": completed_today,
            "unreviewed_inbox": unreviewed,
            "calendar_today": safe_calendar(days=1),  # M365 meetings (metadata only; [] if not connected)
        }

    if name == "get_calendar_events":
        if not ms_graph.is_connected():
            return {"connected": False, "events": [],
                    "note": "Microsoft 365 no está conectado. Conéctalo en Integraciones → Microsoft 365."}
        try:
            return {"connected": True, "events": ms_graph.get_calendar_events(days=int(a.get("days", 1)))}
        except Exception as exc:
            return {"error": str(exc)}

    if name == "sync_ms_email":
        return sync_ms_email(db, limit=int(a.get("limit", 25)))

    if name == "list_ms_email":
        items = (
            db.query(models.InboxItem)
            .filter(models.InboxItem.source == "ms_email")
            .order_by(models.InboxItem.created_at.desc())
            .limit(int(a.get("limit", 25)))
            .all()
        )
        # Metadata only — no body.
        return {"emails": [
            {"item_id": i.id, "subject": i.title, "meta": i.summary,
             "status": i.status, "web_link": i.linked_note_url}
            for i in items
        ], "count": len(items)}

    if name == "read_email_body":
        i = db.query(models.InboxItem).filter(
            models.InboxItem.id == a["item_id"], models.InboxItem.source == "ms_email"
        ).first()
        if not i:
            return {"error": "email no encontrado (¿id correcto y source ms_email?)"}
        return {"item_id": i.id, "subject": i.title, "meta": i.summary, "body": i.raw_content}

    if name == "sync_ms_teams":
        return sync_ms_teams(db, limit=int(a.get("limit", 25)))

    if name == "list_ms_teams":
        items = (
            db.query(models.InboxItem)
            .filter(models.InboxItem.source == "ms_teams")
            .order_by(models.InboxItem.created_at.desc())
            .limit(int(a.get("limit", 25)))
            .all()
        )
        # Metadata only — no body.
        return {"chats": [
            {"item_id": i.id, "title": i.title, "meta": i.summary,
             "status": i.status, "web_link": i.linked_note_url}
            for i in items
        ], "count": len(items)}

    if name == "read_teams_message":
        i = db.query(models.InboxItem).filter(
            models.InboxItem.id == a["item_id"], models.InboxItem.source == "ms_teams"
        ).first()
        if not i:
            return {"error": "mensaje de Teams no encontrado (¿id correcto y source ms_teams?)"}
        return {"item_id": i.id, "title": i.title, "meta": i.summary, "body": i.raw_content}

    if name == "get_briefing":
        return get_or_create_briefing(db, force=bool(a.get("refresh", False)))

    if name == "list_tasks":
        q = db.query(models.Task)
        if a.get("status"):
            q = q.filter(models.Task.status == a["status"])
        if a.get("project_id"):
            q = q.filter(models.Task.project_id == a["project_id"])
        if a.get("today_only"):
            q = q.filter(models.Task.is_today == True)
        if a.get("query"):
            q = q.filter(models.Task.title.ilike(f"%{a['query']}%"))
        limit = int(a.get("limit", 25))
        tasks = q.order_by(models.Task.created_at.desc()).limit(limit).all()
        return {"tasks": [task_to_dict(t, db) for t in tasks], "count": len(tasks)}

    if name == "get_task":
        t = db.query(models.Task).filter(models.Task.id == a["task_id"]).first()
        if not t:
            return {"error": "task not found"}
        d = task_to_dict(t, db)
        d["subtasks"] = [{"id": s.id, "title": s.title, "is_done": bool(s.is_done)} for s in t.subtasks]
        return d

    if name == "create_task":
        t = models.Task(
            title=a["title"],
            priority=a.get("priority", "medium"),
            status="todo",
            project_id=a.get("project_id"),
            due_date=_parse_date(a.get("due_date")),
            energy_tag=a.get("energy_tag"),
            description=a.get("description"),
        )
        db.add(t)
        db.commit()
        db.refresh(t)
        return {"created": True, "task": task_to_dict(t, db)}

    if name == "update_task":
        t = db.query(models.Task).filter(models.Task.id == a["task_id"]).first()
        if not t:
            return {"error": "task not found"}
        for f in ("title", "status", "priority", "description", "assignee", "project_id"):
            if f in a and a[f] is not None:
                setattr(t, f, a[f])
        if "due_date" in a:
            t.due_date = _parse_date(a["due_date"])  # empty/invalid -> None (clears)
        if a.get("status") == "done" and not t.completed_at:
            t.completed_at = datetime.utcnow()
        t.updated_at = datetime.utcnow()
        db.commit()
        return {"updated": True, "task": task_to_dict(t, db)}

    if name == "set_task_focus":
        t = db.query(models.Task).filter(models.Task.id == a["task_id"]).first()
        if not t:
            return {"error": "task not found"}
        fs = a["focus_state"]
        if fs in ("now", "next"):
            _clear_focus(db, fs, exclude_id=t.id)
        t.focus_state = fs
        if fs == "later":
            t.is_today = False
        else:
            t.is_today = True
            _mark_day_started(db)
        if fs == "now":
            db.query(models.Task).filter(models.Task.is_now == True).update(
                {models.Task.is_now: False}, synchronize_session=False
            )
            t.is_now = True
        t.updated_at = datetime.utcnow()
        db.commit()
        return {"updated": True, "task": task_to_dict(t, db)}

    if name == "complete_task":
        t = db.query(models.Task).filter(models.Task.id == a["task_id"]).first()
        if not t:
            return {"error": "task not found"}
        t.status = "done"
        t.completed_at = datetime.utcnow()
        t.is_now = False
        t.updated_at = datetime.utcnow()
        db.commit()
        return {"completed": True, "task": task_to_dict(t, db)}

    if name == "list_projects":
        q = db.query(models.Project)
        if a.get("active_only", True):
            q = q.filter(models.Project.is_active == True)
        ps = q.order_by(models.Project.name).all()
        return {"projects": [project_to_dict(p) for p in ps], "count": len(ps)}

    if name == "get_project":
        p = db.query(models.Project).filter(models.Project.id == a["project_id"]).first()
        if not p:
            return {"error": "project not found"}
        tasks = db.query(models.Task).filter(
            models.Task.project_id == p.id, models.Task.status != "done"
        ).order_by(models.Task.created_at).all()
        d = project_to_dict(p)
        d["open_tasks"] = [task_to_dict(t, db) for t in tasks]
        return d

    if name == "create_project":
        p = models.Project(name=a["name"].strip(), description=a.get("description"), is_active=True)
        db.add(p)
        db.commit()
        db.refresh(p)
        return {"created": True, "project": project_to_dict(p)}

    if name == "list_inbox":
        q = db.query(models.InboxItem)
        if a.get("status"):
            q = q.filter(models.InboxItem.status == a["status"])
        items = q.order_by(models.InboxItem.created_at.desc()).limit(int(a.get("limit", 25))).all()
        return {"items": [inbox_to_dict(i) for i in items], "count": len(items)}

    if name == "create_inbox_item":
        i = models.InboxItem(
            title=a["title"], raw_content=a.get("content"), summary=a.get("content"),
            source="self", source_type="capture", status="new", suggested_actions_json="[]",
        )
        db.add(i)
        db.commit()
        db.refresh(i)
        return {"created": True, "item": inbox_to_dict(i)}

    if name == "promote_inbox_to_task":
        item = db.query(models.InboxItem).filter(models.InboxItem.id == a["item_id"]).first()
        if not item:
            return {"error": "inbox item not found"}
        t = models.Task(
            title=(a.get("title") or item.title).strip(),
            description=item.raw_content or None,
            project_id=a.get("project_id"),
            source_type="inbox", source_ref=f"inbox:{item.id}",
            focus_state="later", status="todo",
        )
        db.add(t)
        db.flush()
        item.status = "promoted"
        item.linked_task_id = t.id
        item.reviewed_at = item.reviewed_at or datetime.utcnow()
        db.commit()
        db.refresh(t)
        return {"promoted": True, "task": task_to_dict(t, db)}

    if name == "search_notes":
        q = db.query(models.NoteItem)
        if a.get("query"):
            term = f"%{a['query']}%"
            q = q.filter(models.NoteItem.title.ilike(term) | models.NoteItem.content.ilike(term))
        notes = q.order_by(models.NoteItem.created_at.desc()).limit(int(a.get("limit", 25))).all()
        return {"notes": [note_to_dict(n) for n in notes], "count": len(notes)}

    if name == "create_note":
        n = models.NoteItem(
            title=a["title"], content=a["content"], summary=a.get("summary"),
            source="self", imported_at=datetime.utcnow(),
        )
        db.add(n)
        db.commit()
        db.refresh(n)
        return {"created": True, "note": note_to_dict(n)}

    if name == "list_notion_targets":
        if not notion.is_configured():
            return {"configured": False, "note": "NOTION_API_TOKEN not set; export unavailable."}
        targets = db.query(models.NotionExportTarget).order_by(
            models.NotionExportTarget.is_default.desc()
        ).all()
        return {
            "configured": True,
            "targets": [
                {"id": t.id, "name": t.name, "type": t.target_type, "is_default": bool(t.is_default)}
                for t in targets
            ],
        }

    if name == "export_note_to_notion":
        if not notion.is_configured():
            return {"error": "Notion not configured (NOTION_API_TOKEN missing)."}
        n = db.query(models.NoteItem).filter(models.NoteItem.id == a["note_id"]).first()
        if not n:
            return {"error": "note not found"}
        target = None
        if a.get("target_id"):
            target = db.query(models.NotionExportTarget).filter(
                models.NotionExportTarget.id == a["target_id"]
            ).first()
        if not target:
            target = db.query(models.NotionExportTarget).filter(
                models.NotionExportTarget.is_default == True
            ).first() or db.query(models.NotionExportTarget).first()
        if not target:
            return {"error": "no Notion export target configured. Add one in Integrations → Notion."}
        page = notion.export_note(n, target.notion_id, target.target_type)
        n.notion_page_id = page["id"].replace("-", "")
        n.notion_url = page.get("url") or f"https://notion.so/{n.notion_page_id}"
        n.exported_at = datetime.utcnow()
        n.last_synced_at = datetime.utcnow()
        db.commit()
        return {"exported": True, "notion_url": n.notion_url, "target": target.name}

    return {"error": f"unknown tool: {name}"}


# ─── System prompt ──────────────────────────────────────────────────────────

def build_system_prompt() -> str:
    today = date.today()
    return (
        "Eres el asistente de MyDay, el sistema personal de productividad de Paul "
        "(consultor en V2A Consulting). Tu trabajo: ayudarle a entender su día, priorizar, "
        "capturar y documentar su trabajo — conversando, no solo respondiendo.\n\n"
        f"Fecha de hoy: {today.isoformat()} ({today.strftime('%A')}).\n\n"
        "Principios:\n"
        "- Responde SIEMPRE en el idioma del usuario (normalmente español). Sé conciso y directo.\n"
        "- Eres agente: usa las herramientas para leer y actuar sobre los datos reales. No inventes "
        "tareas, proyectos ni IDs — consúltalos con las tools.\n"
        "- Para priorizar el día, empieza llamando a get_today_overview y razona sobre energía, "
        "vencimientos, foco actual y carga.\n"
        "- Antes de acciones destructivas o irreversibles (completar, cambiar estado masivo), confírmalo "
        "brevemente salvo que el usuario ya lo haya pedido explícitamente.\n"
        "- Para documentar avances/decisiones: crea una nota con create_note y, si el usuario quiere "
        "llevarlo a Notion, usa export_note_to_notion (revisa antes list_notion_targets).\n"
        "- Cuando ejecutes acciones, resume al final qué hiciste con los IDs/títulos afectados.\n"
        "- Si una herramienta devuelve un error, explícalo en lenguaje natural y propón una alternativa.\n\n"
        "Acceso actual: datos internos de MyDay (tareas, proyectos, inbox, notas), Notion, y Microsoft 365: "
        "CALENDARIO (get_calendar_events; planifica alrededor de las reuniones), EMAIL de Outlook "
        "(sync_ms_email/list_ms_email; cuerpos solo con read_email_body) y CHATS de Teams "
        "(sync_ms_teams/list_ms_teams; cuerpos solo con read_teams_message). Confidencialidad: para email y "
        "Teams a ti solo te llegan metadatos (asunto/tema, remitente, hora); el cuerpo se guarda local y solo "
        "lo lees si el usuario lo pide explícitamente para un ítem concreto."
    )


def _system_blocks():
    return [{"type": "text", "text": build_system_prompt(), "cache_control": {"type": "ephemeral"}}]


def _cached_tools():
    tools = [dict(t) for t in TOOLS]
    tools[-1] = {**tools[-1], "cache_control": {"type": "ephemeral"}}
    return tools


# ─── Streaming agent loop ─────────────────────────────────────────────────────

def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def run_agent_stream(db, conversation: "models.Conversation", user_text: str):
    """Generator yielding SSE events for one user turn. Persists the turn."""
    if not is_configured():
        yield _sse({"type": "error", "message": "ANTHROPIC_API_KEY no está configurada en .env."})
        return

    # Persist the user message
    user_msg = models.Message(conversation_id=conversation.id, role="user", content=user_text)
    db.add(user_msg)
    if not conversation.title:
        conversation.title = (user_text.strip()[:60] or "Nueva conversación")
    db.commit()

    # Rebuild context from prior persisted text turns + this one
    history = (
        db.query(models.Message)
        .filter(models.Message.conversation_id == conversation.id)
        .order_by(models.Message.created_at)
        .all()
    )
    messages = [{"role": m.role, "content": m.content} for m in history]

    client = get_client()
    tool_trace = []
    final_text_parts = []

    try:
        for _ in range(12):  # hard cap on tool-use rounds
            with client.messages.stream(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=_system_blocks(),
                tools=_cached_tools(),
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    final_text_parts.append(text)
                    yield _sse({"type": "delta", "text": text})
                final = stream.get_final_message()

            messages.append({"role": "assistant", "content": final.content})
            tool_uses = [b for b in final.content if getattr(b, "type", None) == "tool_use"]

            if final.stop_reason == "tool_use" and tool_uses:
                results = []
                for tu in tool_uses:
                    yield _sse({"type": "tool", "name": tu.name})
                    result = execute_tool(tu.name, tu.input, db)
                    tool_trace.append({"name": tu.name, "ok": "error" not in result})
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })
                messages.append({"role": "user", "content": results})
                continue
            break
    except Exception as exc:
        db.rollback()
        yield _sse({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
        return

    final_text = "".join(final_text_parts).strip()
    assistant_msg = models.Message(
        conversation_id=conversation.id,
        role="assistant",
        content=final_text or "(sin respuesta)",
        tool_trace=json.dumps(tool_trace, ensure_ascii=False) if tool_trace else None,
    )
    db.add(assistant_msg)
    conversation.updated_at = datetime.utcnow()
    db.commit()

    yield _sse({"type": "done", "tool_trace": tool_trace})


# ─── Phase 1: AI day planner ──────────────────────────────────────────────────

ENERGY_LABELS = {
    "high": "alta energía",
    "flow": "en flujo",
    "low": "baja energía",
    "scattered": "disperso/a",
}

PLAN_SLOTS = ["now", "next", "later_today", "defer", "reschedule"]

_PLAN_TOOL = {
    "name": "submit_day_plan",
    "description": "Devuelve el plan del día priorizado para Paul.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "2-4 frases en español: enfoque del día y razonamiento."},
            "assignments": {
                "type": "array",
                "description": "Una entrada por tarea relevante. No inventes IDs: usa solo los candidatos dados.",
                "items": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "integer"},
                        "title": {"type": "string"},
                        "slot": {"type": "string", "enum": PLAN_SLOTS},
                        "reason": {"type": "string", "description": "Por qué, breve (1 frase, español)."},
                        "new_due_date": {"type": "string", "description": "Solo si slot=reschedule: ISO YYYY-MM-DD."},
                    },
                    "required": ["task_id", "title", "slot", "reason"],
                },
            },
            "warnings": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Señales de atención: sobrecarga, demasiadas vencidas, conflictos.",
            },
        },
        "required": ["summary", "assignments"],
    },
}


def _gather_plan_candidates(db, today: date) -> list:
    """Collect a deduped candidate pool: today's tasks, overdue, due-soon, top backlog."""
    soon = today + timedelta(days=3)
    seen, candidates = set(), []

    def add(tasks):
        for t in tasks:
            if t.id not in seen:
                seen.add(t.id)
                candidates.append(t)

    add(db.query(models.Task).filter(
        models.Task.is_today == True, models.Task.status != "done"
    ).all())
    add(db.query(models.Task).filter(
        models.Task.due_date < today, models.Task.status != "done"
    ).order_by(models.Task.due_date).all())
    add(db.query(models.Task).filter(
        models.Task.due_date >= today, models.Task.due_date <= soon,
        models.Task.status != "done"
    ).order_by(models.Task.due_date).all())
    add(db.query(models.Task).filter(
        models.Task.status.in_(["todo", "doing"]), models.Task.is_today == False
    ).order_by(models.Task.priority.desc(), models.Task.created_at.desc()).limit(20).all())

    return candidates[:45]


def _recover_leaked_plan(plan: dict) -> dict:
    """Defensive: occasionally the model leaks nested params into the `summary`
    string using `</parameter><parameter name="...">` delimiters, leaving
    `assignments` empty. Recover the real summary and the assignments array."""
    summ = plan.get("summary")
    if not isinstance(summ, str) or "parameter" not in summ:
        return plan

    # Real summary is whatever precedes the first leaked delimiter.
    real_summary = re.split(r'</?\s*parameter', summ)[0].strip()
    plan["summary"] = real_summary

    decoder = json.JSONDecoder()
    if not plan.get("assignments"):
        m = re.search(r'name="assignments">\s*(\[)', summ)
        if m:
            try:
                arr, _ = decoder.raw_decode(summ[m.start(1):].strip())
                if isinstance(arr, list):
                    plan["assignments"] = arr
            except Exception:
                pass
    if not plan.get("warnings"):
        m = re.search(r'name="warnings">\s*(\[)', summ)
        if m:
            try:
                arr, _ = decoder.raw_decode(summ[m.start(1):].strip())
                if isinstance(arr, list):
                    plan["warnings"] = arr
            except Exception:
                pass
    return plan


def compute_day_plan(db, energy_today: Optional[str] = None) -> dict:
    """Ask the model to produce a structured day plan. Does NOT apply it."""
    if not is_configured():
        return {"error": "ANTHROPIC_API_KEY no está configurada."}

    today = date.today()
    if energy_today is None:
        log = db.query(models.DailyLog).filter(models.DailyLog.date == today).first()
        energy_today = log.energy_today if log else None

    candidates = _gather_plan_candidates(db, today)
    if not candidates:
        return {"summary": "No hay tareas candidatas para planificar. Captura algo primero.",
                "assignments": [], "warnings": [], "energy_today": energy_today, "candidate_count": 0}

    def _cand(t):
        d = task_to_dict(t, db)
        if t.due_date:
            delta = (t.due_date - today).days
            d["due_in_days"] = delta
            d["overdue"] = delta < 0
        return d

    cand_json = json.dumps([_cand(t) for t in candidates], ensure_ascii=False)
    energy_str = ENERGY_LABELS.get(energy_today or "", "no indicada")
    events = safe_calendar(days=1)
    cal_json = json.dumps(events, ensure_ascii=False) if events else "[]"

    system = (
        "Eres el planificador del día de Paul (consultor en V2A Consulting), perfil ENFP + ADHD: "
        "necesita un día enfocado, pocas cosas a la vez, sin sobrecarga. Tu trabajo es ARMAR el día, "
        "no solo describirlo.\n\n"
        f"Fecha: {today.isoformat()} ({today.strftime('%A')}). Energía hoy: {energy_str}.\n\n"
        "Reglas de planificación:\n"
        "- Asigna EXACTAMENTE una tarea a 'now' y como mucho una a 'next'. Elige la de mayor impacto/urgencia "
        "que encaje con la energía.\n"
        "- 'later_today' para lo demás que sí debe hacerse hoy (sé selectivo: máximo 3-4).\n"
        "- 'defer' para lo que no es para hoy (lo saca del día).\n"
        "- 'reschedule' (con new_due_date) para vencidas que ya no aplican a su fecha original.\n"
        "- Con energía baja/dispersa: prioriza tareas admin/low_energy y reduce la carga. Con energía alta/flujo: "
        "ataca lo creativo/de mayor impacto.\n"
        "- Tareas en estado 'waiting' dependen de terceros: normalmente NO van a 'now'/'next'.\n"
        "- No inventes IDs ni tareas. Usa solo los candidatos. Llama a submit_day_plan una vez."
    )
    user = (
        "Agenda de hoy en Microsoft 365 (metadata; planifica alrededor de estas reuniones, "
        "no las dupliques como tareas):\n" + cal_json + "\n\n"
        "Candidatos de tareas (JSON). due_in_days negativo = vencida. "
        "Arma el plan del día:\n\n" + cand_json
    )

    client = get_client()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=[{"type": "text", "text": system}],
        tools=[_PLAN_TOOL],
        tool_choice={"type": "tool", "name": "submit_day_plan"},
        messages=[{"role": "user", "content": user}],
    )
    plan = None
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "submit_day_plan":
            plan = block.input
            break
    if not plan:
        return {"error": "El modelo no devolvió un plan."}

    plan = _recover_leaked_plan(plan)

    # Enrich assignments with current task context for display
    by_id = {t.id: t for t in candidates}
    enriched = []
    for a in plan.get("assignments", []):
        t = by_id.get(a.get("task_id"))
        if not t:
            continue  # drop hallucinated/non-candidate ids
        a["current_status"] = t.status
        a["priority"] = t.priority
        a["due_date"] = _d(t.due_date)
        enriched.append(a)
    plan["assignments"] = enriched
    plan.setdefault("warnings", [])
    plan["energy_today"] = energy_today
    plan["candidate_count"] = len(candidates)
    return plan


def apply_day_plan(db, assignments: list) -> dict:
    """Apply a list of {task_id, slot, new_due_date?} assignments to the DB."""
    applied = []
    # Clear existing now/next so the new plan owns them cleanly.
    for st in ("now", "next"):
        _clear_focus(db, st)
    db.query(models.Task).filter(models.Task.is_now == True).update(
        {models.Task.is_now: False}, synchronize_session=False
    )

    for a in assignments or []:
        t = db.query(models.Task).filter(models.Task.id == a.get("task_id")).first()
        if not t:
            continue
        slot = a.get("slot")
        if slot == "now":
            t.focus_state = "now"; t.is_today = True; t.is_now = True
            _mark_day_started(db)
        elif slot == "next":
            t.focus_state = "next"; t.is_today = True
            _mark_day_started(db)
        elif slot == "later_today":
            t.focus_state = "later_today"; t.is_today = True
            _mark_day_started(db)
        elif slot == "defer":
            t.focus_state = "later"; t.is_today = False; t.is_now = False
        elif slot == "reschedule":
            t.focus_state = "later"; t.is_today = False; t.is_now = False
            nd = _parse_date(a.get("new_due_date"))
            if nd:
                t.due_date = nd
        else:
            continue
        t.updated_at = datetime.utcnow()
        applied.append({"task_id": t.id, "slot": slot})

    db.commit()
    return {"applied": True, "count": len(applied), "assignments": applied}


# ─── Weekly auto-plan: LLM reasoning layer over the deterministic engine ───────

_WEEK_PLAN_TOOL = {
    "name": "submit_week_plan",
    "description": "Devuelve el plan semanal de bloques de trabajo para Paul, encajados en sus huecos libres.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "2-4 frases en español: cómo organizaste la semana y por qué."},
            "assignments": {
                "type": "array",
                "description": "Una entrada por tarea que COLOCAS en un hueco. No inventes IDs ni días: usa solo los dados.",
                "items": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "integer"},
                        "day": {"type": "string", "description": "Fecha del bloque, ISO YYYY-MM-DD. Debe ser uno de los días con huecos."},
                        "start": {"type": "string", "description": "Hora local de inicio HH:MM (24h), dentro de un hueco libre."},
                        "minutes": {"type": "integer", "description": "Duración en minutos (15-240). Cabe dentro del hueco."},
                        "reason": {"type": "string", "description": "Por qué aquí/ahora, 1 frase breve en español (energía, agrupación, urgencia)."},
                    },
                    "required": ["task_id", "day", "start", "minutes", "reason"],
                },
            },
            "deferred": {
                "type": "array",
                "description": "Tareas que decides NO agendar esta semana a propósito (dejar buffer / evitar sobrecarga).",
                "items": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "integer"},
                        "reason": {"type": "string", "description": "Por qué la dejas fuera, 1 frase en español."},
                    },
                    "required": ["task_id", "reason"],
                },
            },
            "warnings": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Señales de atención: semana sobrecargada, demasiadas vencidas, poco hueco.",
            },
        },
        "required": ["summary", "assignments"],
    },
}


def _fmt_free_by_day(free_by_day: dict, today: date) -> str:
    """Render free intervals as human, day-labelled lines for the prompt."""
    lines = []
    for d_iso in sorted(free_by_day):
        ivs = free_by_day[d_iso]
        if not ivs:
            continue
        try:
            d = date.fromisoformat(d_iso)
            label = f"{d.strftime('%A')} {d_iso}"
        except Exception:
            label = d_iso
        slots = ", ".join(f"{s // 60:02d}:{s % 60:02d}-{e // 60:02d}:{e % 60:02d} ({e - s}min)"
                           for s, e in ivs)
        lines.append(f"- {label}: {slots}")
    return "\n".join(lines) if lines else "(sin huecos libres esta semana)"


def compute_week_plan(free_by_day: dict, tasks: list, energy_today: Optional[str] = None,
                      calendar: Optional[list] = None, today: Optional[date] = None) -> dict:
    """Ask the model to place prioritized tasks into the week's free slots, reasoning
    about energy/time-of-day, grouping and buffer. Returns a validated-by-schema plan;
    the caller still slot-validates each assignment before writing draft blocks.
    Returns {"error": ...} if the LLM is not configured or returns nothing."""
    if not is_configured():
        return {"error": "ANTHROPIC_API_KEY no está configurada."}
    today = today or date.today()
    valid_ids = {t.get("id") for t in tasks}
    valid_days = set(free_by_day)

    free_str = _fmt_free_by_day(free_by_day, today)
    tasks_json = json.dumps(tasks, ensure_ascii=False)
    cal_json = json.dumps(calendar or [], ensure_ascii=False)
    energy_str = ENERGY_LABELS.get(energy_today or "", "no indicada")

    system = (
        "Eres el planificador SEMANAL de Paul (consultor en V2A Consulting), perfil ENFP + ADHD: "
        "necesita una semana enfocada, sin sobrecarga, con trabajo agrupado y aire para respirar. "
        "Tu trabajo es ENCAJAR las tareas en los huecos libres, no solo describirlas.\n\n"
        f"Fecha de hoy: {today.isoformat()} ({today.strftime('%A')}). Energía reportada: {energy_str}.\n\n"
        "Reglas de planificación:\n"
        "- Coloca cada bloque DENTRO de un hueco libre listado, en su día, con start+minutes que QUEPAN en ese hueco. "
        "No solapes dos bloques. No uses días ni horas fuera de los huecos dados.\n"
        "- Trabajo creativo/de alta concentración o alta energía → MAÑANA. Admin/rutina/baja energía → tarde. "
        "Usa energy_tag y la energía reportada.\n"
        "- AGRUPA tareas del mismo proyecto/contexto en el mismo día o en bloques contiguos cuando tenga sentido.\n"
        "- Respeta vencimientos: lo vencido/urgente (due_in_days bajo o negativo) va primero y pronto.\n"
        "- DEJA BUFFER: no llenes cada hueco al 100%. Es mejor una semana realista que una saturada. "
        "Puedes mover a 'deferred' tareas de bajo valor para no sobrecargar (di por qué).\n"
        "- Duración: usa la estimación de la tarea si existe; si no, 60 min. Máximo 240.\n"
        "- No inventes IDs ni días ni tareas. Usa solo los candidatos y los huecos dados. "
        "Llama a submit_week_plan exactamente una vez."
    )
    user = (
        "Huecos libres de la semana (planifica DENTRO de estos; ya excluyen reuniones, almuerzo y bloques existentes):\n"
        + free_str + "\n\n"
        "Reuniones reales de Microsoft 365 esta semana (contexto; NO las dupliques como tareas):\n"
        + cal_json + "\n\n"
        "Tareas candidatas, ya ordenadas por prioridad (JSON). due_in_days negativo = vencida. "
        "Encaja las que importan en los huecos y razona cada colocación:\n\n" + tasks_json
    )

    client = get_client()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=[{"type": "text", "text": system}],
        tools=[_WEEK_PLAN_TOOL],
        tool_choice={"type": "tool", "name": "submit_week_plan"},
        messages=[{"role": "user", "content": user}],
    )
    plan = None
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "submit_week_plan":
            plan = block.input
            break
    if not plan:
        return {"error": "El modelo no devolvió un plan."}

    plan = _recover_leaked_plan(plan)

    # Drop hallucinated ids/days; the caller still checks slot-fit + overlap.
    clean = []
    for a in plan.get("assignments", []) or []:
        if a.get("task_id") in valid_ids and a.get("day") in valid_days:
            clean.append(a)
    plan["assignments"] = clean
    plan["deferred"] = [d for d in (plan.get("deferred") or []) if d.get("task_id") in valid_ids]
    plan.setdefault("warnings", [])
    return plan


# ─── Phase 2: Microsoft 365 (email + calendar) ────────────────────────────────

def safe_calendar(days: int = 1) -> list:
    """Fetch calendar events, swallowing errors / not-connected into []."""
    try:
        if ms_graph.is_connected():
            return ms_graph.get_calendar_events(days=days)
    except Exception:
        pass
    return []


def sync_ms_email(db, limit: int = 25) -> dict:
    """Pull recent Outlook messages into the inbox (deduped). Bodies stay local."""
    if not ms_graph.mail_enabled():
        return {"error": "El acceso a email (Mail.Read) requiere aprobación de admin en tu tenant y "
                         "aún no está habilitado. El calendario sí funciona."}
    if not ms_graph.is_connected():
        return {"error": "No conectado a Microsoft 365. Conéctalo en Integraciones → Microsoft 365."}
    try:
        messages = ms_graph.get_messages(top=limit)
    except Exception as exc:
        return {"error": str(exc)}
    imported = skipped = 0
    for msg in messages:
        fields = ms_graph.email_to_inbox_fields(msg)
        dup = db.query(models.InboxItem).filter(
            models.InboxItem.source == "ms_email",
            models.InboxItem.external_id == fields["external_id"],
        ).first()
        if dup:
            skipped += 1
            continue
        db.add(models.InboxItem(**fields))
        imported += 1
    db.commit()
    return {"imported": imported, "skipped": skipped}


def sync_ms_teams(db, limit: int = 25) -> dict:
    """Pull recent Teams chats into the inbox (deduped). Message bodies stay local."""
    if not ms_graph.teams_enabled():
        return {"error": "El acceso a Teams (Chat.Read) requiere aprobación de admin en tu tenant y "
                         "aún no está habilitado."}
    if not ms_graph.is_connected():
        return {"error": "No conectado a Microsoft 365. Conéctalo en Integraciones → Microsoft 365."}
    try:
        chats = ms_graph.get_chat_messages(top=limit)
    except Exception as exc:
        return {"error": str(exc)}
    imported = skipped = 0
    for chat in chats:
        fields = ms_graph.teams_to_inbox_fields(chat)
        if not fields.get("external_id"):
            skipped += 1
            continue
        dup = db.query(models.InboxItem).filter(
            models.InboxItem.source == "ms_teams",
            models.InboxItem.external_id == fields["external_id"],
        ).first()
        if dup:
            skipped += 1
            continue
        db.add(models.InboxItem(**fields))
        imported += 1
    db.commit()
    return {"imported": imported, "skipped": skipped}


# ─── Phase 3: Proactive briefing + stall radar ─────────────────────────────────

_BRIEFING_TOOL = {
    "name": "submit_briefing",
    "description": "Devuelve el briefing proactivo del día para Paul.",
    "input_schema": {
        "type": "object",
        "properties": {
            "headline": {"type": "string", "description": "Una línea (<=110 chars) para la notificación: el objetivo del día."},
            "objective": {"type": "string", "description": "EL único objetivo principal de hoy (concreto y accionable)."},
            "objective_reason": {"type": "string", "description": "Por qué es la prioridad (1 frase)."},
            "now": {"type": "string", "description": "Título de la tarea foco 'ahora', o vacío."},
            "next": {"type": "string", "description": "Título de la tarea 'siguiente', o vacío."},
            "meetings": {"type": "string", "description": "Resumen breve de reuniones de hoy, o 'Sin reuniones hoy'."},
            "stalls": {
                "type": "array",
                "description": "Tareas estancadas (mucho tiempo en el plato). Sé selectivo: máximo 5, las más importantes.",
                "items": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "integer"},
                        "title": {"type": "string"},
                        "issue": {"type": "string", "description": "Por qué está estancada (ej. '12 días sin avanzar')."},
                        "action": {"type": "string", "description": "El siguiente paso MÍNIMO, o 'matar'/'delegar a X'/'reprogramar'."},
                    },
                    "required": ["task_id", "title", "issue", "action"],
                },
            },
            "encouragement": {"type": "string", "description": "Una línea breve de cierre, directa y motivadora."},
        },
        "required": ["headline", "objective", "stalls"],
    },
}


def _recover_leaked(d: dict) -> dict:
    """Generic recovery: if the model leaked nested params into a string value
    using `</parameter><parameter name="K">` delimiters, redistribute them."""
    for k, v in list(d.items()):
        if isinstance(v, str) and 'parameter name="' in v:
            d[k] = re.split(r'</?\s*parameter', v)[0].strip()
            dec = json.JSONDecoder()
            for m in re.finditer(r'name="([a-zA-Z_]+)"\s*>\s*', v):
                key = m.group(1)
                rest = v[m.end():].lstrip()
                try:
                    val, _ = dec.raw_decode(rest)
                    d[key] = val
                except Exception:
                    seg = re.split(r'</?\s*parameter', rest)[0].strip()
                    if seg:
                        d[key] = seg
            break
    return d


def _stall_candidates(db, today: date) -> list:
    """Tasks that may be stalled: overdue, old-and-untouched, or stuck in 'doing'."""
    tasks = db.query(models.Task).filter(models.Task.status.notin_(["done", "dropped"])).all()
    out = []
    for t in tasks:
        created_days = (today - t.created_at.date()).days if t.created_at else 0
        updated_days = (today - t.updated_at.date()).days if t.updated_at else 0
        overdue_days = (today - t.due_date).days if t.due_date and t.due_date < today else 0
        stalled = (
            overdue_days > 0
            or (t.status == "doing" and updated_days >= 2)
            or (t.status in ("todo", "backlog") and created_days >= 5 and not t.is_today)
            or (t.status == "waiting" and updated_days >= 4)
        )
        if not stalled:
            continue
        out.append({
            "task_id": t.id, "title": t.title, "status": t.status, "priority": t.priority,
            "assignee": t.assignee, "days_since_created": created_days,
            "days_since_update": updated_days, "overdue_days": overdue_days,
            "project_id": t.project_id,
        })
    out.sort(key=lambda x: (x["overdue_days"], x["days_since_update"]), reverse=True)
    return out[:25]


def compute_briefing(db, energy_today: Optional[str] = None) -> dict:
    """Generate the proactive morning briefing (objective + stall radar)."""
    if not is_configured():
        return {"error": "ANTHROPIC_API_KEY no está configurada."}

    today = date.today()
    if energy_today is None:
        log = db.query(models.DailyLog).filter(models.DailyLog.date == today).first()
        energy_today = log.energy_today if log else None

    today_tasks = db.query(models.Task).filter(
        models.Task.is_today == True, models.Task.status != "done"
    ).order_by(models.Task.priority.desc()).all()
    stalls = _stall_candidates(db, today)
    events = safe_calendar(days=1)

    ctx = {
        "today_tasks": [task_to_dict(t, db) for t in today_tasks],
        "stall_candidates": stalls,
        "meetings": events,
        "energy": energy_today,
    }
    energy_str = ENERGY_LABELS.get(energy_today or "", "no indicada")

    system = (
        "Eres el coach proactivo de Paul (consultor V2A, perfil ENFP + ADHD). Su problema: las cosas se "
        "quedan demasiado tiempo 'en su plato' por cuenta propia. Tu trabajo: darle UN objetivo claro y "
        "empujarlo a CERRAR lo estancado. Sé directo, breve, accionable — nada de listas abrumadoras.\n\n"
        f"Fecha: {today.isoformat()} ({today.strftime('%A')}). Energía: {energy_str}.\n\n"
        "Reglas:\n"
        "- 'objective': UNA sola cosa, la de mayor impacto/urgencia para hoy (idealmente atada a un vencimiento "
        "o reunión). Concreta, no vaga.\n"
        "- 'stalls': de stall_candidates elige las que de verdad importan (máx 5). Para cada una da el siguiente "
        "paso MÍNIMO para destrabarla, o recomienda matarla/delegarla/reprogramarla si ya no aplica.\n"
        "- Planifica alrededor de las reuniones; no las dupliques como tareas.\n"
        "- 'headline': una línea potente para la notificación de escritorio.\n"
        "- Tono: como un jefe de staff que te conoce. Llama por nombre (Paul). Español.\n"
        "- No inventes task_id: usa solo los dados. Llama submit_briefing una vez."
    )
    user = "Contexto del día (JSON):\n\n" + json.dumps(ctx, ensure_ascii=False)

    client = get_client()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=[{"type": "text", "text": system}],
        tools=[_BRIEFING_TOOL],
        tool_choice={"type": "tool", "name": "submit_briefing"},
        messages=[{"role": "user", "content": user}],
    )
    briefing = None
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "submit_briefing":
            briefing = block.input
            break
    if not briefing:
        return {"error": "El modelo no devolvió un briefing."}

    briefing = _recover_leaked(briefing)
    briefing.setdefault("stalls", [])
    # Drop hallucinated task ids in stalls
    valid_ids = {s["task_id"] for s in stalls}
    briefing["stalls"] = [s for s in briefing["stalls"] if s.get("task_id") in valid_ids]
    briefing["date"] = today.isoformat()
    briefing["generated_at"] = datetime.utcnow().isoformat()
    return briefing


def get_or_create_briefing(db, force: bool = False) -> dict:
    """Return today's cached briefing, generating + caching it if missing/forced."""
    today = date.today()
    row = db.query(models.Briefing).filter(models.Briefing.date == today).first()
    if row and not force:
        try:
            return json.loads(row.content)
        except Exception:
            pass

    briefing = compute_briefing(db)
    if "error" in briefing:
        return briefing

    payload = json.dumps(briefing, ensure_ascii=False)
    if row:
        row.content = payload
        row.created_at = datetime.utcnow()
    else:
        db.add(models.Briefing(date=today, content=payload))
    db.commit()
    return briefing
