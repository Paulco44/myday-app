"""
Bulk-import CoP Org Plan initiatives from a CSV file.

Month columns are matched by the first 3 letters of the column header
(case-insensitive), so "Jan", "Jan-26", "January" all map to active_jan.

Usage (standalone):
    python import_cop_initiatives.py /path/to/cop_org_plan_pc.csv

Usage (from app):
    from import_cop_initiatives import run_import
    result = run_import(db_session, csv_path)
"""

import csv
import os
import sys

# ---------------------------------------------------------------------------
# Month abbreviation → model field name
# ---------------------------------------------------------------------------
MONTH_ABBR_TO_FIELD = {
    "jan": "active_jan",
    "feb": "active_feb",
    "mar": "active_mar",
    "apr": "active_apr",
    "may": "active_may",
    "jun": "active_jun",
    "jul": "active_jul",
    "aug": "active_aug",
    "sep": "active_sep",
    "oct": "active_oct",
    "nov": "active_nov",
    "dec": "active_dec",
}

# Default CSV path: repo root / cop_org_plan_pc.csv
DEFAULT_CSV = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "cop_org_plan_pc.csv")
)


def _is_active(cell: str) -> bool:
    """True if cell contains 'x' (any case)."""
    return cell.strip().lower() == "x"


def _clean(val) -> "str | None":
    """Strip whitespace; return None if empty."""
    v = (val or "").strip()
    return v if v else None


def _build_month_map(headers: list) -> dict:
    """
    Scan actual CSV headers and return {header_name: model_field} for months.
    Matches on the first 3 characters of each header (case-insensitive), so
    'Jan', 'Jan-26', 'January 2026' all resolve to 'active_jan'.
    """
    mapping = {}
    for h in headers:
        prefix = h.strip()[:3].lower()
        if prefix in MONTH_ABBR_TO_FIELD:
            mapping[h.strip()] = MONTH_ABBR_TO_FIELD[prefix]
    return mapping


def run_import(db, csv_path: "str | None" = None) -> dict:
    """
    Read the CSV and bulk-insert CoPInitiative rows.

    Returns dict: {imported, skipped, errors, month_map_used}
    """
    import models  # local import keeps script usable without FastAPI

    csv_path = os.path.abspath(csv_path or DEFAULT_CSV)

    if not os.path.isfile(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    imported = 0
    skipped = 0
    errors = []
    month_map: dict = {}

    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)

        # Strip whitespace from every header
        raw_headers = reader.fieldnames or []
        reader.fieldnames = [h.strip() for h in raw_headers]

        # Build month mapping once from the real headers
        month_map = _build_month_map(reader.fieldnames)

        for lineno, row in enumerate(reader, start=2):
            # Skip rows with no leader
            leader = _clean(
                row.get("Leader / Responsible")
                or row.get("Leader")
                or ""
            )
            if not leader:
                skipped += 1
                continue

            try:
                # Resolve month booleans using the dynamic map
                month_kwargs = {
                    field: _is_active(row.get(col, ""))
                    for col, field in month_map.items()
                }
                # Fill any months not found in the CSV as False
                for field in MONTH_ABBR_TO_FIELD.values():
                    month_kwargs.setdefault(field, False)

                initiative = models.CoPInitiative(
                    effort=_clean(row.get("Effort")),
                    topic=_clean(row.get("Topic")),
                    topic_description=_clean(row.get("Topic Description")),
                    subtopic=_clean(
                        row.get("Sub topic/ Application")
                        or row.get("Sub topic")
                    ),
                    type_of_effort=_clean(
                        row.get("Type of K.O / Effort")
                        or row.get("Type of Effort")
                    ),
                    focus_market=_clean(row.get("Focus Market")),
                    leader=leader,
                    cop_collaboration=_clean(
                        row.get("CofP Collaboration")
                        or row.get("CoP Collaboration")
                        or row.get("cop_collaboration")
                    ),
                    notes=_clean(row.get("Notas") or row.get("Notes")),
                    **month_kwargs,
                )
                db.add(initiative)
                imported += 1
            except Exception as exc:
                errors.append(f"Row {lineno}: {exc}")

    if imported:
        db.commit()

    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "month_map_used": list(month_map.keys()),
    }


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
