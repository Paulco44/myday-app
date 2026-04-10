import json
import os
import pathlib
from contextlib import asynccontextmanager
from datetime import datetime, date, timedelta
from typing import Optional, List

import notion_client as notion

from fastapi import FastAPI, Depends, HTTPException, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import or_, text as sa_text
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

import models
import schemas
from database import engine, get_db, Base, SessionLocal

BASE = "/task-manager"
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

STATUSES = ["backlog", "todo", "doing", "waiting", "done"]
STATUS_LABELS = {"backlog": "Backlog", "todo": "To Do", "doing": "Doing", "waiting": "Waiting", "done": "Done"}

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

def build_suggestions(db: Session, today: date, exclude_ids: set, energy_today: Optional[str] = None) -> list:
    base_filter = [
        models.Task.is_today == False,
        models.Task.status != "done",
        models.Task.focus_state != "later",
    ]
    overdue = (
        db.query(models.Task)
        .filter(*base_filter, models.Task.due_date < today)
        .order_by(models.Task.due_date.asc())
        .all()
    )
    due_today = (
        db.query(models.Task)
        .filter(*base_filter, models.Task.due_date == today)
        .all()
    )
    high_no_date = (
        db.query(models.Task)
        .filter(*base_filter, models.Task.priority == "high", models.Task.due_date == None)
        .all()
    )
    seen: set = set(exclude_ids)
    all_tasks = []
    for task in overdue + due_today + high_no_date:
        if task.id not in seen:
            seen.add(task.id)
            all_tasks.append(task)

    # Boost energy-matching tasks to the top when energy_today is known
    if energy_today and energy_today in ENERGY_TO_TAG:
        matched_tag = ENERGY_TO_TAG[energy_today]
        matched = [t for t in all_tasks if t.energy_tag == matched_tag]
        rest    = [t for t in all_tasks if t.energy_tag != matched_tag]
        all_tasks = matched + rest

    return all_tasks[:SUGGESTIONS_CAP]


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

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount(f"{BASE}/static", StaticFiles(directory=STATIC_DIR), name="static")


# ─── Health ──────────────────────────────────────────────────────────────────

@app.get(f"{BASE}/healthz")
def health():
    return {"status": "ok"}


# ─── Home ─────────────────────────────────────────────────────────────────────

@app.get(f"{BASE}", response_class=HTMLResponse)
@app.get(f"{BASE}/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    projects = db.query(models.Project).all()
    total_tasks = db.query(models.Task).count()
    today_count = db.query(models.Task).filter(models.Task.is_today == True).count()
    doing_count = db.query(models.Task).filter(models.Task.status == "doing").count()
    return templates.TemplateResponse(
        request, "index.html",
        {"projects": projects, "base": BASE, "total_tasks": total_tasks,
         "today_count": today_count, "doing_count": doing_count},
    )


# ─── Morning Check-In ────────────────────────────────────────────────────────

@app.get(f"{BASE}/morning-checkin", response_class=HTMLResponse)
async def morning_checkin_get(request: Request, db: Session = Depends(get_db)):
    tasks = (
        db.query(models.Task)
        .filter(models.Task.status.in_(["todo", "backlog"]))
        .order_by(models.Task.priority.desc(), models.Task.due_date.asc())
        .all()
    )
    return templates.TemplateResponse(
        request, "morning_checkin.html",
        {"base": BASE, "tasks": tasks},
    )


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

    return templates.TemplateResponse(
        request, "my_day.html",
        {
            "wins_tasks": wins_tasks,
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
            "energy_today": energy_today,
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
    now_hour = datetime.now().hour  # 0–23 local server hour

    # All today_flag tasks
    flagged_all = (
        db.query(models.Task)
        .filter(models.Task.today_flag == True)
        .order_by(models.Task.today_category, models.Task.priority.desc())
        .all()
    )
    wins_done       = [t for t in flagged_all if t.today_category == "win"  and t.status == "done"]
    wins_incomplete = [t for t in flagged_all if t.today_category == "win"  and t.status != "done"]
    nice_done       = [t for t in flagged_all if t.today_category == "nice" and t.status == "done"]
    nice_incomplete = [t for t in flagged_all if t.today_category == "nice" and t.status != "done"]

    daily_log = db.query(models.DailyLog).filter(models.DailyLog.date == today).first()
    already_closed = daily_log.day_closed if daily_log else False

    total_wins    = len(wins_done) + len(wins_incomplete)
    score_pct     = int(len(wins_done) / total_wins * 100) if total_wins else 0

    return templates.TemplateResponse(request, "close_day.html", {
        "wins_done":       wins_done,
        "wins_incomplete": wins_incomplete,
        "nice_done":       nice_done,
        "nice_incomplete": nice_incomplete,
        "already_closed":  already_closed,
        "now_hour":        now_hour,
        "score_pct":       score_pct,
        "base": BASE,
    })


@app.post(f"{BASE}/close-day")
async def close_day_post(request: Request, db: Session = Depends(get_db)):
    today = date.today()
    form  = await request.form()

    # Process each incomplete task's action choice
    flagged_all = db.query(models.Task).filter(models.Task.today_flag == True).all()
    for task in flagged_all:
        if task.status == "done":
            # Completed tasks: just clear flags
            task.today_flag     = False
            task.today_category = None
            continue

        action = form.get(f"action_{task.id}", "rollover")
        if action == "backlog":
            task.status         = "todo"
            task.is_today       = False
            task.today_flag     = False
            task.today_category = None
        else:  # rollover
            task.is_today       = True
            task.today_flag     = False
            task.today_category = None

    # Mark the day as closed in the daily log
    log = db.query(models.DailyLog).filter(models.DailyLog.date == today).first()
    if not log:
        log = models.DailyLog(date=today)
        db.add(log)
    log.day_closed = True
    db.commit()

    return RedirectResponse(url=f"{BASE}/my-day", status_code=303)


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
async def kanban(request: Request):
    """Deprecated — the React Kanban at / is the canonical board view."""
    return RedirectResponse(url="/", status_code=301)


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
    return templates.TemplateResponse(
        request, "tasks.html",
        {
            "tasks": tasks,
            "projects": projects,
            "base": BASE,
            "current_status": status,
            "current_project_id": project_id,
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
        db.delete(db_task)
        db.commit()
    return RedirectResponse(url=f"{BASE}/tasks-page", status_code=303)


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
    db: Session = Depends(get_db),
):
    task = models.Task(
        title=title,
        priority=priority,
        status="todo",
        energy_type=energy_type or None,
        time_estimate_minutes=time_estimate_minutes or None,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return JSONResponse({"status": "ok", "task_id": task.id, "title": task.title})


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
    db: Session = Depends(get_db),
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if task:
        task.updated_at = datetime.utcnow()
        mark_today_started(db, date.today())
        db.commit()
    return JSONResponse({
        "status": "ok",
        "task_id": task_id,
        "duration": duration_minutes,
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
    return templates.TemplateResponse(
        request, "inbox.html",
        {"base": BASE, "items": items, "archived_count": archived_count},
    )


@app.get(f"{BASE}/inbox/archived", response_class=HTMLResponse)
def inbox_archived(request: Request, db: Session = Depends(get_db)):
    items = (
        db.query(models.InboxItem)
        .filter(models.InboxItem.status == "archived")
        .order_by(models.InboxItem.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request, "inbox.html",
        {"base": BASE, "items": items, "archived_count": len(items), "show_archived": True},
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


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
