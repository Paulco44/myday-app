import os
from contextlib import asynccontextmanager
from datetime import datetime, date, timedelta
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import or_
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

import models
import schemas
from database import engine, get_db, Base, SessionLocal

BASE = "/task-manager"
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

STATUSES = ["backlog", "todo", "doing", "waiting", "done"]
STATUS_LABELS = {"backlog": "Backlog", "todo": "To Do", "doing": "Doing", "waiting": "Waiting", "done": "Done"}

MUST_DO_CAP = 5

# Month number → active_<month> attribute name
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


def mark_today_completed(db: Session, for_date: date) -> None:
    log = get_or_create_daily_log(db, for_date)
    if not log.has_completed_task:
        log.has_completed_task = True
        db.commit()


def compute_streak(db: Session) -> int:
    """Count consecutive days (ending today or yesterday) with started or has_completed_task."""
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


def build_suggestions(db: Session, today: date) -> list:
    """Return suggestions ordered: overdue → due today → high-priority no-date."""
    base_filter = [models.Task.is_today == False, models.Task.status != "done"]

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

    seen: set = set()
    result = []
    for task in overdue + due_today + high_no_date:
        if task.id not in seen:
            seen.add(task.id)
            result.append(task)
    return result


def get_cop_initiatives_this_month(db: Session, leader_name: str = "Paul") -> list:
    """Return CoP initiatives active this month where leader contains leader_name."""
    month_num = date.today().month
    field_name = MONTH_FIELD[month_num]
    month_col = getattr(models.CoPInitiative, field_name)
    return (
        db.query(models.CoPInitiative)
        .filter(
            month_col == True,
            models.CoPInitiative.leader.ilike(f"%{leader_name}%"),
        )
        .order_by(models.CoPInitiative.topic, models.CoPInitiative.topic_description)
        .all()
    )


@asynccontextmanager
async def lifespan(app):
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_settings(db)
    finally:
        db.close()
    yield


app = FastAPI(title="MyDay Task Manager", lifespan=lifespan)
templates = Jinja2Templates(directory=TEMPLATES_DIR)


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


# ─── My Day ──────────────────────────────────────────────────────────────────

@app.get(f"{BASE}/my-day", response_class=HTMLResponse)
async def my_day(request: Request, db: Session = Depends(get_db)):
    today = date.today()
    today_start = datetime(today.year, today.month, today.day)

    today_tasks = (
        db.query(models.Task)
        .filter(models.Task.is_today == True)
        .order_by(models.Task.status, models.Task.priority.desc())
        .all()
    )

    must_do_active = [t for t in today_tasks if t.status != "done"]
    must_do_active_count = len(must_do_active)

    suggestions = build_suggestions(db, today)

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
    streak = compute_streak(db)

    cop_initiatives = get_cop_initiatives_this_month(db, "Paul")
    current_month_name = MONTH_NAMES[today.month]

    return templates.TemplateResponse(
        request, "my_day.html",
        {
            "today_tasks": today_tasks,
            "must_do_active_count": must_do_active_count,
            "suggestions": suggestions,
            "overdue_count": overdue_count,
            "completed_today": completed_today,
            "today_started": today_started,
            "streak": streak,
            "must_do_cap": MUST_DO_CAP,
            "today": today,
            "base": BASE,
            "cop_initiatives": cop_initiatives,
            "current_month_name": current_month_name,
        },
    )


@app.post(f"{BASE}/my-day/start-today")
async def start_today(db: Session = Depends(get_db)):
    mark_today_started(db, date.today())
    return RedirectResponse(url=f"{BASE}/my-day", status_code=303)


@app.post(f"{BASE}/tasks/{{task_id}}/set-today")
async def set_today(task_id: int, db: Session = Depends(get_db)):
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if db_task:
        db_task.is_today = True
        db_task.updated_at = datetime.utcnow()
        db.commit()
        mark_today_started(db, date.today())
    return RedirectResponse(url=f"{BASE}/my-day", status_code=303)


@app.post(f"{BASE}/tasks/{{task_id}}/unset-today")
async def unset_today(task_id: int, db: Session = Depends(get_db)):
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if db_task:
        db_task.is_today = False
        db_task.updated_at = datetime.utcnow()
        db.commit()
    return RedirectResponse(url=f"{BASE}/my-day", status_code=303)


# ─── Kanban ──────────────────────────────────────────────────────────────────

@app.get(f"{BASE}/kanban", response_class=HTMLResponse)
async def kanban(request: Request, db: Session = Depends(get_db)):
    today = date.today()
    columns = {
        s: db.query(models.Task).filter(models.Task.status == s)
              .order_by(models.Task.priority.desc())
              .all()
        for s in STATUSES
    }
    settings = ensure_settings(db)
    return templates.TemplateResponse(
        request, "kanban.html",
        {
            "columns": columns,
            "statuses": STATUSES,
            "status_labels": STATUS_LABELS,
            "wip_limit": settings.wip_limit_doing,
            "today": today,
            "base": BASE,
        },
    )


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
        if status == "done" and not db_task.completed_at:
            db_task.completed_at = datetime.utcnow()
            mark_today_completed(db, date.today())
        elif status != "done":
            db_task.completed_at = None
        db.commit()
    dest = redirect_to if redirect_to else f"{BASE}/kanban"
    return RedirectResponse(url=dest, status_code=303)


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
    db: Session = Depends(get_db),
):
    parsed_due: Optional[date] = None
    if due_date:
        try:
            parsed_due = date.fromisoformat(due_date)
        except ValueError:
            pass

    pid = int(project_id) if project_id and project_id.strip() else None
    task = models.Task(title=title, priority=priority, due_date=parsed_due, status=status, project_id=pid)
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
        effort=effort or None,
        topic=topic or None,
        topic_description=topic_description or None,
        subtopic=subtopic or None,
        type_of_effort=type_of_effort or None,
        focus_market=focus_market or None,
        leader=leader or None,
        cop_collaboration=cop_collaboration or None,
        notes=notes or None,
        active_jan=to_bool(active_jan),
        active_feb=to_bool(active_feb),
        active_mar=to_bool(active_mar),
        active_apr=to_bool(active_apr),
        active_may=to_bool(active_may),
        active_jun=to_bool(active_jun),
        active_jul=to_bool(active_jul),
        active_aug=to_bool(active_aug),
        active_sep=to_bool(active_sep),
        active_oct=to_bool(active_oct),
        active_nov=to_bool(active_nov),
        active_dec=to_bool(active_dec),
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
    db: Session = Depends(get_db),
):
    query = db.query(models.Task)
    if status:
        query = query.filter(models.Task.status == status)
    if project_id is not None:
        query = query.filter(models.Task.project_id == project_id)
    if is_today is not None:
        query = query.filter(models.Task.is_today == is_today)
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


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
