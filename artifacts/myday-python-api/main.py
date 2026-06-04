import json
import os
import pathlib
from contextlib import asynccontextmanager
from datetime import datetime, date, timedelta
from typing import Optional, List

# Load local .env (repo root) so ANTHROPIC_API_KEY / NOTION_API_TOKEN are available.
# Must run before reading env-dependent config below.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
except Exception:
    pass

import notion_client as notion

from fastapi import FastAPI, Depends, HTTPException, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import or_, text as sa_text
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

import models
import schemas
import agent
import ms_graph
from database import engine, get_db, Base, SessionLocal

BASE = "/task-manager"
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

STATUSES = ["backlog", "todo", "doing", "waiting", "done", "dropped"]
STATUS_LABELS = {"backlog": "Backlog", "todo": "To Do", "doing": "Doing", "waiting": "Waiting", "done": "Done", "dropped": "Dropped"}

MUST_DO_CAP = 6
TODAY_VISIBLE_CAP = 4  # max Later Today tasks shown before "+N more"
SUGGESTIONS_CAP = 7

FOCUS_STATES = ["now", "next", "later_today", "later"]
TIME_BLOCKS = ["morning", "afternoon", "evening"]
ENERGY_TAGS = ["creative", "admin", "social", "low_energy"]

MONTH_FIELD = {
    1: "active_jan", 2: "active_feb", 3: "active_mar", 4: "active_apr",
    5: "active_may", 6: "active_jun", 7: "active_jul", 8: "active_aug",
    9: "active_sep", 10: "active_oct", 11: "active_nov", 12: "active_dec",
}
MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}
MONTH_ABBR = ["jan", "feb", "mar", "apr", "may", "jun",
               "jul", "aug", "sep", "oct", "nov", "dec"]


# ─── DB Migration helpers ─────────────────────────────────────────────────────

