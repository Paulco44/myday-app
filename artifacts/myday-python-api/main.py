import os
from contextlib import asynccontextmanager
from datetime import datetime, date, time as dtime
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


def ensure_settings(db: Session):
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

    suggestions = (
        db.query(models.Task)
        .filter(
            models.Task.is_today == False,
            models.Task.status != "done",
            or_(
                models.Task.due_date <= today,
                models.Task.priority == "high",
            ),
        )
        .order_by(models.Task.due_date.asc().nullslast(), models.Task.priority.desc())
        .all()
    )

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

    return templates.TemplateResponse(
        request, "my_day.html",
        {
            "today_tasks": today_tasks,
            "suggestions": suggestions,
            "overdue_count": overdue_count,
            "completed_today": completed_today,
            "today": today,
            "base": BASE,
        },
    )


@app.post(f"{BASE}/tasks/{{task_id}}/set-today")
async def set_today(task_id: int, db: Session = Depends(get_db)):
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if db_task:
        db_task.is_today = True
        db_task.updated_at = datetime.utcnow()
        db.commit()
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


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
