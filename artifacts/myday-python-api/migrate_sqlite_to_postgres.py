"""
One-time migration: SQLite app.db → PostgreSQL (DATABASE_URL).

Run once from the artifacts/myday-python-api directory:
    python migrate_sqlite_to_postgres.py

Idempotent: skips rows whose primary key already exists in PostgreSQL.
"""
import os
import sys
import sqlite3
from sqlalchemy import create_engine, text, inspect, Boolean
from sqlalchemy.orm import Session

SQLITE_URL = "sqlite:///./app.db"
PG_URL = os.environ.get("DATABASE_URL")

if not PG_URL or PG_URL.startswith("sqlite"):
    print("ERROR: DATABASE_URL must point to a PostgreSQL instance.")
    sys.exit(1)

print(f"Source : {SQLITE_URL}")
print(f"Target : {PG_URL[:40]}...")

# ── Connect to both ────────────────────────────────────────────────────────────
sqlite_engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
pg_engine     = create_engine(PG_URL)

# Import models so Base.metadata knows all tables
import models  # noqa: E402 (side-effect: registers all Table objects)
from database import Base  # noqa: E402

# ── Create all tables in PostgreSQL (no-op if they already exist) ──────────────
print("\nCreating tables in PostgreSQL…")
Base.metadata.create_all(pg_engine)
print("  Done.")

# ── Build a map of boolean column names per table ──────────────────────────────
BOOL_COLS: dict[str, set[str]] = {}
for table_name, table_obj in Base.metadata.tables.items():
    bool_set = {col.name for col in table_obj.columns if isinstance(col.type, Boolean)}
    if bool_set:
        BOOL_COLS[table_name] = bool_set

# ── Helper: copy one table ─────────────────────────────────────────────────────
def migrate_table(table_name: str, sqlite_conn: sqlite3.Connection, pg_engine):
    cur = sqlite_conn.cursor()
    cur.execute(f"SELECT * FROM {table_name}")
    rows = cur.fetchall()
    if not rows:
        print(f"  {table_name}: 0 rows (empty — skipping)")
        return

    cols = [d[0] for d in cur.description]
    bool_cols = BOOL_COLS.get(table_name, set())
    inserted = 0
    skipped  = 0

    with pg_engine.begin() as pg_conn:
        for row in rows:
            row_dict = {}
            for col, val in zip(cols, row):
                # Cast SQLite 0/1 integers to Python bool for PostgreSQL boolean columns
                if col in bool_cols and val is not None:
                    val = bool(val)
                row_dict[col] = val

            col_list  = ", ".join(f'"{c}"' for c in cols)
            val_names = ", ".join(f":{c}" for c in cols)
            sql = text(
                f'INSERT INTO {table_name} ({col_list}) VALUES ({val_names}) '
                f'ON CONFLICT DO NOTHING'
            )
            result = pg_conn.execute(sql, row_dict)
            if result.rowcount:
                inserted += 1
            else:
                skipped += 1

    # Reset PostgreSQL serial sequence so INSERT without id works afterwards
    with pg_engine.begin() as pg_conn:
        try:
            pg_conn.execute(text(
                f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {table_name}), 0) + 1, false)"
            ))
        except Exception:
            pass  # table has no serial id

    print(f"  {table_name}: {inserted} inserted, {skipped} skipped")


# ── Migration order (respect FK dependencies) ─────────────────────────────────
TABLE_ORDER = [
    "projects",
    "settings",
    "tags",
    "recurring_tasks",
    "tasks",
    "subtasks",
    "task_tags",
    "daily_logs",
    "inbox_items",
    "note_items",
    "notion_sources",
    "notion_export_targets",
    "cop_initiatives",
]

sqlite_conn = sqlite3.connect("./app.db")
inspector = inspect(sqlite_engine)
existing_tables = inspector.get_table_names()

print("\nMigrating tables…")
for table in TABLE_ORDER:
    if table in existing_tables:
        migrate_table(table, sqlite_conn, pg_engine)
    else:
        print(f"  {table}: not in SQLite (skipping)")

sqlite_conn.close()
print("\nMigration complete.")
