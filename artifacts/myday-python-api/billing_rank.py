"""Data-driven ranking of billing codes (Capa 2 of the MyDay↔Paylocity bridge).

Paylocity lets you pick any Client × Project × Task, but in practice only a
handful of combinations recur. This module reads TimeTracker's history
(READ-ONLY) and ranks the catalog options by how likely they are, so the
planner/task_edit can float the probable ones to the top ("Frecuentes") while
keeping the rest reachable ("Todos"). It never restricts: it only re-orders.

Signal:
  - marginal weighted frequency per client/project/task code
  - conditional co-occurrence: P(task | project), P(project | client)
  - recency weight (half-life ~120 days) so recent work counts more
Join key = the billing code (verified to match TimeTracker's codes).
"""
import os
import sqlite3
import time
from datetime import date
from typing import Optional

import models

TT_DB = os.environ.get("TIMETRACKER_DB", r"C:\TimeTracker\timetracker.db")
_HALF_LIFE_DAYS = 120.0
_CACHE_TTL = 60.0
_cache = {"ts": 0.0, "model": None}


def _recency_weight(work_date: str, today: date) -> float:
    try:
        y, m, d = map(int, (work_date or "")[:10].split("-"))
        age = (today - date(y, m, d)).days
        return max(0.2, 0.5 ** (age / _HALF_LIFE_DAYS))
    except Exception:
        return 1.0


def _build_model() -> dict:
    model = {
        "client": {}, "project": {}, "task": {},           # marginal weighted freq by code
        "proj_by_client": {}, "task_by_proj": {},          # conditional weighted freq
    }
    if not os.path.exists(TT_DB):
        return model
    try:
        con = sqlite3.connect(f"file:{TT_DB}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT work_date, client_code, project_code, task_code FROM time_entries"
        ).fetchall()
        con.close()
    except Exception:
        return model
    today = date.today()
    for r in rows:
        cc = (r["client_code"] or "").strip()
        pc = (r["project_code"] or "").strip()
        tc = (r["task_code"] or "").strip()
        w = _recency_weight(r["work_date"], today)
        if cc:
            model["client"][cc] = model["client"].get(cc, 0.0) + w
        if pc:
            model["project"][pc] = model["project"].get(pc, 0.0) + w
        if tc:
            model["task"][tc] = model["task"].get(tc, 0.0) + w
        if cc and pc:
            model["proj_by_client"].setdefault(cc, {})
            model["proj_by_client"][cc][pc] = model["proj_by_client"][cc].get(pc, 0.0) + w
        if pc and tc:
            model["task_by_proj"].setdefault(pc, {})
            model["task_by_proj"][pc][tc] = model["task_by_proj"][pc].get(tc, 0.0) + w
    return model


def get_model() -> dict:
    now = time.time()
    if _cache["model"] is None or now - _cache["ts"] > _CACHE_TTL:
        _cache["model"] = _build_model()
        _cache["ts"] = now
    return _cache["model"]


def _ranked(rows, score_of) -> list:
    """rows: ORM objects with .id/.name/.code → list of dicts sorted by score desc, name asc."""
    scored = [(float(score_of((r.code or "").strip())), r) for r in rows]
    scored.sort(key=lambda x: (-x[0], (x[1].name or "").lower()))
    return [
        {"id": r.id, "name": r.name, "code": r.code or "",
         "frequent": s > 0, "score": round(s, 2)}
        for s, r in scored
    ]


def rank_clients(db) -> list:
    m = get_model()["client"]
    rows = (db.query(models.BillingClient)
            .filter(models.BillingClient.is_active == True).all())
    return _ranked(rows, lambda code: m.get(code, 0.0))


def rank_projects(db, client_id: Optional[int]) -> list:
    model = get_model()
    rows = (db.query(models.BillingProject)
            .filter(models.BillingProject.is_active == True).all())
    cond = None
    if client_id:
        client = db.get(models.BillingClient, client_id)
        if client and (client.code or "").strip() in model["proj_by_client"]:
            cond = model["proj_by_client"][(client.code or "").strip()]
    # known client with history → conditional; otherwise marginal project frequency
    table = cond if cond is not None else model["project"]
    return _ranked(rows, lambda code: table.get(code, 0.0))


def rank_tasks(db, project_id: Optional[int]) -> list:
    model = get_model()
    rows = (db.query(models.BillingTask)
            .filter(models.BillingTask.is_active == True).all())
    cond = None
    if project_id:
        project = db.get(models.BillingProject, project_id)
        if project and (project.code or "").strip() in model["task_by_proj"]:
            cond = model["task_by_proj"][(project.code or "").strip()]
    table = cond if cond is not None else model["task"]
    return _ranked(rows, lambda code: table.get(code, 0.0))
