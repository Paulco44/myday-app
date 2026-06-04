"""Reconciliation: actual hours from TimeTracker vs planned hours in MyDay.

Reads TimeTracker's SQLite (READ-ONLY — never writes) and aggregates the
classified time_entries for a week by project code (CC2) and by day, so the
planner can show planned-vs-actual. TimeTracker stays untouched.
"""
import os
import sqlite3
from datetime import date, timedelta
from typing import Optional

TT_DB = os.environ.get("TIMETRACKER_DB", r"C:\TimeTracker\timetracker.db")


def _connect_ro(path: str):
    """Open the SQLite file read-only; fall back to a normal open."""
    try:
        return sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except Exception:
        return sqlite3.connect(path)


def actual_for_week(week_start: date, db_path: Optional[str] = None) -> dict:
    """Actual billable hours for the week from TimeTracker time_entries."""
    path = db_path or TT_DB
    out = {"available": False, "by_project": {}, "by_day": {}, "total": 0.0}
    if not os.path.exists(path):
        return out
    we = week_start + timedelta(days=7)
    try:
        con = _connect_ro(path)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT work_date, project_code, project_name, duration_hours "
            "FROM time_entries WHERE work_date >= ? AND work_date < ?",
            (week_start.isoformat(), we.isoformat()),
        ).fetchall()
        con.close()
    except Exception:
        return out
    out["available"] = True
    for r in rows:
        hours = float(r["duration_hours"] or 0)
        code = (r["project_code"] or "").strip() or "(sin código)"
        bucket = out["by_project"].setdefault(code, {"name": (r["project_name"] or "").strip(), "hours": 0.0})
        bucket["hours"] += hours
        out["by_day"][r["work_date"]] = out["by_day"].get(r["work_date"], 0.0) + hours
        out["total"] += hours
    return out
