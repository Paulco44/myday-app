"""Billing codes catalog (MyDay↔TimeTracker bridge).

Imports the V2A coding catalog (Client CC1 → Project CC2 → Task CC3, with the
valid Client↔Project and Project→Task pairings) from a JSON seed produced from
the "Time and attendance" workbooks, and offers cascade lookups for the planner.

Re-runnable: when the complete DB arrives, regenerate billing_catalog_seed.json
and POST /task-manager/billing/import to refresh.
"""
import os
import json
from typing import Optional

import models

SEED_PATH = os.path.join(os.path.dirname(__file__), "billing_catalog_seed.json")


# ─── Import ───────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    return (s or "").strip()


def _upsert(db, Model, name: str, code: str):
    """Get-or-create by (case-insensitive) name; fill code if we have a better one."""
    name = _norm(name)
    if not name:
        return None
    row = (
        db.query(Model)
        .filter(Model.name.ilike(name))
        .first()
    )
    if row is None:
        row = Model(name=name, code=_norm(code) or None, is_active=True)
        db.add(row)
        db.flush()
    elif _norm(code) and not _norm(row.code or ""):
        row.code = _norm(code)
    return row


def import_catalog(db, path: Optional[str] = None) -> dict:
    """Upsert clients/projects/tasks + valid pairings from the JSON seed."""
    path = path or SEED_PATH
    if not os.path.exists(path):
        return {"error": f"seed not found: {path}"}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    clients, projects, tasks = {}, {}, {}
    for c in data.get("clients", []):
        r = _upsert(db, models.BillingClient, c["name"], c.get("code"))
        if r: clients[_norm(c["name"]).lower()] = r
    for p in data.get("projects", []):
        r = _upsert(db, models.BillingProject, p["name"], p.get("code"))
        if r: projects[_norm(p["name"]).lower()] = r
    for t in data.get("tasks", []):
        r = _upsert(db, models.BillingTask, t["name"], t.get("code"))
        if r: tasks[_norm(t["name"]).lower()] = r
    db.flush()

    cp_added = pt_added = 0
    for cname, pname in data.get("client_project", []):
        c, p = clients.get(_norm(cname).lower()), projects.get(_norm(pname).lower())
        if not (c and p):
            continue
        exists = db.query(models.BillingClientProject).filter_by(
            client_id=c.id, project_id=p.id).first()
        if not exists:
            db.add(models.BillingClientProject(client_id=c.id, project_id=p.id))
            cp_added += 1
    for pname, tname in data.get("project_task", []):
        p, t = projects.get(_norm(pname).lower()), tasks.get(_norm(tname).lower())
        if not (p and t):
            continue
        exists = db.query(models.BillingProjectTask).filter_by(
            project_id=p.id, task_id=t.id).first()
        if not exists:
            db.add(models.BillingProjectTask(project_id=p.id, task_id=t.id))
            pt_added += 1

    db.commit()
    return {
        "clients": len(clients), "projects": len(projects), "tasks": len(tasks),
        "client_project_added": cp_added, "project_task_added": pt_added,
        "source": data.get("source"),
    }


def seed_if_empty(db) -> None:
    """Import the seed on first run (no clients yet)."""
    if db.query(models.BillingClient).count() == 0 and os.path.exists(SEED_PATH):
        try:
            import_catalog(db)
        except Exception:
            db.rollback()


# ─── Cascade lookups (for the planner UI) ─────────────────────────────────────

def list_clients(db):
    return db.query(models.BillingClient).filter(
        models.BillingClient.is_active == True).order_by(models.BillingClient.name).all()


def projects_for_client(db, client_id: int):
    return (
        db.query(models.BillingProject)
        .join(models.BillingClientProject,
              models.BillingClientProject.project_id == models.BillingProject.id)
        .filter(models.BillingClientProject.client_id == client_id,
                models.BillingProject.is_active == True)
        .order_by(models.BillingProject.name)
        .all()
    )


def tasks_for_project(db, project_id: int):
    return (
        db.query(models.BillingTask)
        .join(models.BillingProjectTask,
              models.BillingProjectTask.task_id == models.BillingTask.id)
        .filter(models.BillingProjectTask.project_id == project_id,
                models.BillingTask.is_active == True)
        .order_by(models.BillingTask.name)
        .all()
    )
