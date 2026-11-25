"""SQLite: esquema embebido (sin rutas relativas a archivos externos)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

TS_FMT = "%Y-%m-%d %H:%M:%S"

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    objective      TEXT    NOT NULL,
    task_type      TEXT    NOT NULL DEFAULT 'auto',   -- auto|implementation|reasoning|light
    allowed_files  TEXT,                              -- prefijos/globs separados por coma
    test_command   TEXT,
    priority       INTEGER NOT NULL DEFAULT 0,
    retry_count    INTEGER NOT NULL DEFAULT 0,        -- fallos reales de la tarea
    max_retries    INTEGER NOT NULL DEFAULT 2,        -- reintentos tras el primer intento
    infra_failures INTEGER NOT NULL DEFAULT 0,        -- caidas de infraestructura (no consumen reintentos)
    status         TEXT    NOT NULL DEFAULT 'PENDING',-- PENDING|RUNNING|DONE|FAILED|CANCELLED
    assigned_model TEXT,
    branch_name    TEXT,
    base_commit    TEXT,
    not_before     TEXT,                              -- UTC; no ejecutar antes de esta hora
    last_error     TEXT,
    output_path    TEXT,
    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tasks_ready ON tasks(status, priority DESC, id);
"""


def now() -> str:
    return datetime.now(timezone.utc).strftime(TS_FMT)


def later(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).strftime(TS_FMT)


def connect(db_path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db(cfg) -> sqlite3.Connection:
    cfg.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(cfg.db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def add_task(conn, objective, task_type="auto", allowed_files=None, test_command=None,
             priority=0, max_retries=2) -> int:
    cur = conn.execute(
        "INSERT INTO tasks (objective, task_type, allowed_files, test_command, priority, max_retries)"
        " VALUES (?,?,?,?,?,?)",
        (objective, task_type, allowed_files, test_command, priority, max_retries),
    )
    conn.commit()
    return cur.lastrowid


def update_task(conn, task_id: int, **fields) -> None:
    fields["updated_at"] = now()
    cols = ", ".join(f"{k}=?" for k in fields)
    conn.execute(f"UPDATE tasks SET {cols} WHERE id=?", (*fields.values(), task_id))
    conn.commit()