def run_migrations():
    """Add new columns to existing tables safely (SQLite idempotent ALTER TABLE)."""
    task_cols = [
        ("focus_state", "TEXT"),
        ("time_block", "TEXT"),
        ("energy_tag", "TEXT"),
        ("is_now", "BOOLEAN DEFAULT 0"),
        ("energy_type", "VARCHAR(20)"),
        ("time_estimate_minutes", "INTEGER"),
        ("today_flag", "BOOLEAN DEFAULT 0"),
        ("today_category", "VARCHAR(10)"),
        ("card_id", "INTEGER"),             # bridge: linked Kanban card
        ("status_note", "TEXT"),
        ("assignee", "VARCHAR(100)"),
    ]
    log_cols = [
        ("has_morning_checkin", "BOOLEAN DEFAULT 0"),
        ("energy_today", "VARCHAR(30)"),
        ("day_closed", "BOOLEAN DEFAULT 0"),
    ]
    inbox_cols = [
        ("linked_note_id", "INTEGER"),
    ]
    project_cols = [
        ("source_ref", "TEXT"),
        ("imported_at", "TEXT"),
        ("notion_page_id", "TEXT"),
        ("notion_url", "TEXT"),
        ("exported_at", "DATETIME"),
        ("last_synced_at", "DATETIME"),
    ]
    note_cols = [
        ("notion_page_id", "TEXT"),
        ("notion_url", "TEXT"),
        ("exported_at", "DATETIME"),
        ("last_synced_at", "DATETIME"),
    ]
    table_migrations = [
        ("tasks", task_cols),
        ("daily_logs", log_cols),
        ("inbox_items", inbox_cols),
        ("projects", project_cols),
        ("note_items", note_cols),
    ]
    with engine.connect() as conn:
        for table, cols in table_migrations:
            for col, col_type in cols:
                try:
                    conn.execute(sa_text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                    conn.commit()
                except Exception:
                    pass


# ─── Bridge helpers ───────────────────────────────────────────────────────────

def _bridge_available(db: Session) -> bool:
    """Return True if the shared Kanban 'cards' table is accessible.
    Only possible when both services share a PostgreSQL instance."""
    if engine.dialect.name != "postgresql":
        return False
    try:
        db.execute(sa_text("SELECT 1 FROM cards LIMIT 0"))
        return True
    except Exception:
        return False


# ─── Streak helper ────────────────────────────────────────────────────────────

def calc_streak(db: Session) -> int:
    """Count consecutive days (ending today) where daily_log.started == True."""
    today = date.today()
    streak = 0
    check_date = today
    for _ in range(365):  # cap at 1 year to prevent infinite loop
        log = db.query(models.DailyLog).filter(
            models.DailyLog.date == check_date,
            models.DailyLog.started == True,
        ).first()
        if log:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break
    return streak


# ─── Helpers ──────────────────────────────────────────────────────────────────

def ensure_settings(db: Session) -> models.Settings:
    settings = db.query(models.Settings).first()
    if not settings:
        settings = models.Settings(
            morning_ritual_time="08:30",
            wip_limit_doing=3,
            default_priority="medium",
        )
        db.add(settings)
        db.commit()
    return settings


def get_or_create_daily_log(db: Session, for_date: date) -> models.DailyLog:
    log = db.query(models.DailyLog).filter(models.DailyLog.date == for_date).first()
    if not log:
        log = models.DailyLog(date=for_date)
        db.add(log)
        db.commit()
        db.refresh(log)
    return log


def mark_today_started(db: Session, for_date: date) -> None:
    log = get_or_create_daily_log(db, for_date)
    if not log.started:
        log.started = True
        log.started_at = datetime.utcnow()
        db.commit()


def mark_morning_checkin(db: Session, for_date: date) -> None:
    log = get_or_create_daily_log(db, for_date)
    log.has_morning_checkin = True
    if not log.started:
        log.started = True
        log.started_at = datetime.utcnow()
    db.commit()


def mark_today_completed(db: Session, for_date: date) -> None:
    log = get_or_create_daily_log(db, for_date)
    if not log.has_completed_task:
        log.has_completed_task = True
        db.commit()


def compute_streak(db: Session) -> int:
    streak = 0
    check = date.today()
    for _ in range(365):
        log = db.query(models.DailyLog).filter(models.DailyLog.date == check).first()
        if log and (log.started or log.has_completed_task):
            streak += 1
            check -= timedelta(days=1)
        else:
            break
    return streak


ENERGY_TO_TAG = {
    "high":      "creative",
    "flow":      "creative",
    "low":       "low_energy",
    "scattered": "low_energy",
}

def score_task(task, today: date, energy_today: Optional[str], current_hour: int):
    """Return (score, reasons, energy_match, time_match) for a candidate task."""
    score = 0
    reasons = []
    energy_match = False
    time_match = False

    if task.due_date:
        if task.due_date < today:
            days_overdue = (today - task.due_date).days
            score += min(days_overdue * 2, 10)
            reasons.append("overdue")
        elif task.due_date == today:
            score += 5
            reasons.append("due_today")
        elif task.due_date == today + timedelta(days=1):
            score += 2
            reasons.append("due_soon")

    if task.priority == "high":
        score += 3
    elif task.priority == "medium":
        score += 1

    if energy_today and energy_today in ENERGY_TO_TAG:
        if task.energy_tag == ENERGY_TO_TAG[energy_today]:
            score += 3
            energy_match = True
            reasons.append("energy_match")

    if task.time_block:
        if current_hour < 12 and task.time_block == "morning":
            score += 2
            time_match = True
            reasons.append("time_match")
        elif 12 <= current_hour < 17 and task.time_block == "afternoon":
            score += 2
            time_match = True
            reasons.append("time_match")
        elif current_hour >= 17 and task.time_block == "evening":
            score += 2
            time_match = True
            reasons.append("time_match")

    if hasattr(task, "subtasks") and task.subtasks:
        score += 1

    return score, reasons, energy_match, time_match


def build_suggestions(db: Session, today: date, exclude_ids: set, energy_today: Optional[str] = None) -> list:
    from datetime import datetime as _dt
    current_hour = _dt.now().hour

    base_filter = [
        models.Task.is_today == False,
        models.Task.status != "done",
        or_(
            models.Task.focus_state != "later",
            models.Task.due_date == today,  # always surface due-today even if parked
        ),
    ]
    candidates = db.query(models.Task).filter(*base_filter).all()

    seen: set = set(exclude_ids)
    scored = []
    for task in candidates:
        if task.id in seen:
            continue
        seen.add(task.id)
        score, reasons, energy_match, time_match = score_task(task, today, energy_today, current_hour)
        task._score = score
        task._reasons = reasons
        task._energy_match = energy_match
        task._time_match = time_match
        scored.append((score, task))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [t for _, t in scored[:SUGGESTIONS_CAP]]


def clear_focus_state(db: Session, state: str, exclude_id: Optional[int] = None):
    """Ensure only one task holds a given focus_state at a time."""
    q = db.query(models.Task).filter(models.Task.focus_state == state)
    if exclude_id:
        q = q.filter(models.Task.id != exclude_id)
    for t in q.all():
        t.focus_state = "later_today" if t.is_today else None
    db.commit()


def get_cop_initiatives_this_month(db: Session, leader_name: str = "Paul") -> list:
    month_num = date.today().month
    field_name = MONTH_FIELD[month_num]
    month_col = getattr(models.CoPInitiative, field_name)
    return (
        db.query(models.CoPInitiative)
        .filter(month_col == True, models.CoPInitiative.leader.ilike(f"%{leader_name}%"))
        .order_by(models.CoPInitiative.topic, models.CoPInitiative.topic_description)
        .all()
    )


@asynccontextmanager
async def lifespan(app):
    models.Base.metadata.create_all(bind=engine)
    run_migrations()
    db = SessionLocal()
    try:
        ensure_settings(db)
        # Sweep any done tasks that still carry is_now=True (data integrity guard)
        db.query(models.Task).filter(
            models.Task.status == "done", models.Task.is_now == True
        ).update({models.Task.is_now: False}, synchronize_session=False)
        db.commit()
    finally:
        db.close()
    yield


app = FastAPI(title="MyDay Task Manager", lifespan=lifespan)
templates = Jinja2Templates(directory=TEMPLATES_DIR)

import re as _re

def _datefmt(dt, fmt: str) -> str:
    """Cross-platform strftime: %-d, %-I etc. strip leading zeros on all OSes."""
    if dt is None:
        return ''
    if '%-' in fmt:
        def _strip_zero(m):
            val = dt.strftime(f'%{m.group(1)}').lstrip('0')
            return val or '0'
        fmt = _re.sub(r'%-([dIHmMS])', _strip_zero, fmt)
    return dt.strftime(fmt)

templates.env.filters['datefmt'] = _datefmt

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount(f"{BASE}/static", StaticFiles(directory=STATIC_DIR), name="static")


# ─── Root redirect ───────────────────────────────────────────────────────────

@app.get("/")
async def root_redirect(db: Session = Depends(get_db)):
    # Command Center is the home / morning landing; My Day is the execution view.
    return RedirectResponse(url=f"{BASE}/command-center", status_code=302)


# ─── Health ──────────────────────────────────────────────────────────────────

@app.get(f"{BASE}/healthz")
def health():
    return {"status": "ok"}


# ─── Home ─────────────────────────────────────────────────────────────────────

@app.get(f"{BASE}", response_class=HTMLResponse)
@app.get(f"{BASE}/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    return RedirectResponse(url=f"{BASE}/command-center", status_code=302)


# ─── Morning Check-In ────────────────────────────────────────────────────────

@app.get(f"{BASE}/morning-checkin", response_class=HTMLResponse)
async def morning_checkin_get(request: Request, db: Session = Depends(get_db)):
    # Retired: the morning ritual now lives in My Day's briefing card.
    return RedirectResponse(url=f"{BASE}/my-day", status_code=302)


@app.post(f"{BASE}/morning-checkin")
async def morning_checkin_post(
    request: Request,
    energy_today: Optional[str] = Form(default=None),
    brain_dump: str = Form(default=""),
    win_ids: list[int] = Form(default=[]),
    nice_ids: list[int] = Form(default=[]),
    db: Session = Depends(get_db),
):
    today = date.today()
    # 1. Save energy_today to daily log
    log = db.query(models.DailyLog).filter(models.DailyLog.date == today).first()
    if not log:
        log = models.DailyLog(date=today)
        db.add(log)
    if energy_today:
        log.energy_today = energy_today
    log.has_morning_checkin = True

    # 2. Brain dump → Inbox items
    lines = [line.strip() for line in brain_dump.splitlines() if line.strip()]
    for line in lines:
        item = models.InboxItem(
            title=line,
            source="morning_checkin",
            source_type="brain_dump",
            status="new",
        )
        db.add(item)

    # 3 & 4. Set today_flag + today_category on selected tasks; clear on deselected
    selected_ids = set(win_ids) | set(nice_ids)
    all_flagged = db.query(models.Task).filter(models.Task.today_flag == True).all()
    for task in all_flagged:
        if task.id not in selected_ids:
            task.today_flag = False
            task.today_category = None
    for task_id in win_ids:
        task = db.query(models.Task).filter(models.Task.id == task_id).first()
        if task:
            task.today_flag = True
            task.today_category = "win"
    for task_id in nice_ids:
        task = db.query(models.Task).filter(models.Task.id == task_id).first()
        if task:
            task.today_flag = True
            task.today_category = "nice"

    db.commit()

    # AJAX / fetch() callers get JSON; plain form submissions get redirect
    is_fetch = (
        request.headers.get("X-Requested-With") == "fetch"
        or "application/json" in request.headers.get("Accept", "")
    )
    if is_fetch:
        return JSONResponse({
            "ok": True,
            "redirect": f"{BASE}/my-day",
            "wins": len(win_ids),
            "nice": len(nice_ids),
            "inbox_added": len(lines),
        })
    return RedirectResponse(url=f"{BASE}/my-day", status_code=303)


# ─── My Day ──────────────────────────────────────────────────────────────────

@app.get(f"{BASE}/my-day", response_class=HTMLResponse)
async def my_day(
    request: Request,
    from_brain_dump: int = Query(default=0),
    db: Session = Depends(get_db),
):
    today = date.today()
    today_start = datetime(today.year, today.month, today.day)

    # All today tasks not done
    active_today = (
        db.query(models.Task)
        .filter(models.Task.is_today == True, models.Task.status != "done")
        .order_by(models.Task.priority.desc())
        .all()
    )
    active_today_ids = {t.id for t in active_today}

    # Focus state buckets — prefer kanban is_now flag, fall back to focus_state
    is_now_task = db.query(models.Task).filter(
        models.Task.is_now == True, models.Task.status != "done"
    ).first()
    now_task = is_now_task or next((t for t in active_today if t.focus_state == "now"), None)
    next_task = next((t for t in active_today if t.focus_state == "next"), None)
    later_today_all = [t for t in active_today if t.focus_state in ("later_today", None)]
    later_today_tasks = later_today_all[:TODAY_VISIBLE_CAP]
    later_today_overflow = max(0, len(later_today_all) - TODAY_VISIBLE_CAP)

    # Time block buckets (all today active tasks)
    morning_tasks = [t for t in active_today if t.time_block == "morning"]
    afternoon_tasks = [t for t in active_today if t.time_block == "afternoon"]
    evening_tasks = [t for t in active_today if t.time_block == "evening"]
    unblocked_today = [t for t in active_today if not t.time_block]

    # Stats
    overdue_count = (
        db.query(models.Task)
        .filter(models.Task.due_date < today, models.Task.status != "done")
        .count()
    )
    completed_today = (
        db.query(models.Task)
        .filter(
            models.Task.completed_at >= today_start,
            models.Task.status == "done",
        )
        .count()
    )
    daily_log = db.query(models.DailyLog).filter(models.DailyLog.date == today).first()
    today_started = daily_log.started if daily_log else False
    energy_today  = daily_log.energy_today if daily_log else None
    streak = compute_streak(db)

    # Suggestions (exclude already-today tasks, boost energy-matched)
    suggestions = build_suggestions(db, today, active_today_ids, energy_today=energy_today)

    cop_initiatives = get_cop_initiatives_this_month(db, "Paul")
    current_month_name = MONTH_NAMES[today.month]

    # Today's flagged tasks split by category (wins vs nice-to-haves)
    # Only show tasks in active states — waiting/backlog are not actionable today
    today_flagged = (
        db.query(models.Task)
        .filter(models.Task.today_flag == True,
                models.Task.status.in_(["todo", "doing"]))
        .order_by(models.Task.priority.desc())
        .all()
    )
    wins_tasks = [t for t in today_flagged if t.today_category == "win"]
    nice_tasks  = [t for t in today_flagged if t.today_category == "nice"]
    done_wins   = (
        db.query(models.Task)
        .filter(models.Task.today_flag == True, models.Task.today_category == "win",
                models.Task.status == "done")
        .all()
    )

    # All done tasks today (for done section)
    done_today = (
        db.query(models.Task)
        .filter(models.Task.is_today == True, models.Task.status == "done")
        .all()
    )

    # ── Today's inbox nudge stats (read-only, for evening panel) ──
    today_inbox_all = (
        db.query(models.InboxItem)
        .filter(models.InboxItem.created_at >= today_start)
        .all()
    )
    inbox_today = {
        "total": len(today_inbox_all),
        "new": sum(1 for i in today_inbox_all if i.status == "new"),
        "reviewing": sum(1 for i in today_inbox_all if i.status == "reviewing"),
        "promoted": sum(1 for i in today_inbox_all if i.status == "promoted"),
        "archived": sum(1 for i in today_inbox_all if i.status == "archived"),
    }
    inbox_today["unreviewed"] = inbox_today["new"] + inbox_today["reviewing"]

    # ── Recent captures for widget (last 5, any date, non-archived) ──
    recent_captures = (
        db.query(models.InboxItem)
        .filter(models.InboxItem.status != "archived")
        .order_by(models.InboxItem.created_at.desc())
        .limit(5)
        .all()
    )

    projects = (
        db.query(models.Project)
        .filter(models.Project.is_active == True)
        .order_by(models.Project.name)
        .all()
    )

    return templates.TemplateResponse(
        request, "my_day.html",
        {
            "wins_tasks": wins_tasks,
            "projects": projects,
            "nice_tasks": nice_tasks,
            "done_wins": done_wins,
            "now_task": now_task,
            "next_task": next_task,
            "later_today_tasks": later_today_tasks,
            "later_today_overflow": later_today_overflow,
            "morning_tasks": morning_tasks,
            "afternoon_tasks": afternoon_tasks,
            "evening_tasks": evening_tasks,
            "unblocked_today": unblocked_today,
            "active_today": active_today,
            "done_today": done_today,
            "suggestions": suggestions,
            "overdue_count": overdue_count,
            "completed_today": completed_today,
            "today_started": today_started,
            "streak": streak,
            "today": today,
            "base": BASE,
            "cop_initiatives": cop_initiatives,
            "current_month_name": current_month_name,
            "from_brain_dump": bool(from_brain_dump),
            "must_do_cap": MUST_DO_CAP,
            "today_total": len(active_today),
            "focus_states": FOCUS_STATES,
            "time_blocks": TIME_BLOCKS,
            "energy_tags": ENERGY_TAGS,
            "inbox_today": inbox_today,
            "recent_captures": recent_captures,
            "energy_today": energy_today,
            "tomorrow": today + timedelta(days=1),
        },
    )


@app.get(f"{BASE}/api/today-status")
def today_status_api(db: Session = Depends(get_db)):
    today = date.today()
    log = db.query(models.DailyLog).filter(models.DailyLog.date == today).first()
    return {
        "has_checkin": bool(log and log.has_morning_checkin),
        "started":     bool(log and log.started),
        "day_closed":  bool(log and log.day_closed),
    }


@app.post(f"{BASE}/my-day/start-today")
async def start_today(db: Session = Depends(get_db)):
    mark_today_started(db, date.today())
    return RedirectResponse(url=f"{BASE}/my-day", status_code=303)


# ─── Close the Day ────────────────────────────────────────────────────────────

@app.get(f"{BASE}/close-day", response_class=HTMLResponse)
async def close_day_get(request: Request, db: Session = Depends(get_db)):
    today = date.today()
    now_hour = datetime.now().hour

    # All today_flag tasks
    flagged_all = (
        db.query(models.Task)
        .filter(models.Task.today_flag == True)
        .order_by(models.Task.today_category, models.Task.priority.desc())
        .all()
    )
    wins_done       = [t for t in flagged_all if t.today_category == "win"  and t.status == "done"]
    wins_incomplete = [t for t in flagged_all if t.today_category == "win"  and t.status not in ("done", "dropped")]
    nice_done       = [t for t in flagged_all if t.today_category == "nice" and t.status == "done"]
    nice_incomplete = [t for t in flagged_all if t.today_category == "nice" and t.status not in ("done", "dropped")]

    daily_log = db.query(models.DailyLog).filter(models.DailyLog.date == today).first()
    already_closed = daily_log.day_closed if daily_log else False

    # Completed today (any task with completed_at = today)
    today_start = datetime.combine(today, datetime.min.time())
    today_end   = datetime.combine(today + timedelta(days=1), datetime.min.time())
    completed_today_count = (
        db.query(models.Task)
        .filter(models.Task.completed_at >= today_start, models.Task.completed_at < today_end)
        .count()
    )

    # Wins stats
    wins_total = len(wins_done) + len(wins_incomplete)
    wins_done_count = len(wins_done)

    # Streak
    streak = calc_streak(db)

    # Contextual message (no shame)
    if wins_done_count >= 1:
        if wins_done_count == wins_total and wins_total > 0:
            day_msg = "You delivered on every win you planned. That's real."
        else:
            day_msg = "You showed up and delivered. That's what counts."
    elif daily_log and daily_log.started:
        day_msg = "You showed up today. That alone is progress."
    else:
        day_msg = "Tomorrow is a fresh start. Rest up."

    # Inbox stats for today
    inbox_today_new = (
        db.query(models.InboxItem)
        .filter(models.InboxItem.created_at >= today_start, models.InboxItem.status == "new")
        .count()
    )
    inbox_today_promoted = (
        db.query(models.InboxItem)
        .filter(models.InboxItem.created_at >= today_start, models.InboxItem.status == "promoted")
        .count()
    )
    inbox_today_archived = (
        db.query(models.InboxItem)
        .filter(models.InboxItem.created_at >= today_start, models.InboxItem.status == "archived")
        .count()
    )
    inbox_today_total = inbox_today_new + inbox_today_promoted + inbox_today_archived

    return templates.TemplateResponse(request, "close_day.html", {
        "wins_done":             wins_done,
        "wins_incomplete":       wins_incomplete,
        "nice_done":             nice_done,
        "nice_incomplete":       nice_incomplete,
        "already_closed":        already_closed,
        "now_hour":              now_hour,
        "completed_today_count": completed_today_count,
        "wins_done_count":       wins_done_count,
        "wins_total":            wins_total,
        "streak":                streak,
        "day_msg":               day_msg,
        "inbox_today_new":       inbox_today_new,
        "inbox_today_promoted":  inbox_today_promoted,
        "inbox_today_archived":  inbox_today_archived,
        "inbox_today_total":     inbox_today_total,
        "base": BASE,
    })


@app.post(f"{BASE}/close-day")
async def close_day_post(request: Request, db: Session = Depends(get_db)):
    today = date.today()

    # Clear flags on all completed today_flag tasks; reset focus_state
    flagged_all = db.query(models.Task).filter(models.Task.today_flag == True).all()
    for task in flagged_all:
        task.focus_state    = None  # always clear focus state
        task.today_flag     = False
        task.today_category = None
        if task.status not in ("done", "dropped"):
            # Incomplete tasks not already handled by evening-action → roll to tomorrow
            task.is_today = True

    # Mark the day as closed
    log = db.query(models.DailyLog).filter(models.DailyLog.date == today).first()
    if not log:
        log = models.DailyLog(date=today)
        db.add(log)
    log.day_closed = True
    db.commit()

    is_fetch = request.headers.get("X-Requested-With") == "fetch"
    if is_fetch:
        return JSONResponse({"ok": True})
    return RedirectResponse(url=f"{BASE}/my-day", status_code=303)


@app.post(f"{BASE}/close-day/reopen")
async def close_day_reopen(request: Request, db: Session = Depends(get_db)):
    today = date.today()
    log = db.query(models.DailyLog).filter(models.DailyLog.date == today).first()
    if log:
        log.day_closed = False
        db.commit()
    is_fetch = request.headers.get("X-Requested-With") == "fetch"
    if is_fetch:
        return JSONResponse({"ok": True})
    return RedirectResponse(url=f"{BASE}/close-day", status_code=303)


@app.patch(f"{BASE}/tasks/{{task_id}}/evening-action")
async def evening_action(task_id: int, request: Request, db: Session = Depends(get_db)):
    """Per-task action during Evening Reset: tomorrow | later | drop."""
    body = await request.json()
    action = body.get("action", "tomorrow")

    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if action == "tomorrow":
        task.is_today       = True
        task.today_flag     = False  # will be re-set in morning check-in
        task.focus_state    = None
    elif action == "later":
        task.is_today       = False
        task.today_flag     = False
        task.today_category = None
        task.focus_state    = None
    elif action == "drop":
        task.status         = "dropped"
        task.today_flag     = False
        task.today_category = None
        task.focus_state    = None

    task.updated_at = datetime.utcnow()
    db.commit()
    return JSONResponse({"ok": True, "action": action, "task_id": task_id})


@app.post(f"{BASE}/tasks/{{task_id}}/set-today")
async def set_today(
    task_id: int,
    focus_state: str = Form(default="later_today"),
    time_block: Optional[str] = Form(default=None),
    redirect_to: str = Form(default=""),
    db: Session = Depends(get_db),
):
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if db_task:
        db_task.is_today = True
        db_task.focus_state = focus_state or "later_today"
        if time_block:
            db_task.time_block = time_block
        db_task.updated_at = datetime.utcnow()
        db.commit()
        mark_today_started(db, date.today())
    dest = redirect_to if redirect_to else f"{BASE}/my-day"
    return RedirectResponse(url=dest, status_code=303)


@app.post(f"{BASE}/tasks/{{task_id}}/unset-today")
async def unset_today(
    task_id: int,
    redirect_to: str = Form(default=""),
    db: Session = Depends(get_db),
):
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if db_task:
        db_task.is_today = False
        db_task.focus_state = None
        db_task.updated_at = datetime.utcnow()
        db.commit()
    dest = redirect_to if redirect_to else f"{BASE}/my-day"
    return RedirectResponse(url=dest, status_code=303)


@app.post(f"{BASE}/tasks/{{task_id}}/focus-state")
async def set_focus_state(
    task_id: int,
    focus_state: str = Form(...),
    db: Session = Depends(get_db),
):
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Enforce single "now" and single "next"
    if focus_state in ("now", "next"):
        clear_focus_state(db, focus_state, exclude_id=task_id)

    db_task.focus_state = focus_state
    if focus_state == "later":
        db_task.is_today = False
    elif focus_state in ("now", "next", "later_today"):
        db_task.is_today = True
        mark_today_started(db, date.today())

    db_task.updated_at = datetime.utcnow()
    db.commit()
    return RedirectResponse(url=f"{BASE}/my-day", status_code=303)


@app.post(f"{BASE}/tasks/{{task_id}}/time-block")
async def set_time_block(
    task_id: int,
    time_block: str = Form(...),
    db: Session = Depends(get_db),
):
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    db_task.time_block = time_block if time_block != "none" else None
    db_task.updated_at = datetime.utcnow()
    db.commit()
    return RedirectResponse(url=f"{BASE}/my-day", status_code=303)


# ─── Task Edit ───────────────────────────────────────────────────────────────

@app.get(f"{BASE}/tasks/{{task_id}}/edit", response_class=HTMLResponse)
async def edit_task_get(
    task_id: int,
    request: Request,
    back: str = Query(default=""),
    db: Session = Depends(get_db),
):
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    projects = db.query(models.Project).all()
    return templates.TemplateResponse(
        request, "task_edit.html",
        {
            "base": BASE,
            "task": db_task,
            "projects": projects,
            "back": back or f"{BASE}/tasks-page",
            "focus_states": FOCUS_STATES,
            "time_blocks": TIME_BLOCKS,
            "energy_tags": ENERGY_TAGS,
            "statuses": STATUSES,
            "status_labels": STATUS_LABELS,
        },
    )


@app.post(f"{BASE}/tasks/{{task_id}}/edit")
async def edit_task_post(
    task_id: int,
    title: str = Form(...),
    status: str = Form("todo"),
    priority: str = Form("medium"),
    due_date: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    focus_state: Optional[str] = Form(None),
    time_block: Optional[str] = Form(None),
    energy_tag: Optional[str] = Form(None),
    energy_type: Optional[str] = Form(None),
    time_estimate_minutes: Optional[str] = Form(None),
    project_id: Optional[str] = Form(None),
    status_note: Optional[str] = Form(None),
    assignee: Optional[str] = Form(None),
    back: str = Form(default=""),
    db: Session = Depends(get_db),
):
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    db_task.title = title
    db_task.status = status
    db_task.priority = priority
    db_task.description = description or None
    db_task.status_note = status_note or None
    db_task.assignee = assignee.strip() if assignee and assignee.strip() else None
    db_task.focus_state = focus_state if focus_state and focus_state != "none" else None
    db_task.time_block = time_block if time_block and time_block != "none" else None
    db_task.energy_tag = energy_tag if energy_tag and energy_tag != "none" else None
    db_task.energy_type = energy_type if energy_type and energy_type.strip() else None
    db_task.time_estimate_minutes = int(time_estimate_minutes) if time_estimate_minutes and time_estimate_minutes.strip().isdigit() else None
    db_task.project_id = int(project_id) if project_id and project_id.strip() else None
    if due_date:
        try:
            db_task.due_date = date.fromisoformat(due_date)
        except ValueError:
            db_task.due_date = None
    else:
        db_task.due_date = None
    if status == "done":
        db_task.is_now = False          # clear NOW on completion
        if not db_task.completed_at:
            db_task.completed_at = datetime.utcnow()
            mark_today_completed(db, date.today())
    else:
        db_task.completed_at = None
        if status not in ("todo", "doing"):
            db_task.is_now = False      # waiting/backlog can't be the NOW task
    db_task.updated_at = datetime.utcnow()
    db.commit()
    dest = back if back else f"{BASE}/tasks-page"
    return RedirectResponse(url=dest, status_code=303)


# ─── Kanban ──────────────────────────────────────────────────────────────────

@app.post(f"{BASE}/tasks/{{task_id}}/quick-edit")
async def quick_edit_task(
    task_id: int,
    title: str = Form(...),
    priority: str = Form("medium"),
    due_date: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Lightweight AJAX card edit — returns JSON, no redirect."""
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    db_task.title = title
    db_task.priority = priority
    db_task.description = description or None
    if due_date:
        try:
            db_task.due_date = date.fromisoformat(due_date)
        except ValueError:
            db_task.due_date = None
    else:
        db_task.due_date = None
    db_task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_task)
    return JSONResponse({
        "status": "ok",
        "task": {
            "id": db_task.id,
            "title": db_task.title,
            "priority": db_task.priority,
            "due_date": db_task.due_date.isoformat() if db_task.due_date else None,
            "description": db_task.description,
        }
    })


@app.get(f"{BASE}/kanban", response_class=HTMLResponse)
async def kanban(request: Request, db: Session = Depends(get_db)):
    today = date.today()
    today_start = datetime(today.year, today.month, today.day)

    # All tasks except dropped, grouped by status
    all_tasks = (
        db.query(models.Task)
        .filter(models.Task.status != "dropped")
        .options(joinedload(models.Task.project))
        .order_by(models.Task.priority.desc(), models.Task.created_at.asc())
        .all()
    )

    board_statuses = ["backlog", "todo", "doing", "waiting", "done"]
    columns = {s: [] for s in board_statuses}
    for t in all_tasks:
        if t.status in columns:
            columns[t.status].append(t)

    # NOW task
    now_task = db.query(models.Task).filter(
        models.Task.is_now == True, models.Task.status != "done"
    ).first()

    # Done today count
    done_today_count = (
        db.query(models.Task)
        .filter(
            models.Task.completed_at >= today_start,
            models.Task.status == "done",
        )
        .count()
    )

    wip_limit = 3

    response = templates.TemplateResponse(
        request, "kanban.html",
        {
            "base": BASE,
            "statuses": board_statuses,
            "status_labels": STATUS_LABELS,
            "columns": columns,
            "wip_limit": wip_limit,
            "now_task_id": now_task.id if now_task else None,
            "done_today_count": done_today_count,
            "today": today,
        },
    )
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response


@app.post(f"{BASE}/tasks/{{task_id}}/status")
async def update_status(
    task_id: int,
    status: str = Form(...),
    redirect_to: str = Form(default=""),
    db: Session = Depends(get_db),
):
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if db_task:
        db_task.status = status
        db_task.updated_at = datetime.utcnow()
        if status == "done":
            db_task.is_now = False          # clear NOW on completion
            if not db_task.completed_at:
                db_task.completed_at = datetime.utcnow()
                mark_today_completed(db, date.today())
        else:
            db_task.completed_at = None
            if status not in ("todo", "doing"):
                db_task.is_now = False      # waiting/backlog can't be the NOW task
        db.commit()
    dest = redirect_to if redirect_to else f"{BASE}/kanban"
    return RedirectResponse(url=dest, status_code=303)


# ─── Bridge: push task → Kanban card ─────────────────────────────────────────

STATUS_TO_COLUMN_TITLE = {
    "backlog":  "Back log",
    "todo":     "To Do",
    "doing":    "In Progress",
    "waiting":  "In Progress",
    "done":     "Done",
}

@app.post(f"{BASE}/tasks/{{task_id}}/push-to-kanban")
async def push_to_kanban(
    task_id: int,
    redirect_to: str = Form(default=""),
    request: Request = None,
    db: Session = Depends(get_db),
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Guard: bridge requires shared PostgreSQL
    if not _bridge_available(db):
        is_fetch = (request and request.headers.get("X-Requested-With") == "fetch")
        if is_fetch:
            return JSONResponse(
                {"ok": False, "error": "Bridge requires shared PostgreSQL. Enable DATABASE_URL to use this feature."},
                status_code=503,
            )
        dest = redirect_to or f"{BASE}/tasks-page"
        return RedirectResponse(url=dest, status_code=303)

    # If already on Kanban, just redirect/return
    if task.card_id:
        is_fetch = (request and request.headers.get("X-Requested-With") == "fetch")
        if is_fetch:
            return JSONResponse({"ok": True, "card_id": task.card_id, "already_linked": True})
        dest = redirect_to or f"{BASE}/tasks-page"
        return RedirectResponse(url=dest, status_code=303)

    # Determine target column
    col_title = STATUS_TO_COLUMN_TITLE.get(task.status or "todo", "To Do")
    col_row = db.execute(
        sa_text("SELECT id FROM columns WHERE title = :t LIMIT 1"), {"t": col_title}
    ).fetchone()
    if not col_row:
        col_row = db.execute(sa_text("SELECT id FROM columns ORDER BY position LIMIT 1")).fetchone()
    column_id = col_row[0] if col_row else 1

    # Get current max position in that column
    max_pos = db.execute(
        sa_text("SELECT COALESCE(MAX(position),0) FROM cards WHERE column_id = :cid"), {"cid": column_id}
    ).scalar() or 0

    # Build description: energy + time estimate
    desc_parts = []
    if task.energy_tag:
        desc_parts.append(task.energy_tag.replace("_", " "))
    if task.time_estimate_minutes:
        desc_parts.append(f"{task.time_estimate_minutes} min")
    if task.project:
        desc_parts.append(f"Project: {task.project.name}")
    description = " · ".join(desc_parts) if desc_parts else None

    # Insert the card
    row = db.execute(
        sa_text("""
            INSERT INTO cards (column_id, title, description, position, priority, due_date, task_id, created_at)
            VALUES (:col, :title, :desc, :pos, :pri, :due, :tid, now())
            RETURNING id
        """),
        {
            "col": column_id,
            "title": task.title,
            "desc": description,
            "pos": max_pos + 1,
            "pri": task.priority,
            "due": str(task.due_date) if task.due_date else None,
            "tid": task_id,
        },
    ).fetchone()
    card_id = row[0]

    # Link the task back
    task.card_id = card_id
    db.commit()

    is_fetch = (request and request.headers.get("X-Requested-With") == "fetch")
    if is_fetch:
        return JSONResponse({"ok": True, "card_id": card_id, "column": col_title})
    dest = redirect_to or f"{BASE}/tasks-page"
    return RedirectResponse(url=dest, status_code=303)


@app.post(f"{BASE}/tasks/{{task_id}}/set-now")
async def set_now(task_id: int, db: Session = Depends(get_db)):
    db.query(models.Task).update({models.Task.is_now: False})
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if task:
        task.is_now = True
    db.commit()
    return JSONResponse({"ok": True})


@app.post(f"{BASE}/tasks/{{task_id}}/clear-now")
async def clear_now(task_id: int, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if task:
        task.is_now = False
    db.commit()
    return JSONResponse({"ok": True})


@app.post(f"{BASE}/tasks/{{task_id}}/subtasks")
async def create_subtask(task_id: int, title: str = Form(...), db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        return JSONResponse({"error": "Task not found"}, status_code=404)
    sub = models.Subtask(task_id=task_id, title=title.strip())
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return JSONResponse({"id": sub.id, "title": sub.title, "is_done": sub.is_done})


@app.post(f"{BASE}/tasks/{{task_id}}/subtasks/{{subtask_id}}/toggle")
async def toggle_subtask(task_id: int, subtask_id: int, db: Session = Depends(get_db)):
    sub = db.query(models.Subtask).filter(
        models.Subtask.id == subtask_id,
        models.Subtask.task_id == task_id,
    ).first()
    if not sub:
        return JSONResponse({"error": "Not found"}, status_code=404)
    sub.is_done = not sub.is_done
    sub.completed_at = datetime.utcnow() if sub.is_done else None
    db.commit()
    return JSONResponse({"id": sub.id, "is_done": sub.is_done})


@app.delete(f"{BASE}/tasks/{{task_id}}/subtasks/{{subtask_id}}")
async def delete_subtask(task_id: int, subtask_id: int, db: Session = Depends(get_db)):
    sub = db.query(models.Subtask).filter(
        models.Subtask.id == subtask_id,
        models.Subtask.task_id == task_id,
    ).first()
    if sub:
        db.delete(sub)
        db.commit()
    return JSONResponse({"ok": True})


@app.post(f"{BASE}/tasks/{{task_id}}/start-focus")
async def start_focus(task_id: int, db: Session = Depends(get_db)):
    """Set task as NOW and redirect straight to the focus timer."""
    db.query(models.Task).update({models.Task.is_now: False})
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if task:
        task.is_now = True
    db.commit()
    return RedirectResponse(url=f"{BASE}/focus", status_code=303)


# ─── Tasks HTML pages ─────────────────────────────────────────────────────────

@app.get(f"{BASE}/tasks-page", response_class=HTMLResponse)
async def tasks_page(
    request: Request,
    status: Optional[str] = None,
    project_id: Optional[int] = None,
    is_today: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Task)
    if status:
        query = query.filter(models.Task.status == status)
    if project_id:
        query = query.filter(models.Task.project_id == project_id)
    if is_today is not None:
        query = query.filter(models.Task.is_today == is_today)
    tasks = query.order_by(models.Task.created_at.desc()).all()
    projects = db.query(models.Project).all()
    recurring = (
        db.query(models.RecurringTask)
        .filter(models.RecurringTask.active == True)
        .order_by(models.RecurringTask.title)
        .all()
    )
    return templates.TemplateResponse(
        request, "tasks.html",
        {
            "tasks": tasks,
            "projects": projects,
            "recurring": recurring,
            "base": BASE,
            "current_status": status,
            "current_project_id": project_id,
            "bridge_available": _bridge_available(db),
        },
    )


@app.post(f"{BASE}/tasks-page")
async def create_task_form(
    title: str = Form(...),
    project_id: Optional[str] = Form(None),
    priority: str = Form("medium"),
    due_date: Optional[str] = Form(None),
    status: str = Form("todo"),
    energy_type: Optional[str] = Form(None),
    time_estimate_minutes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    parsed_due: Optional[date] = None
    if due_date:
        try:
            parsed_due = date.fromisoformat(due_date)
        except ValueError:
            pass
    pid = int(project_id) if project_id and project_id.strip() else None
    etype = energy_type if energy_type and energy_type.strip() else None
    tmin = int(time_estimate_minutes) if time_estimate_minutes and time_estimate_minutes.strip().isdigit() else None
    task = models.Task(
        title=title, priority=priority, due_date=parsed_due, status=status,
        project_id=pid, energy_type=etype, time_estimate_minutes=tmin,
    )
    db.add(task)
    db.commit()
    return RedirectResponse(url=f"{BASE}/tasks-page", status_code=303)


@app.post(f"{BASE}/tasks-page/{{task_id}}/delete")
async def delete_task_form(task_id: int, db: Session = Depends(get_db)):
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if db_task:
        # Bridge cleanup: clear task_id on the linked Kanban card before deleting
        if db_task.card_id:
            try:
                db.execute(sa_text("UPDATE cards SET task_id = NULL WHERE id = :cid"), {"cid": db_task.card_id})
            except Exception:
                pass  # best-effort, non-fatal
        db.delete(db_task)
        db.commit()
    return RedirectResponse(url=f"{BASE}/tasks-page", status_code=303)


@app.post(f"{BASE}/tasks/bulk")
async def bulk_tasks(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    ids = [int(i) for i in data.get("ids", []) if str(i).isdigit()]
    action = data.get("action", "")
    value = data.get("value", "")
    if not ids or action not in ("status", "delete"):
        return JSONResponse({"ok": False, "error": "Invalid request"}, status_code=400)
    tasks = db.query(models.Task).filter(models.Task.id.in_(ids)).all()
    if action == "delete":
        for t in tasks:
            if t.card_id:
                try:
                    db.execute(sa_text("UPDATE cards SET task_id = NULL WHERE id = :cid"), {"cid": t.card_id})
                except Exception:
                    pass
            db.delete(t)
    elif action == "status":
        for t in tasks:
            t.status = value
            if value == "done" and not t.completed_at:
                t.completed_at = datetime.utcnow()
    db.commit()
    return JSONResponse({"ok": True, "count": len(tasks)})


# ─── CoP Admin (HTML) ─────────────────────────────────────────────────────────

@app.get(f"{BASE}/cop-admin", response_class=HTMLResponse)
async def cop_admin(request: Request, db: Session = Depends(get_db)):
    initiatives = (
        db.query(models.CoPInitiative)
        .order_by(models.CoPInitiative.topic, models.CoPInitiative.topic_description)
        .all()
    )
    return templates.TemplateResponse(
        request, "cop_initiatives.html",
        {"initiatives": initiatives, "base": BASE, "month_abbr": MONTH_ABBR},
    )


@app.post(f"{BASE}/cop-admin")
async def cop_admin_create(
    effort: Optional[str] = Form(None),
    topic: Optional[str] = Form(None),
    topic_description: Optional[str] = Form(None),
    subtopic: Optional[str] = Form(None),
    type_of_effort: Optional[str] = Form(None),
    focus_market: Optional[str] = Form(None),
    leader: Optional[str] = Form(None),
    cop_collaboration: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    active_jan: Optional[str] = Form(None),
    active_feb: Optional[str] = Form(None),
    active_mar: Optional[str] = Form(None),
    active_apr: Optional[str] = Form(None),
    active_may: Optional[str] = Form(None),
    active_jun: Optional[str] = Form(None),
    active_jul: Optional[str] = Form(None),
    active_aug: Optional[str] = Form(None),
    active_sep: Optional[str] = Form(None),
    active_oct: Optional[str] = Form(None),
    active_nov: Optional[str] = Form(None),
    active_dec: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    def to_bool(v): return v is not None and v.lower() in ("on", "true", "1", "yes")
    initiative = models.CoPInitiative(
        effort=effort or None, topic=topic or None,
        topic_description=topic_description or None, subtopic=subtopic or None,
        type_of_effort=type_of_effort or None, focus_market=focus_market or None,
        leader=leader or None, cop_collaboration=cop_collaboration or None, notes=notes or None,
        active_jan=to_bool(active_jan), active_feb=to_bool(active_feb), active_mar=to_bool(active_mar),
        active_apr=to_bool(active_apr), active_may=to_bool(active_may), active_jun=to_bool(active_jun),
        active_jul=to_bool(active_jul), active_aug=to_bool(active_aug), active_sep=to_bool(active_sep),
        active_oct=to_bool(active_oct), active_nov=to_bool(active_nov), active_dec=to_bool(active_dec),
    )
    db.add(initiative)
    db.commit()
    return RedirectResponse(url=f"{BASE}/cop-admin", status_code=303)


@app.post(f"{BASE}/cop-admin/{{initiative_id}}/delete")
async def cop_admin_delete(initiative_id: int, db: Session = Depends(get_db)):
    item = db.query(models.CoPInitiative).filter(models.CoPInitiative.id == initiative_id).first()
    if item:
        db.delete(item)
        db.commit()
    return RedirectResponse(url=f"{BASE}/cop-admin", status_code=303)


# ─── CoP CSV Import ───────────────────────────────────────────────────────────

# Look for the CSV at the repo root (two levels above this file)
_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
_COP_CSV = _REPO_ROOT / "cop_org_plan_pc.csv"


@app.get(f"{BASE}/cop-import", response_class=HTMLResponse)
async def cop_import_get(request: Request):
    return templates.TemplateResponse(
        request, "cop_import.html",
        {"base": BASE, "result": None, "csv_path": str(_COP_CSV)},
    )


@app.post(f"{BASE}/cop-import", response_class=HTMLResponse)
async def cop_import_post(request: Request, db: Session = Depends(get_db)):
    from import_cop_initiatives import run_import
    try:
        result = run_import(db, str(_COP_CSV))
    except FileNotFoundError as exc:
        result = {
            "imported": 0,
            "skipped": 0,
            "errors": [str(exc)],
        }
    return templates.TemplateResponse(
        request, "cop_import.html",
        {"base": BASE, "result": result, "csv_path": str(_COP_CSV)},
    )


# ─── Projects HTML pages ──────────────────────────────────────────────────────

@app.get(f"{BASE}/projects-list", response_class=HTMLResponse)
def projects_list_page(request: Request, db: Session = Depends(get_db)):
    projects = (
        db.query(models.Project)
        .options(joinedload(models.Project.tasks))
        .order_by(models.Project.is_active.desc(), models.Project.id.desc())
        .all()
    )
    return templates.TemplateResponse(
        request, "projects_list.html",
        {"base": BASE, "projects": projects},
    )


@app.post(f"{BASE}/projects-list/new")
def projects_create_html(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    proj = models.Project(
        name=name.strip(),
        description=description.strip() if description else None,
        is_active=True,
    )
    db.add(proj)
    db.commit()
    return RedirectResponse(url=f"{BASE}/projects-list", status_code=303)


@app.post(f"{BASE}/projects/{{project_id}}/archive")
def project_archive(project_id: int, db: Session = Depends(get_db)):
    proj = db.query(models.Project).filter(models.Project.id == project_id).first()
    if proj:
        proj.is_active = False
        db.commit()
    return RedirectResponse(url=f"{BASE}/projects-list", status_code=303)


@app.post(f"{BASE}/projects/{{project_id}}/activate")
def project_activate(project_id: int, db: Session = Depends(get_db)):
    proj = db.query(models.Project).filter(models.Project.id == project_id).first()
    if proj:
        proj.is_active = True
        db.commit()
    return RedirectResponse(url=f"{BASE}/projects-list", status_code=303)


# ─── Projects API ─────────────────────────────────────────────────────────────

@app.get(f"{BASE}/projects", response_model=List[schemas.ProjectRead])
def list_projects(db: Session = Depends(get_db)):
    return db.query(models.Project).all()


@app.post(f"{BASE}/projects", response_model=schemas.ProjectRead, status_code=201)
def create_project(project: schemas.ProjectCreate, db: Session = Depends(get_db)):
    db_project = models.Project(**project.model_dump())
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


# ─── Tasks API ────────────────────────────────────────────────────────────────

@app.get(f"{BASE}/tasks", response_model=List[schemas.TaskRead])
def list_tasks(
    status: Optional[str] = None,
    project_id: Optional[int] = None,
    is_today: Optional[bool] = None,
    focus_state: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Task)
    if status:
        query = query.filter(models.Task.status == status)
    if project_id is not None:
        query = query.filter(models.Task.project_id == project_id)
    if is_today is not None:
        query = query.filter(models.Task.is_today == is_today)
    if focus_state is not None:
        query = query.filter(models.Task.focus_state == focus_state)
    return query.order_by(models.Task.created_at.desc()).all()


@app.get(f"{BASE}/tasks/{{task_id}}", response_model=schemas.TaskDetail)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    result = schemas.TaskDetail.model_validate(task)
    result.subtasks = [schemas.SubtaskRead.model_validate(s) for s in task.subtasks]
    result.project_name = task.project.name if task.project else None
    return result


@app.patch(f"{BASE}/tasks/{{task_id}}", response_model=schemas.TaskRead)
def patch_task(task_id: int, update: schemas.TaskUpdate, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    if update.status == "done" and not task.completed_at:
        task.completed_at = datetime.utcnow()
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return task


@app.get(f"{BASE}/projects-api", response_model=List[schemas.ProjectRead])
def list_projects_api(db: Session = Depends(get_db)):
    return db.query(models.Project).filter(models.Project.is_active == True).order_by(models.Project.name).all()


@app.post(f"{BASE}/tasks", response_model=schemas.TaskRead, status_code=201)
def create_task(task: schemas.TaskCreate, db: Session = Depends(get_db)):
    db_task = models.Task(**task.model_dump())
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


@app.put(f"{BASE}/tasks/{{task_id}}", response_model=schemas.TaskRead)
def update_task(task_id: int, update: schemas.TaskUpdate, db: Session = Depends(get_db)):
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(db_task, field, value)
    db_task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_task)
    return db_task


@app.delete(f"{BASE}/tasks/{{task_id}}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    # Bridge cleanup: clear task_id on the linked Kanban card before deleting
    if db_task.card_id:
        try:
            db.execute(sa_text("UPDATE cards SET task_id = NULL WHERE id = :cid"), {"cid": db_task.card_id})
        except Exception:
            pass  # best-effort, non-fatal
    db.delete(db_task)
    db.commit()
    return {"success": True}


# ─── CoP Initiatives API ──────────────────────────────────────────────────────

@app.get(f"{BASE}/cop-initiatives", response_model=List[schemas.CoPInitiativeRead])
def list_cop_initiatives(db: Session = Depends(get_db)):
    return db.query(models.CoPInitiative).order_by(models.CoPInitiative.topic).all()


@app.post(f"{BASE}/cop-initiatives", response_model=schemas.CoPInitiativeRead, status_code=201)
def create_cop_initiative(initiative: schemas.CoPInitiativeCreate, db: Session = Depends(get_db)):
    db_item = models.CoPInitiative(**initiative.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@app.put(f"{BASE}/cop-initiatives/{{initiative_id}}", response_model=schemas.CoPInitiativeRead)
def update_cop_initiative(initiative_id: int, update: schemas.CoPInitiativeUpdate, db: Session = Depends(get_db)):
    db_item = db.query(models.CoPInitiative).filter(models.CoPInitiative.id == initiative_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Initiative not found")
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(db_item, field, value)
    db.commit()
    db.refresh(db_item)
    return db_item


@app.delete(f"{BASE}/cop-initiatives/{{initiative_id}}")
def delete_cop_initiative(initiative_id: int, db: Session = Depends(get_db)):
    db_item = db.query(models.CoPInitiative).filter(models.CoPInitiative.id == initiative_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Initiative not found")
    db.delete(db_item)
    db.commit()
    return {"success": True}


# ─── Quick-Add Task (FAB / N-key) ────────────────────────────────────────────

@app.post(f"{BASE}/tasks/quick-add")
async def quick_add_task(
    title: str = Form(...),
    priority: str = Form("medium"),
    energy_type: Optional[str] = Form(default=None),
    time_estimate_minutes: Optional[int] = Form(default=None),
    project_id: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
):
    task = models.Task(
        title=title,
        priority=priority,
        status="todo",
        energy_type=energy_type or None,
        time_estimate_minutes=time_estimate_minutes or None,
        project_id=int(project_id) if project_id and project_id.strip().isdigit() else None,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return JSONResponse({"status": "ok", "task_id": task.id, "title": task.title})


@app.post(f"{BASE}/tasks/inline-add")
async def inline_add_task(
    request: Request,
    db: Session = Depends(get_db),
):
    body = await request.json()
    title = (body.get("title") or "").strip()
    if not title:
        return JSONResponse({"ok": False, "error": "title required"}, status_code=422)

    today_category = body.get("today_category")
    focus_state    = body.get("focus_state")
    is_today       = bool(body.get("is_today", False))
    today_flag     = bool(today_category)

    task = models.Task(
        title=title,
        priority="medium",
        status="todo",
        is_today=is_today,
        focus_state=focus_state or None,
        today_flag=today_flag,
        today_category=today_category or None,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return JSONResponse({"ok": True, "task_id": task.id, "title": task.title})


# ─── Focus Mode ──────────────────────────────────────────────────────────────

@app.get(f"{BASE}/focus", response_class=HTMLResponse)
def focus_mode(request: Request, db: Session = Depends(get_db)):
    now_task = (
        db.query(models.Task)
        .filter(models.Task.focus_state == "now", models.Task.status != "done")
        .first()
    )
    return templates.TemplateResponse(
        request, "focus.html", {"base": BASE, "now_task": now_task}
    )


@app.post(f"{BASE}/focus/complete")
def focus_complete(
    task_id: int = Form(...),
    duration_minutes: int = Form(default=20),
    mark_done: bool = Form(default=False),
    db: Session = Depends(get_db),
):
    today = date.today()
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if task:
        task.updated_at = datetime.utcnow()
        if mark_done and task.status != "done":
            task.status = "done"
            task.completed_at = datetime.utcnow()
        mark_today_started(db, today)

    # Record the focus session
    session = models.FocusSession(
        task_id=task_id,
        started_at=datetime.utcnow() - timedelta(minutes=duration_minutes),
        duration_minutes=max(1, duration_minutes),
        completed=True,
        date=today,
    )
    db.add(session)
    db.commit()

    return JSONResponse({
        "status": "ok",
        "task_id": task_id,
        "duration": duration_minutes,
        "marked_done": mark_done and task is not None,
    })


# ─── Weekly Review ───────────────────────────────────────────────────────────

@app.get(f"{BASE}/weekly-review", response_class=HTMLResponse)
def weekly_review(request: Request, db: Session = Depends(get_db)):
    today = date.today()
    week_start = today - timedelta(days=6)

    # Build 7-day array (oldest → newest)
    days = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        log = db.query(models.DailyLog).filter(models.DailyLog.date == d).first()
        d_start = datetime.combine(d, datetime.min.time())
        d_end   = datetime.combine(d + timedelta(days=1), datetime.min.time())
        completed = (
            db.query(models.Task)
            .filter(models.Task.completed_at >= d_start, models.Task.completed_at < d_end)
            .count()
        )
        # Planned proxy: today_flag tasks + completed tasks for that day
        planned = completed  # V1 approximation (no historical snapshot)
        if d == today:
            planned = max(planned, db.query(models.Task).filter(models.Task.today_flag == True).count())
        days.append({
            "date":        d,
            "day_name":    d.strftime("%a"),
            "day_initial": d.strftime("%a")[0],
            "has_checkin": log.started if log else False,
            "is_today":    d == today,
            "completed":   completed,
            "planned":     max(planned, completed),
        })

    streak = calc_streak(db)
    checkin_days = sum(1 for d in days if d["has_checkin"])

    # Streak message
    if checkin_days == 7:
        streak_msg = "Perfect week. You showed up every day."
    elif checkin_days >= 5:
        streak_msg = "Strong consistency. Keep the rhythm."
    elif checkin_days >= 3:
        streak_msg = "You showed up more days than not. That's real."
    elif checkin_days >= 1:
        streak_msg = "Every day you show up is a win."
    else:
        streak_msg = "Fresh start this week."

    # Focus sessions this week
    total_focus_minutes = 0
    avg_focus_minutes   = 0
    has_focus_data      = False
    try:
        sessions = (
            db.query(models.FocusSession)
            .filter(models.FocusSession.date >= week_start, models.FocusSession.date <= today)
            .all()
        )
        if sessions:
            has_focus_data = True
            total_focus_minutes = sum(s.duration_minutes for s in sessions)
            active_days = len(set(s.date for s in sessions))
            avg_focus_minutes = round(total_focus_minutes / active_days) if active_days else 0
    except Exception:
        pass

    # Top wins this week (completed wins)
    week_start_dt = datetime.combine(week_start, datetime.min.time())
    top_wins = (
        db.query(models.Task)
        .filter(
            models.Task.today_category == "win",
            models.Task.status == "done",
            models.Task.completed_at >= week_start_dt,
        )
        .order_by(models.Task.completed_at.desc())
        .limit(5)
        .all()
    )

    return templates.TemplateResponse(request, "weekly_review.html", {
        "base":                 BASE,
        "today":                today,
        "week_start":           week_start,
        "days":                 days,
        "streak":               streak,
        "checkin_days":         checkin_days,
        "streak_msg":           streak_msg,
        "total_focus_minutes":  total_focus_minutes,
        "avg_focus_minutes":    avg_focus_minutes,
        "has_focus_data":       has_focus_data,
        "top_wins":             top_wins,
    })


# ─── Meeting Inbox ───────────────────────────────────────────────────────────

INBOX_STATUSES = ["new", "reviewing", "promoted", "archived"]


@app.get(f"{BASE}/inbox", response_class=HTMLResponse)
def inbox_list(request: Request, db: Session = Depends(get_db)):
    items = (
        db.query(models.InboxItem)
        .filter(models.InboxItem.status != "archived")
        .order_by(models.InboxItem.created_at.desc())
        .all()
    )
    archived_count = (
        db.query(models.InboxItem)
        .filter(models.InboxItem.status == "archived")
        .count()
    )
    unreviewed_count = sum(1 for i in items if i.status in ("new", "reviewing"))
    return templates.TemplateResponse(
        request, "inbox.html",
        {"base": BASE, "items": items, "archived_count": archived_count,
         "unreviewed_count": unreviewed_count},
    )


@app.post(f"{BASE}/inbox/quick-capture")
def inbox_quick_capture(
    title: str = Form(...),
    raw_content: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    item = models.InboxItem(
        source="manual",
        source_type="brain_dump",
        title=title.strip(),
        raw_content=raw_content.strip() if raw_content else None,
        status="new",
    )
    db.add(item)
    db.commit()
    return RedirectResponse(url=f"{BASE}/inbox", status_code=303)


@app.get(f"{BASE}/inbox/archived", response_class=HTMLResponse)
def inbox_archived(request: Request, db: Session = Depends(get_db)):
    items = (
        db.query(models.InboxItem)
        .filter(models.InboxItem.status == "archived")
        .order_by(models.InboxItem.created_at.desc())
        .all()
    )
    unreviewed_count = (
        db.query(models.InboxItem)
        .filter(models.InboxItem.status.in_(["new", "reviewing"]))
        .count()
    )
    return templates.TemplateResponse(
        request, "inbox.html",
        {"base": BASE, "items": items, "archived_count": len(items),
         "show_archived": True, "unreviewed_count": unreviewed_count},
    )


@app.get(f"{BASE}/meetings", response_class=HTMLResponse)
def meetings_list(request: Request, db: Session = Depends(get_db)):
    """
    Group all InboxItems by calendar date and source for a meeting-centric view.
    Read-only. No sync or promotion triggered here.
    """
    items = (
        db.query(models.InboxItem)
        .order_by(models.InboxItem.created_at.desc())
        .all()
    )

    # Group by date
    from collections import defaultdict, OrderedDict
    groups: dict = OrderedDict()
    for item in items:
        day = item.created_at.date()
        if day not in groups:
            groups[day] = []
        groups[day].append(item)

    # Build summary dicts for each date group
    day_summaries = []
    for day, day_items in groups.items():
        promoted = [i for i in day_items if i.status == "promoted"]
        unreviewed = [i for i in day_items if i.status in ("new", "reviewing")]
        archived = [i for i in day_items if i.status == "archived"]

        # Sub-group by source
        by_source: dict = OrderedDict()
        for item in day_items:
            src = item.source
            if src not in by_source:
                by_source[src] = []
            by_source[src].append(item)

        day_summaries.append({
            "date": day,
            "items": day_items,
            "by_source": by_source,
            "total": len(day_items),
            "promoted_count": len(promoted),
            "unreviewed_count": len(unreviewed),
            "archived_count": len(archived),
        })

    return templates.TemplateResponse(
        request, "meetings.html",
        {"base": BASE, "day_summaries": day_summaries},
    )


@app.get(f"{BASE}/inbox/{{item_id}}", response_class=HTMLResponse)
def inbox_detail(item_id: int, request: Request, db: Session = Depends(get_db)):
    item = db.query(models.InboxItem).filter(models.InboxItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    if item.status == "new":
        item.status = "reviewing"
        item.reviewed_at = datetime.utcnow()
        db.commit()
        db.refresh(item)
    actions = []
    if item.suggested_actions_json:
        try:
            actions = json.loads(item.suggested_actions_json)
        except Exception:
            actions = []
    linked_task = None
    if item.linked_task_id:
        linked_task = db.query(models.Task).filter(models.Task.id == item.linked_task_id).first()
    linked_project = None
    if item.linked_project_id:
        linked_project = db.query(models.Project).filter(models.Project.id == item.linked_project_id).first()
    linked_note = None
    if item.linked_note_id:
        linked_note = db.query(models.NoteItem).filter(models.NoteItem.id == item.linked_note_id).first()
    projects = db.query(models.Project).filter(models.Project.is_active == True).all()
    # Determine what it was promoted to (for status badge and notice)
    promoted_type = None
    if item.status == "promoted":
        if item.linked_task_id:
            promoted_type = "task"
        elif item.linked_project_id:
            promoted_type = "project"
        elif item.linked_note_id:
            promoted_type = "note"
    return templates.TemplateResponse(
        request, "inbox_detail.html",
        {
            "base": BASE,
            "item": item,
            "actions": actions,
            "linked_task": linked_task,
            "linked_project": linked_project,
            "linked_note": linked_note,
            "promoted_type": promoted_type,
            "projects": projects,
        },
    )


@app.post(f"{BASE}/inbox/ingest/whisper")
def ingest_whisper(payload: schemas.WhisperIngest, db: Session = Depends(get_db)):
    actions_json = json.dumps(payload.suggested_actions or [])
    item = models.InboxItem(
        source="whisper",
        source_type="meeting",
        external_id=payload.external_id,
        title=payload.title,
        raw_content=payload.raw_content,
        summary=payload.summary,
        suggested_actions_json=actions_json,
        status="new",
        created_at=payload.source_created_at or datetime.utcnow(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return JSONResponse({"status": "ok", "id": item.id, "title": item.title}, status_code=201)


@app.post(f"{BASE}/inbox/{{item_id}}/promote-task")
def inbox_promote_task(
    item_id: int,
    title: str = Form(...),
    description: str = Form(default=""),
    project_id: Optional[int] = Form(default=None),
    db: Session = Depends(get_db),
):
    item = db.query(models.InboxItem).filter(models.InboxItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    task = models.Task(
        title=title,
        description=description or None,
        project_id=project_id or None,
        source_type="inbox",
        source_ref=f"inbox:{item_id}",
        focus_state="later",
        status="todo",
    )
    db.add(task)
    db.flush()
    item.status = "promoted"
    item.linked_task_id = task.id
    item.reviewed_at = item.reviewed_at or datetime.utcnow()
    db.commit()
    return RedirectResponse(url=f"{BASE}/inbox/{item_id}", status_code=303)


@app.post(f"{BASE}/inbox/{{item_id}}/promote-project")
def inbox_promote_project(
    item_id: int,
    name: str = Form(...),
    description: str = Form(default=""),
    first_step: str = Form(default=""),
    db: Session = Depends(get_db),
):
    item = db.query(models.InboxItem).filter(models.InboxItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")

    # Build provenance line for description
    source_label = "Notion" if item.source == "notion" else item.source.capitalize()
    imported_str = datetime.utcnow().strftime("%b %d, %Y")
    provenance = f"[Imported from {source_label} on {imported_str}]"
    if item.linked_note_url:
        provenance += f"\n{item.linked_note_url}"
    full_desc = f"{provenance}\n\n{description}".strip() if description else provenance

    project = models.Project(
        name=name.strip(),
        description=full_desc,
        is_active=True,
    )
    db.add(project)
    db.flush()

    if first_step.strip():
        first_task = models.Task(
            title=first_step.strip(),
            project_id=project.id,
            source_type="inbox",
            source_ref=f"inbox:{item_id}",
            focus_state="later",
            status="todo",
        )
        db.add(first_task)

    item.status = "promoted"
    item.linked_project_id = project.id
    item.reviewed_at = item.reviewed_at or datetime.utcnow()
    db.commit()
    return RedirectResponse(url=f"{BASE}/inbox/{item_id}", status_code=303)


@app.post(f"{BASE}/inbox/{{item_id}}/promote-note")
def inbox_promote_note(
    item_id: int,
    title: str = Form(...),
    include_raw: str = Form(default="on"),
    db: Session = Depends(get_db),
):
    item = db.query(models.InboxItem).filter(models.InboxItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")

    content = item.raw_content if include_raw == "on" else None
    note = models.NoteItem(
        title=title.strip() or item.title,
        content=content,
        summary=item.summary,
        source=item.source,
        external_id=item.external_id,
        external_url=item.linked_note_url,
        linked_inbox_id=item.id,
        imported_at=datetime.utcnow(),
    )
    db.add(note)
    db.flush()

    item.status = "promoted"
    item.linked_note_id = note.id
    item.reviewed_at = item.reviewed_at or datetime.utcnow()
    db.commit()
    return RedirectResponse(url=f"{BASE}/inbox/{item_id}", status_code=303)


@app.post(f"{BASE}/inbox/{{item_id}}/archive")
def inbox_archive(item_id: int, db: Session = Depends(get_db)):
    item = db.query(models.InboxItem).filter(models.InboxItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    item.status = "archived"
    item.reviewed_at = item.reviewed_at or datetime.utcnow()
    db.commit()
    return RedirectResponse(url=f"{BASE}/inbox", status_code=303)


@app.post(f"{BASE}/inbox/{{item_id}}/delete")
def inbox_delete(item_id: int, db: Session = Depends(get_db)):
    item = db.query(models.InboxItem).filter(models.InboxItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    db.delete(item)
    db.commit()
    return RedirectResponse(url=f"{BASE}/inbox", status_code=303)


# ─── Notes (NoteItem) ─────────────────────────────────────────────────────────

@app.get(f"{BASE}/notes", response_class=HTMLResponse)
def notes_list(request: Request, db: Session = Depends(get_db)):
    notes = (
        db.query(models.NoteItem)
        .order_by(models.NoteItem.created_at.desc())
        .all()
    )
    export_targets = db.query(models.NotionExportTarget).order_by(models.NotionExportTarget.created_at).all()
    return templates.TemplateResponse(
        request, "notes.html",
        {"base": BASE, "notes": notes, "export_targets": export_targets, "is_notion_configured": notion.is_configured()},
    )


@app.get(f"{BASE}/notes/{{note_id}}", response_class=HTMLResponse)
def note_detail(note_id: int, request: Request, db: Session = Depends(get_db)):
    note = db.query(models.NoteItem).filter(models.NoteItem.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    inbox_item = None
    if note.linked_inbox_id:
        inbox_item = db.query(models.InboxItem).filter(models.InboxItem.id == note.linked_inbox_id).first()
    export_targets = db.query(models.NotionExportTarget).order_by(models.NotionExportTarget.is_default.desc()).all()
    return templates.TemplateResponse(
        request, "note_detail.html",
        {
            "base": BASE,
            "note": note,
            "inbox_item": inbox_item,
            "export_targets": export_targets,
            "is_notion_configured": notion.is_configured(),
            "exported": note.notion_url is not None,
        },
    )


@app.post(f"{BASE}/notes/{{note_id}}/export-to-notion")
def note_export_to_notion(
    note_id: int,
    target_id: int = Form(...),
    db: Session = Depends(get_db),
):
    if not notion.is_configured():
        raise HTTPException(status_code=503, detail="Notion not configured")
    note = db.query(models.NoteItem).filter(models.NoteItem.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    target = db.query(models.NotionExportTarget).filter(models.NotionExportTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Export target not found")
    try:
        page = notion.export_note(note, target.notion_id, target.target_type)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    note.notion_page_id = page["id"].replace("-", "")
    note.notion_url = page.get("url") or f"https://notion.so/{page['id'].replace('-', '')}"
    note.exported_at = datetime.utcnow()
    note.last_synced_at = datetime.utcnow()
    db.commit()
    return RedirectResponse(url=f"{BASE}/notes/{note_id}?exported=1", status_code=303)


# ─── Project detail + Notion export ──────────────────────────────────────────

@app.get(f"{BASE}/projects/{{project_id}}", response_class=HTMLResponse)
def project_detail(project_id: int, request: Request, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    tasks = (
        db.query(models.Task)
        .filter(models.Task.project_id == project_id, models.Task.status != "done")
        .order_by(models.Task.created_at)
        .all()
    )
    first_next_task = next(
        (t for t in tasks if t.focus_state in ("now", "next", "later")), None
    )
    export_targets = db.query(models.NotionExportTarget).order_by(models.NotionExportTarget.is_default.desc()).all()
    return templates.TemplateResponse(
        request, "project_detail.html",
        {
            "base": BASE,
            "project": project,
            "tasks": tasks,
            "first_next_task": first_next_task,
            "export_targets": export_targets,
            "is_notion_configured": notion.is_configured(),
            "exported": project.notion_url is not None,
        },
    )


@app.post(f"{BASE}/projects/{{project_id}}/export-to-notion")
def project_export_to_notion(
    project_id: int,
    target_id: int = Form(...),
    db: Session = Depends(get_db),
):
    if not notion.is_configured():
        raise HTTPException(status_code=503, detail="Notion not configured")
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    target = db.query(models.NotionExportTarget).filter(models.NotionExportTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Export target not found")
    # Find the first non-done task to include as a next step
    first_task = (
        db.query(models.Task)
        .filter(models.Task.project_id == project_id, models.Task.status != "done")
        .order_by(models.Task.created_at)
        .first()
    )
    first_task_title = first_task.title if first_task else None
    try:
        page = notion.export_project(project, first_task_title, target.notion_id, target.target_type)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    project.notion_page_id = page["id"].replace("-", "")
    project.notion_url = page.get("url") or f"https://notion.so/{page['id'].replace('-', '')}"
    project.exported_at = datetime.utcnow()
    project.last_synced_at = datetime.utcnow()
    db.commit()
    return RedirectResponse(url=f"{BASE}/projects/{project_id}?exported=1", status_code=303)


# ─── Notion export targets ────────────────────────────────────────────────────

@app.post(f"{BASE}/integrations/notion/export-targets")
def notion_add_export_target(
    name: str = Form(...),
    notion_id: str = Form(...),
    target_type: str = Form(default="page"),
    is_default: str = Form(default=""),
    db: Session = Depends(get_db),
):
    clean_id = notion_id.strip().replace("-", "")
    if not clean_id:
        raise HTTPException(status_code=422, detail="Notion ID is required")
    make_default = bool(is_default)
    if make_default:
        # clear existing defaults
        db.query(models.NotionExportTarget).update({"is_default": False})
    target = models.NotionExportTarget(
        name=name.strip(),
        notion_id=clean_id,
        target_type=target_type,
        is_default=make_default,
    )
    db.add(target)
    db.commit()
    return RedirectResponse(url=f"{BASE}/integrations/notion#export-targets", status_code=303)


@app.post(f"{BASE}/integrations/notion/export-targets/{{target_id}}/delete")
def notion_delete_export_target(target_id: int, db: Session = Depends(get_db)):
    t = db.query(models.NotionExportTarget).filter(models.NotionExportTarget.id == target_id).first()
    if t:
        db.delete(t)
        db.commit()
    return RedirectResponse(url=f"{BASE}/integrations/notion#export-targets", status_code=303)


@app.post(f"{BASE}/integrations/notion/export-targets/{{target_id}}/set-default")
def notion_set_default_export_target(target_id: int, db: Session = Depends(get_db)):
    db.query(models.NotionExportTarget).update({"is_default": False})
    t = db.query(models.NotionExportTarget).filter(models.NotionExportTarget.id == target_id).first()
    if t:
        t.is_default = True
        db.commit()
    return RedirectResponse(url=f"{BASE}/integrations/notion#export-targets", status_code=303)


# ─── Notion integration settings ─────────────────────────────────────────────

@app.get(f"{BASE}/integrations/notion", response_class=HTMLResponse)
def notion_settings(
    request: Request,
    imported: Optional[int] = Query(default=None),
    skipped: Optional[int] = Query(default=None),
    errors: Optional[int] = Query(default=None),
    error_msg: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    sources = (
        db.query(models.NotionSource)
        .order_by(models.NotionSource.created_at.asc())
        .all()
    )
    inbox_count = db.query(models.InboxItem).filter(models.InboxItem.source == "notion").count()
    last_result = None
    if imported is not None or skipped is not None or errors is not None:
        last_result = {
            "imported": imported or 0,
            "skipped": skipped or 0,
            "errors": errors or 0,
            "error_msg": error_msg,
        }
    export_targets = (
        db.query(models.NotionExportTarget)
        .order_by(models.NotionExportTarget.is_default.desc(), models.NotionExportTarget.created_at)
        .all()
    )
    return templates.TemplateResponse(
        request, "integrations_notion.html",
        {
            "base": BASE,
            "sources": sources,
            "is_configured": notion.is_configured(),
            "inbox_count": inbox_count,
            "last_result": last_result,
            "export_targets": export_targets,
        },
    )


@app.post(f"{BASE}/integrations/notion/sources")
def notion_add_source(
    name: str = Form(...),
    source_type: str = Form(default="page"),
    notion_id: str = Form(...),
    import_mode: str = Form(default="inbox"),
    db: Session = Depends(get_db),
):
    clean_id = notion_id.strip().replace("-", "")
    if not clean_id:
        raise HTTPException(status_code=422, detail="Notion ID is required")
    existing = db.query(models.NotionSource).filter(
        models.NotionSource.notion_id == clean_id
    ).first()
    if not existing:
        source = models.NotionSource(
            name=name.strip(),
            source_type=source_type,
            notion_id=clean_id,
            import_mode=import_mode,
            is_active=True,
        )
        db.add(source)
        db.commit()
    return RedirectResponse(url=f"{BASE}/integrations/notion", status_code=303)


@app.post(f"{BASE}/integrations/notion/sources/{{source_id}}/delete")
def notion_delete_source(source_id: int, db: Session = Depends(get_db)):
    src = db.query(models.NotionSource).filter(models.NotionSource.id == source_id).first()
    if src:
        db.delete(src)
        db.commit()
    return RedirectResponse(url=f"{BASE}/integrations/notion", status_code=303)


@app.post(f"{BASE}/integrations/notion/import")
def notion_import(
    source_id: Optional[int] = Form(default=None),
    db: Session = Depends(get_db),
):
    """
    Fetch Notion content and create InboxItems for each new record.
    Deduplicates by (source='notion', external_id).
    Can import a single source or all active sources.
    """
    if not notion.is_configured():
        return RedirectResponse(
            url=f"{BASE}/integrations/notion?error_msg=NOTION_API_TOKEN+not+configured",
            status_code=303,
        )

    if source_id:
        sources = db.query(models.NotionSource).filter(
            models.NotionSource.id == source_id,
            models.NotionSource.is_active == True,
        ).all()
    else:
        sources = db.query(models.NotionSource).filter(
            models.NotionSource.is_active == True
        ).all()

    total_imported = 0
    total_skipped = 0
    total_errors = 0
    first_error = None

    for src in sources:
        try:
            if src.source_type == "database":
                normalized_items = notion.import_database_entries(src.notion_id)
            else:
                normalized_items = [notion.import_page(src.notion_id)]
        except Exception as exc:
            total_errors += 1
            if not first_error:
                first_error = str(exc)[:200]
            continue

        for item_data in normalized_items:
            ext_id = item_data.get("external_id", "")
            duplicate = db.query(models.InboxItem).filter(
                models.InboxItem.source == "notion",
                models.InboxItem.external_id == ext_id,
            ).first()
            if duplicate:
                total_skipped += 1
                continue
            inbox_item = models.InboxItem(**item_data)
            db.add(inbox_item)
            total_imported += 1

        src.last_imported_at = datetime.utcnow()

    db.commit()

    params = f"imported={total_imported}&skipped={total_skipped}&errors={total_errors}"
    if first_error:
        import urllib.parse
        params += f"&error_msg={urllib.parse.quote(first_error)}"
    return RedirectResponse(url=f"{BASE}/integrations/notion?{params}", status_code=303)


# ─── Assistant chat (Phase 0: local conversational brain) ─────────────────────

from pydantic import BaseModel as _BaseModel


class ChatSendBody(_BaseModel):
    message: str
    conversation_id: Optional[int] = None


@app.get(f"{BASE}/chat/status")
def chat_status():
    """Tell the frontend whether the assistant is usable."""
    return {"configured": agent.is_configured(), "model": agent.MODEL}


@app.get(f"{BASE}/chat/conversations")
def chat_conversations(db: Session = Depends(get_db)):
    convos = (
        db.query(models.Conversation)
        .order_by(models.Conversation.updated_at.desc())
        .limit(30)
        .all()
    )
    return {
        "conversations": [
            {"id": c.id, "title": c.title or "Sin título", "updated_at": c.updated_at.isoformat() if c.updated_at else None}
            for c in convos
        ]
    }


@app.get(f"{BASE}/chat/history")
def chat_history(conversation_id: int = Query(...), db: Session = Depends(get_db)):
    convo = db.query(models.Conversation).filter(models.Conversation.id == conversation_id).first()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {
        "conversation_id": convo.id,
        "title": convo.title,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "tool_trace": json.loads(m.tool_trace) if m.tool_trace else [],
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in convo.messages
        ],
    }


@app.post(f"{BASE}/chat/send")
def chat_send(body: ChatSendBody, db: Session = Depends(get_db)):
    text = (body.message or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="message required")

    convo = None
    if body.conversation_id:
        convo = db.query(models.Conversation).filter(
            models.Conversation.id == body.conversation_id
        ).first()
    if not convo:
        convo = models.Conversation()
        db.add(convo)
        db.commit()
        db.refresh(convo)

    def event_stream():
        # Announce the conversation id first so the client can track it.
        yield f"data: {json.dumps({'type': 'meta', 'conversation_id': convo.id})}\n\n"
        yield from agent.run_agent_stream(db, convo, text)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ─── Phase 1: AI day planner ──────────────────────────────────────────────────

class ApplyPlanBody(_BaseModel):
    assignments: List[dict]


@app.post(f"{BASE}/my-day/plan")
def my_day_plan(db: Session = Depends(get_db)):
    """Compute an AI day plan (does not apply it)."""
    plan = agent.compute_day_plan(db)
    if "error" in plan:
        raise HTTPException(status_code=503, detail=plan["error"])
    return plan


@app.post(f"{BASE}/my-day/plan/apply")
def my_day_plan_apply(body: ApplyPlanBody, db: Session = Depends(get_db)):
    """Apply a previously computed plan's assignments."""
    return agent.apply_day_plan(db, body.assignments)


# ─── Phase 3: Proactive briefing ──────────────────────────────────────────────

@app.get(f"{BASE}/my-day/briefing")
def my_day_briefing(db: Session = Depends(get_db)):
    """Today's cached briefing (generated on first call of the day)."""
    result = agent.get_or_create_briefing(db)
    if "error" in result:
        raise HTTPException(status_code=503, detail=result["error"])
    return result


@app.post(f"{BASE}/my-day/briefing/refresh")
def my_day_briefing_refresh(db: Session = Depends(get_db)):
    result = agent.get_or_create_briefing(db, force=True)
    if "error" in result:
        raise HTTPException(status_code=503, detail=result["error"])
    return result


# ─── Command Center (single home + launch hub for the 3 apps) ─────────────────
import socket as _socket

# Sibling apps in Paul's daily workflow (started by START-MyDay.bat).
SIBLING_APPS = {
    "transcribe":  {"host": "127.0.0.1", "port": 8088, "url": "http://localhost:8088"},
    "timetracker": {"host": "127.0.0.1", "port": 8787, "url": "http://localhost:8787"},
}


def _port_open(host: str, port: int, timeout: float = 0.35) -> bool:
    """True if something is listening on host:port (used for live/down dots)."""
    try:
        with _socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@app.get(f"{BASE}/command-center", response_class=HTMLResponse)
async def command_center(request: Request, db: Session = Depends(get_db)):
    today = date.today()
    daily_log = db.query(models.DailyLog).filter(models.DailyLog.date == today).first()
    inbox_unreviewed = (
        db.query(models.InboxItem)
        .filter(models.InboxItem.status.in_(["new", "reviewing"]))
        .count()
    )
    response = templates.TemplateResponse(
        request, "command_center.html",
        {
            "base": BASE,
            "today": today,
            "energy_today": daily_log.energy_today if daily_log else None,
            "inbox_unreviewed": inbox_unreviewed,
            "transcribe_url": SIBLING_APPS["transcribe"]["url"],
            "timetracker_url": SIBLING_APPS["timetracker"]["url"],
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get(f"{BASE}/command-center/status")
def command_center_status():
    """Live/down status of the three workflow apps. MyDay is up by definition."""
    return {
        "myday": True,
        "transcribe": _port_open(**{k: SIBLING_APPS["transcribe"][k] for k in ("host", "port")}),
        "timetracker": _port_open(**{k: SIBLING_APPS["timetracker"][k] for k in ("host", "port")}),
    }


# ─── Morning ritual folded into My Day (energy + brain dump) ───────────────────

class EnergyBody(_BaseModel):
    energy: str  # high | flow | low | scattered


class BrainDumpBody(_BaseModel):
    text: str


@app.post(f"{BASE}/my-day/energy")
def my_day_set_energy(body: EnergyBody, db: Session = Depends(get_db)):
    energy = (body.energy or "").strip()
    if energy not in ("high", "flow", "low", "scattered"):
        raise HTTPException(status_code=422, detail="invalid energy")
    today = date.today()
    log = get_or_create_daily_log(db, today)
    log.energy_today = energy
    db.commit()
    mark_morning_checkin(db, today)  # marks started + checkin (streak + ritual)
    return {"ok": True, "energy": energy}


@app.post(f"{BASE}/my-day/brain-dump")
def my_day_brain_dump(body: BrainDumpBody, db: Session = Depends(get_db)):
    lines = [l.strip() for l in (body.text or "").splitlines() if l.strip()]
    for line in lines:
        db.add(models.InboxItem(
            title=line, source="self", source_type="brain_dump",
            status="new", suggested_actions_json="[]",
        ))
    db.commit()
    if lines:
        mark_morning_checkin(db, date.today())
    return {"ok": True, "added": len(lines)}


# ─── Phase 2: Microsoft 365 integration ───────────────────────────────────────

@app.get(f"{BASE}/integrations/microsoft", response_class=HTMLResponse)
def microsoft_settings(
    request: Request,
    imported: Optional[int] = Query(default=None),
    skipped: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    email_count = db.query(models.InboxItem).filter(models.InboxItem.source == "ms_email").count()
    last_result = None
    if imported is not None or skipped is not None:
        last_result = {"imported": imported or 0, "skipped": skipped or 0}
    return templates.TemplateResponse(
        request, "integrations_microsoft.html",
        {
            "base": BASE,
            "status": ms_graph.flow_status(),
            "tenant": ms_graph.tenant(),
            "email_count": email_count,
            "last_result": last_result,
            "scopes": " ".join(ms_graph.SCOPES),
            "mail_enabled": ms_graph.mail_enabled(),
        },
    )


@app.post(f"{BASE}/integrations/microsoft/connect")
def microsoft_connect():
    """Start the device-code flow; returns the code + link for the user."""
    return ms_graph.start_device_flow()


@app.get(f"{BASE}/integrations/microsoft/status")
def microsoft_status():
    return ms_graph.flow_status()


@app.post(f"{BASE}/integrations/microsoft/sync-email")
def microsoft_sync_email(db: Session = Depends(get_db)):
    result = agent.sync_ms_email(db, limit=40)
    if "error" in result:
        raise HTTPException(status_code=503, detail=result["error"])
    return RedirectResponse(
        url=f"{BASE}/integrations/microsoft?imported={result['imported']}&skipped={result['skipped']}",
        status_code=303,
    )


@app.post(f"{BASE}/integrations/microsoft/disconnect")
def microsoft_disconnect():
    ms_graph.disconnect()
    return RedirectResponse(url=f"{BASE}/integrations/microsoft", status_code=303)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
