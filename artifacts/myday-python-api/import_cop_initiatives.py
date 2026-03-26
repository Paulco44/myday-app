"""
Bulk-import CoP Org Plan initiatives from a CSV file.

Expected CSV header (at minimum):
    Effort, Topic, Topic Description, Sub topic/ Application,
    Type of K.O / Effort, Focus Market, Leader / Responsible, Notas,
    Jan, Feb, Mar, Apr, May, Jun, Jul, Aug, Sep, Oct, Nov, Dec

Each month column contains "x" (case-insensitive) if active, otherwise blank.

Usage (standalone):
    python import_cop_initiatives.py /path/to/cop_org_plan_pc.csv

Usage (from app):
    from import_cop_initiatives import run_import
    count = run_import(db_session, csv_path)
"""

import csv
import os
import sys

# ---------------------------------------------------------------------------
# Column header → model field mapping
# ---------------------------------------------------------------------------
MONTH_COLS = {
    "Jan": "active_jan",
    "Feb": "active_feb",
    "Mar": "active_mar",
    "Apr": "active_apr",
    "May": "active_may",
    "Jun": "active_jun",
    "Jul": "active_jul",
    "Aug": "active_aug",
    "Sep": "active_sep",
    "Oct": "active_oct",
    "Nov": "active_nov",
    "Dec": "active_dec",
}

# Default CSV path relative to repl root
DEFAULT_CSV = os.path.join(
    os.path.dirname(__file__),  # artifacts/myday-python-api/
    "..", "..",                  # back to repo root
    "cop_org_plan_pc.csv",
)


def _is_active(cell: str) -> bool:
    """Return True if the cell contains 'x' (case-insensitive), else False."""
    return cell.strip().lower() == "x"


def _clean(val) -> str | None:
    """Strip whitespace; return None if empty."""
    v = (val or "").strip()
    return v if v else None


def run_import(db, csv_path: str | None = None) -> dict:
    """
    Read the CSV and bulk-insert CoPInitiative rows.

    Args:
        db:        SQLAlchemy Session (already open).
        csv_path:  Absolute or relative path to the CSV file.
                   Defaults to DEFAULT_CSV (repo-root/cop_org_plan_pc.csv).

    Returns:
        dict with keys: imported (int), skipped (int), errors (list[str])
    """
    import models  # local import so the script is usable without FastAPI

    csv_path = csv_path or DEFAULT_CSV
    csv_path = os.path.abspath(csv_path)

    if not os.path.isfile(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    imported = 0
    skipped = 0
    errors = []

    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)

        # Normalise header names (strip whitespace)
        reader.fieldnames = [h.strip() for h in (reader.fieldnames or [])]

        for lineno, row in enumerate(reader, start=2):  # 1=header
            # Skip rows with no leader
            leader = _clean(row.get("Leader / Responsible") or row.get("Leader") or "")
            if not leader:
                skipped += 1
                continue

            try:
                month_kwargs = {
                    field: _is_active(row.get(col, ""))
                    for col, field in MONTH_COLS.items()
                }
                initiative = models.CoPInitiative(
                    effort=_clean(row.get("Effort")),
                    topic=_clean(row.get("Topic")),
                    topic_description=_clean(row.get("Topic Description")),
                    subtopic=_clean(row.get("Sub topic/ Application") or row.get("Sub topic")),
                    type_of_effort=_clean(row.get("Type of K.O / Effort") or row.get("Type of Effort")),
                    focus_market=_clean(row.get("Focus Market")),
                    leader=leader,
                    cop_collaboration=None,
                    notes=_clean(row.get("Notas") or row.get("Notes")),
                    **month_kwargs,
                )
                db.add(initiative)
                imported += 1
            except Exception as exc:
                errors.append(f"Row {lineno}: {exc}")

    if imported:
        db.commit()

    return {"imported": imported, "skipped": skipped, "errors": errors}


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    csv_arg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV

    # Bootstrap database connection the same way the app does
    sys.path.insert(0, os.path.dirname(__file__))
    from database import SessionLocal
    import models  # noqa: F401 (needed for metadata)
    from database import engine, Base

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        result = run_import(db, csv_arg)
    finally:
        db.close()

    print(f"Imported : {result['imported']}")
    print(f"Skipped  : {result['skipped']} (no leader)")
    for err in result["errors"]:
        print(f"ERROR    : {err}")
