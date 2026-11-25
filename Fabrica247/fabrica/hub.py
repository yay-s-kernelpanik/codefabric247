"""Servidor central de Fabrica247: dashboard, cola y API de workers.

Los workers solo realizan conexiones salientes. El Hub nunca abre una consola
remota ni envía comandos del sistema operativo a los equipos participantes.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

log = logging.getLogger("fabrica.hub")
LEASE_SECONDS = 180
MAX_BODY = 6_000_000

HUB_SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS projects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  agent_prompt TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workers (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  enabled INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'OFFLINE',
  platform TEXT NOT NULL DEFAULT '',
  version TEXT NOT NULL DEFAULT '',
  last_seen TEXT,
  joined_at TEXT NOT NULL,
  metadata TEXT NOT NULL DEFAULT '{}',
  desired_state TEXT NOT NULL DEFAULT 'RUNNING',
  admin_prompt TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS invites (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token_hash TEXT NOT NULL UNIQUE,
  label TEXT NOT NULL DEFAULT '',
  expires_at TEXT NOT NULL,
  uses_left INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS worker_project_priority (
  worker_id TEXT NOT NULL REFERENCES workers(id) ON DELETE CASCADE,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  priority INTEGER NOT NULL DEFAULT 0,
  enabled INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY(worker_id, project_id)
);
CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES projects(id),
  objective TEXT NOT NULL,
  task_prompt TEXT NOT NULL DEFAULT '',
  cancel_requested INTEGER NOT NULL DEFAULT 0,
  task_type TEXT NOT NULL DEFAULT 'implementation',
  allowed_files TEXT,
  priority INTEGER NOT NULL DEFAULT 0,
  max_retries INTEGER NOT NULL DEFAULT 2,
  attempts INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'PENDING',
  assigned_worker TEXT REFERENCES workers(id),
  lease_until TEXT,
  not_before TEXT,
  branch_name TEXT,
  result TEXT,
  patch_text TEXT,
  integration_status TEXT NOT NULL DEFAULT 'NONE',
  integration_attempts INTEGER NOT NULL DEFAULT 0,
  integration_not_before TEXT,
  integration_branch TEXT,
  integration_commit TEXT,
  integration_error TEXT,
  last_error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hub_tasks_ready ON tasks(status, priority DESC, created_at);
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def stamp(dt: datetime | None = None) -> str:
    return (dt or utcnow()).isoformat(timespec="seconds")


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hub_paths(home: Path) -> tuple[Path, Path, Path, Path]:
    folder = home.expanduser().resolve() / "hub"
    return folder, folder / "hub.sqlite3", folder / "admin_password.txt", folder / "session_secret"


def _restrict_file(path: Path) -> None:
    if os.name != "nt":
        try:
            path.chmod(0o600)
        except OSError:
            pass


def init_hub(home: Path) -> tuple[Path, str]:
    folder, db_path, pass_path, secret_path = hub_paths(home)
    folder.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        try: folder.chmod(0o700)
        except OSError: pass
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(HUB_SCHEMA)
        migrations = {
            "projects": {"agent_prompt": "TEXT NOT NULL DEFAULT ''"},
            "workers": {
                "desired_state": "TEXT NOT NULL DEFAULT 'RUNNING'",
                "admin_prompt": "TEXT NOT NULL DEFAULT ''",
            },
            "tasks": {
                "patch_text": "TEXT",
                "task_prompt": "TEXT NOT NULL DEFAULT ''",
                "cancel_requested": "INTEGER NOT NULL DEFAULT 0",
                "integration_status": "TEXT NOT NULL DEFAULT 'NONE'",
                "integration_attempts": "INTEGER NOT NULL DEFAULT 0",
                "integration_not_before": "TEXT",
                "integration_branch": "TEXT",
                "integration_commit": "TEXT",
                "integration_error": "TEXT",
            },
        }
        for table, additions in migrations.items():
            columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            for column, definition in additions.items():
                if column not in columns:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        conn.commit()
    finally:
        conn.close()
    _restrict_file(db_path)
    if not pass_path.exists():
        password = secrets.token_urlsafe(20)
        pass_path.write_text(password + "\n", encoding="utf-8")
        _restrict_file(pass_path)
    else:
        password = pass_path.read_text(encoding="utf-8").strip()
    if not secret_path.exists():
        secret_path.write_bytes(secrets.token_bytes(48))
        _restrict_file(secret_path)
    return db_path, password


def connect_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=20000")
    return conn


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9-]+", "-", value)
    return re.sub(r"-+", "-", value).strip("-")[:48]


def _json_bytes(data) -> bytes:
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


def _read_json(handler):
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length < 0 or length > MAX_BODY:
        raise ValueError("Cuerpo demasiado grande")
    raw = handler.rfile.read(length) if length else b"{}"
    obj = json.loads(raw.decode("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("Se esperaba un objeto JSON")
    return obj


class HubApplication:
    def __init__(self, home: Path, integration_repo=None, auto_push=False, base_branch="main"):
        self.home = home.expanduser().resolve()
        self.integration_repo = Path(integration_repo).expanduser().resolve() if integration_repo else None
        self.auto_push = bool(auto_push and self.integration_repo)
        self.base_branch = str(base_branch or "main").strip() or "main"
        self.folder, self.db_path, self.password_path, self.secret_path = hub_paths(self.home)
        # Existing installations need additive SQLite migrations at Hub startup;
        # requiring users to remember "hub init" after every update would break upgrades.
        if self.db_path.exists():
            init_hub(self.home)
        if not self.db_path.exists() or not self.secret_path.exists() or not self.password_path.exists():
            raise RuntimeError("Hub no inicializado. Ejecuta: python -m fabrica hub init")
        self.secret = self.secret_path.read_bytes()
        self.admin_password = self.password_path.read_text(encoding="utf-8").strip()
        self.web_dir = Path(__file__).resolve().parent / "web"

    @contextmanager
    def db(self):
        conn = connect_db(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def new_session(self) -> tuple[str, str]:
        payload = {"exp": int(time.time()) + 12 * 3600, "csrf": secrets.token_urlsafe(24)}
        raw = base64.urlsafe_b64encode(_json_bytes(payload)).decode().rstrip("=")
        sig = hmac.new(self.secret, raw.encode(), hashlib.sha256).hexdigest()
        return raw + "." + sig, payload["csrf"]

    def parse_session(self, cookie: str | None):
        if not cookie:
            return None
        try:
            raw, sig = cookie.split(".", 1)
            expected = hmac.new(self.secret, raw.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig, expected):
                return None
            payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
            if int(payload.get("exp", 0)) < int(time.time()):
                return None
            if not isinstance(payload.get("csrf"), str):
                return None
            return payload
        except Exception:
            return None

    def worker_from_header(self, authorization: str | None):
        if not authorization or not authorization.startswith("Bearer "):
            return None
        token = authorization[7:].strip()
        if not token:
            return None
        with self.db() as conn:
            row = conn.execute("SELECT * FROM workers WHERE token_hash=? AND enabled=1", (token_hash(token),)).fetchone()
            return dict(row) if row else None

    def dashboard_data(self):
        with self.db() as conn:
            projects = [dict(r) for r in conn.execute("SELECT * FROM projects ORDER BY name COLLATE NOCASE")]
            workers = []
            for r in conn.execute("SELECT * FROM workers ORDER BY name COLLATE NOCASE"):
                w = dict(r)
                # Nunca exponer siquiera el hash de autenticación al dashboard.
                w.pop("token_hash", None)
                try:
                    wmeta = json.loads(w.get("metadata") or "{}")
                except Exception:
                    wmeta = {}
                w["agent_label"] = wmeta.get("agent", "")
                w["capabilities"] = wmeta.get("capabilities", [])
                w["remote_control"] = bool(wmeta.get("remote_control", False))
                w["cores"] = wmeta.get("cores", 0)
                w["cpu"] = wmeta.get("cpu", "")
                w["online"] = bool(w["last_seen"] and (utcnow() - datetime.fromisoformat(w["last_seen"])).total_seconds() < 75)
                w["priorities"] = {
                    str(x["project_id"]): {"priority": x["priority"], "enabled": bool(x["enabled"])}
                    for x in conn.execute("SELECT project_id, priority, enabled FROM worker_project_priority WHERE worker_id=?", (w["id"],))
                }
                workers.append(w)
            tasks = []
            for r in conn.execute("""SELECT t.*, p.slug AS project_slug, p.name AS project_name,
                                      w.name AS worker_name, w.metadata AS worker_metadata
                                      FROM tasks t JOIN projects p ON p.id=t.project_id
                                      LEFT JOIN workers w ON w.id=t.assigned_worker
                                      ORDER BY t.id DESC LIMIT 60"""):
                item = dict(r)
                try:
                    worker_meta = json.loads(item.pop("worker_metadata") or "{}")
                except Exception:
                    worker_meta = {}
                item["remote_cancel_allowed"] = bool(worker_meta.get("remote_control", False))
                item["cancel_requested"] = bool(item.get("cancel_requested", False))
                item["patch_available"] = bool(item.pop("patch_text", None))
                tasks.append(item)
            counts = {r["status"]: r["n"] for r in conn.execute("SELECT status, COUNT(*) n FROM tasks GROUP BY status")}
            return {"projects": projects, "workers": workers, "tasks": tasks, "counts": counts}

    def create_project(self, data):
        name = str(data.get("name", "")).strip()[:100]
        slug = slugify(str(data.get("slug") or name))
        description = str(data.get("description", "")).strip()[:500]
        agent_prompt = str(data.get("agent_prompt", "")).strip()[:8000]
        if not name or not slug:
            raise ValueError("El proyecto necesita un nombre válido")
        with self.db() as conn:
            cur = conn.execute("INSERT INTO projects(slug,name,description,agent_prompt,created_at) VALUES(?,?,?,?,?)",
                               (slug, name, description, agent_prompt, stamp()))
            conn.commit()
            return {"id": cur.lastrowid, "slug": slug, "name": name, "description": description,
                    "agent_prompt": agent_prompt}

    def update_project_prompt(self, slug: str, data):
        prompt = str(data.get("agent_prompt", "")).strip()
        if len(prompt) > 8000:
            raise ValueError("El prompt del proyecto no puede superar 8000 caracteres")
        with self.db() as conn:
            cur = conn.execute("UPDATE projects SET agent_prompt=? WHERE slug=?", (prompt, slug))
            if cur.rowcount != 1:
                raise LookupError("Proyecto inexistente")
            conn.execute("INSERT INTO audit_log(event,detail,created_at) VALUES(?,?,?)",
                         ("project.prompt.updated", f"project={slug}", stamp()))
            conn.commit()
        return {"ok": True}

    def update_worker_control(self, worker_id: str, data):
        requested_state = data.get("desired_state")
        prompt = str(data.get("admin_prompt", "")).strip()
        if len(prompt) > 8000:
            raise ValueError("El prompt del agente no puede superar 8000 caracteres")
        with self.db() as conn:
            row = conn.execute("SELECT metadata,enabled,desired_state,admin_prompt FROM workers WHERE id=?", (worker_id,)).fetchone()
            if not row:
                raise LookupError("Worker inexistente")
            if not row["enabled"]:
                raise ValueError("El worker está revocado")
            try:
                metadata = json.loads(row["metadata"] or "{}")
            except Exception:
                metadata = {}
            if not metadata.get("remote_control", False):
                raise PermissionError("Esta PC todavía no aceptó el control administrativo remoto")
            state = str(requested_state if requested_state is not None else row["desired_state"]).upper()
            if state not in ("RUNNING", "PAUSED"):
                raise ValueError("desired_state debe ser RUNNING o PAUSED")
            if "admin_prompt" not in data:
                prompt = row["admin_prompt"]
            conn.execute("UPDATE workers SET desired_state=?,admin_prompt=? WHERE id=?",
                         (state, prompt, worker_id))
            conn.execute("INSERT INTO audit_log(event,detail,created_at) VALUES(?,?,?)",
                         ("worker.control.updated", f"worker={worker_id} state={state}", stamp()))
            conn.commit()
        return {"ok": True, "desired_state": state}

    def create_task(self, data):
        slug = str(data.get("project_slug", ""))
        objective = str(data.get("objective", "")).strip()
        ttype = str(data.get("task_type", "implementation"))
        if not objective or len(objective) > 5000:
            raise ValueError("La tarea debe tener entre 1 y 5000 caracteres")
        if ttype not in ("implementation", "reasoning", "light"):
            raise ValueError("Tipo de tarea no válido")
        try:
            priority = max(-100, min(100, int(data.get("priority", 0))))
            retries = max(0, min(10, int(data.get("max_retries", 2))))
        except (ValueError, TypeError):
            raise ValueError("Prioridad o reintentos no válidos")
        allowed = str(data.get("allowed_files", "")).strip()[:1000] or None
        task_prompt = str(data.get("task_prompt", "")).strip()[:8000]
        with self.db() as conn:
            project = conn.execute("SELECT id FROM projects WHERE slug=?", (slug,)).fetchone()
            if not project:
                raise ValueError("Proyecto inexistente")
            cur = conn.execute("""INSERT INTO tasks(project_id,objective,task_prompt,task_type,allowed_files,priority,max_retries,
                              created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)""",
                               (project["id"], objective, task_prompt, ttype, allowed, priority, retries, stamp(), stamp()))
            conn.execute("INSERT INTO audit_log(event,detail,created_at) VALUES(?,?,?)",
                         ("task.created", f"task={cur.lastrowid} project={slug}", stamp()))
            conn.commit()
            return {"id": cur.lastrowid}

    def create_invite(self, data):
        try:
            uses = max(1, min(100, int(data.get("uses", 1))))
            hours = max(1, min(24 * 30, int(data.get("hours", 24))))
        except (ValueError, TypeError):
            raise ValueError("Usos o duración no válidos")
        label = str(data.get("label", "")).strip()[:100]
        token = secrets.token_urlsafe(32)
        with self.db() as conn:
            conn.execute("INSERT INTO invites(token_hash,label,expires_at,uses_left,created_at) VALUES(?,?,?,?,?)",
                         (token_hash(token), label, stamp(utcnow() + timedelta(hours=hours)), uses, stamp()))
            conn.commit()
        return {"token": token, "uses": uses, "expires_at": stamp(utcnow() + timedelta(hours=hours))}

    def enroll_worker(self, data):
        invite = str(data.get("invite", ""))
        name = str(data.get("name", "")).strip()[:100]
        if not name or len(invite) < 20:
            raise ValueError("Invitación o nombre de PC no válido")
        raw_token = secrets.token_urlsafe(40)
        wid = secrets.token_hex(12)
        with self.db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            inv = conn.execute("SELECT * FROM invites WHERE token_hash=?", (token_hash(invite),)).fetchone()
            if not inv or inv["uses_left"] <= 0 or inv["expires_at"] < stamp():
                conn.rollback()
                raise PermissionError("Invitación inválida, vencida o agotada")
            conn.execute("UPDATE invites SET uses_left=uses_left-1 WHERE id=?", (inv["id"],))
            conn.execute("""INSERT INTO workers(id,name,token_hash,joined_at,metadata)
                            VALUES(?,?,?,?,?)""",
                         (wid, name, token_hash(raw_token), stamp(), "{}"))
            conn.execute("INSERT INTO audit_log(event,detail,created_at) VALUES(?,?,?)",
                         ("worker.enrolled", f"worker={wid} name={name}", stamp()))
            conn.commit()
        return {"worker_id": wid, "worker_token": raw_token, "worker_name": name}

    def worker_heartbeat(self, worker, data):
        projects = data.get("projects", [])
        projects = [str(p)[:48] for p in projects if isinstance(p, str)][:100]
        current = data.get("current_task_id")
        now_s = stamp()
        meta = {"projects": projects, "capabilities": data.get("capabilities", [])[:10],
                "agent": str(data.get("agent", ""))[:80],
                "cpu": str(data.get("cpu", ""))[:120],
                "cores": max(0, min(1024, int(data.get("cores", 0) or 0))),
                "remote_control": bool(data.get("remote_control", False))}
        with self.db() as conn:
            if not meta["remote_control"]:
                conn.execute("UPDATE workers SET desired_state='RUNNING',admin_prompt='' WHERE id=?", (worker["id"],))
                if current is not None:
                    conn.execute("UPDATE tasks SET cancel_requested=0 WHERE id=? AND assigned_worker=? AND status='RUNNING'",
                                 (int(current), worker["id"]))
            conn.execute("UPDATE workers SET status='ONLINE',last_seen=?,platform=?,version=?,metadata=? WHERE id=?",
                         (now_s, str(data.get("platform", ""))[:100], str(data.get("version", ""))[:40],
                          json.dumps(meta, ensure_ascii=False), worker["id"]))
            if current is not None:
                conn.execute("UPDATE tasks SET lease_until=?,updated_at=? WHERE id=? AND assigned_worker=? AND status='RUNNING'",
                             (stamp(utcnow() + timedelta(seconds=LEASE_SECONDS)), now_s, int(current), worker["id"]))
            conn.commit()
            control = conn.execute("SELECT desired_state,admin_prompt FROM workers WHERE id=?", (worker["id"],)).fetchone()
            cancel_current = False
            if current is not None and meta["remote_control"]:
                active = conn.execute("SELECT cancel_requested FROM tasks WHERE id=? AND assigned_worker=? AND status='RUNNING'",
                                      (int(current), worker["id"])).fetchone()
                cancel_current = bool(active and active["cancel_requested"])
        # El propietario decide si acepta que el Hub pause, edite instrucciones o
        # solicite detener una tarea activa del agente.
        remote_ok = bool(meta["remote_control"])
        return {"ok": True, "lease_seconds": LEASE_SECONDS,
                "desired_state": control["desired_state"] if remote_ok else "RUNNING",
                "worker_prompt": control["admin_prompt"] if remote_ok else "",
                "cancel_current_task": bool(cancel_current and remote_ok)}

    def _reap_expired(self, conn):
        rows = conn.execute("SELECT id,attempts,max_retries FROM tasks WHERE status='RUNNING' AND lease_until IS NOT NULL AND lease_until<?",
                            (stamp(),)).fetchall()
        for row in rows:
            current = conn.execute("SELECT cancel_requested FROM tasks WHERE id=?", (row["id"],)).fetchone()
            if current and current["cancel_requested"]:
                conn.execute("UPDATE tasks SET status='CANCELLED',assigned_worker=NULL,lease_until=NULL,last_error=?,updated_at=? WHERE id=?",
                             ("Worker desconectado después de recibir una solicitud de detención", stamp(), row["id"]))
            else:
                conn.execute("UPDATE tasks SET status='PENDING',attempts=MAX(attempts-1,0),assigned_worker=NULL,lease_until=NULL,last_error=?,updated_at=? WHERE id=?",
                             ("Worker desconectado; venció el lease (no consume reintentos)", stamp(), row["id"]))

    def claim_task(self, worker, data):
        projects = [str(p)[:48] for p in data.get("projects", []) if isinstance(p, str)][:100]
        capabilities = set(data.get("capabilities", []))
        try:
            remote_control = bool(json.loads(worker.get("metadata") or "{}").get("remote_control", False))
        except Exception:
            remote_control = False
        if remote_control and worker.get("desired_state", "RUNNING") != "RUNNING":
            return {"task": None, "paused": True}
        if not projects:
            return {"task": None}
        placeholders = ",".join("?" for _ in projects)
        allowed_types = []
        if "reasoning" in capabilities: allowed_types.append("reasoning")
        if "light" in capabilities: allowed_types.append("light")
        if "implementation" in capabilities: allowed_types.append("implementation")
        if not allowed_types:
            return {"task": None}
        type_placeholders = ",".join("?" for _ in allowed_types)
        conn = connect_db(self.db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            self._reap_expired(conn)
            worker_prompt = worker.get("admin_prompt", "") if remote_control else ""
            row = conn.execute(f"""SELECT t.*, p.slug AS project_slug, p.agent_prompt AS project_prompt,
                  ? AS worker_prompt, COALESCE(wpp.priority,0) AS agent_priority
                  FROM tasks t JOIN projects p ON p.id=t.project_id
                  LEFT JOIN worker_project_priority wpp ON wpp.worker_id=? AND wpp.project_id=t.project_id
                  WHERE t.status='PENDING' AND (t.not_before IS NULL OR t.not_before<=?)
                    AND p.slug IN ({placeholders}) AND t.task_type IN ({type_placeholders})
                    AND (wpp.enabled IS NULL OR wpp.enabled=1)
                  ORDER BY (t.priority + COALESCE(wpp.priority,0)) DESC, t.priority DESC, t.id ASC LIMIT 1""",
                (worker_prompt, worker["id"], stamp(), *projects, *allowed_types)).fetchone()
            if not row:
                conn.commit()
                return {"task": None}
            lease = stamp(utcnow() + timedelta(seconds=LEASE_SECONDS))
            cur = conn.execute("""UPDATE tasks SET status='RUNNING',assigned_worker=?,lease_until=?,cancel_requested=0,
                                 attempts=attempts+1,updated_at=? WHERE id=? AND status='PENDING'""",
                               (worker["id"], lease, stamp(), row["id"]))
            if cur.rowcount != 1:
                conn.rollback()
                return {"task": None}
            conn.commit()
            task = dict(row)
            task["attempts"] = row["attempts"] + 1
            task.pop("agent_priority", None)
            return {"task": task, "lease_seconds": LEASE_SECONDS}
        finally:
            conn.close()

    def finish_task(self, worker, task_id: int, data):
        outcome = str(data.get("outcome", "fail"))
        if outcome not in ("done", "fail", "infra", "cancelled"):
            raise ValueError("Resultado no válido")
        error = str(data.get("error", ""))[:3000]
        result = str(data.get("result", ""))[:20000]
        branch = str(data.get("branch_name", ""))[:200]
        patch_text = str(data.get("patch", ""))
        if len(patch_text.encode("utf-8")) > 4_500_000:
            patch_text = ""
            error = (error + "\nEl diff supera el límite de 4.5 MB; se conservó solo el resultado.").strip()
        integration_status = ("QUEUED" if self.auto_push else "PATCH_READY") if outcome == "done" and patch_text else "NONE"
        with self.db() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=? AND assigned_worker=? AND status='RUNNING'",
                               (task_id, worker["id"])).fetchone()
            if not row:
                raise PermissionError("La tarea no está asignada a este worker")
            if outcome == "done":
                status = "DONE"
                not_before = None
            elif outcome == "cancelled":
                status = "CANCELLED"
                not_before = None
            elif outcome == "infra":
                status = "PENDING"
                not_before = stamp(utcnow() + timedelta(seconds=min(300, 30 * max(1, row["attempts"]))))
            else:
                status = "PENDING" if row["attempts"] <= row["max_retries"] else "FAILED"
                not_before = None
            conn.execute("""UPDATE tasks SET status=?,assigned_worker=NULL,lease_until=NULL,not_before=?,cancel_requested=0,
                            attempts=CASE WHEN ?='infra' THEN MAX(attempts-1,0) ELSE attempts END,
                            branch_name=?,result=?,patch_text=?,integration_status=?,integration_attempts=0,integration_not_before=NULL,
                            integration_branch=NULL,integration_commit=NULL,integration_error=NULL,last_error=?,updated_at=? WHERE id=?""",
                         (status, not_before, outcome, branch or None, result or None, patch_text or None,
                          integration_status, error or None, stamp(), task_id))
            conn.execute("INSERT INTO audit_log(event,detail,created_at) VALUES(?,?,?)",
                         ("task.finished", f"task={task_id} outcome={outcome} status={status} worker={worker['id']}", stamp()))
            conn.commit()
        return {"ok": True, "status": status}

    def recover_interrupted_integrations(self):
        with self.db() as conn:
            conn.execute("UPDATE tasks SET integration_status='QUEUED',integration_not_before=NULL,integration_error='Hub reiniciado durante integración',updated_at=? WHERE integration_status='INTEGRATING'", (stamp(),))
            conn.commit()

    def process_one_integration(self) -> bool:
        """Claim and publish one task branch; called by the Hub's single integrator."""
        with self.db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("""SELECT t.*, p.slug AS project_slug FROM tasks t
                                  JOIN projects p ON p.id=t.project_id
                                  WHERE t.integration_status='QUEUED' AND t.status='DONE'
                                    AND (t.integration_not_before IS NULL OR t.integration_not_before<=?)
                                  ORDER BY t.priority DESC,t.id ASC LIMIT 1""", (stamp(),)).fetchone()
            if not row:
                conn.commit()
                return False
            task = dict(row)
            cur = conn.execute("UPDATE tasks SET integration_status='INTEGRATING',integration_not_before=NULL,integration_error=NULL,updated_at=? WHERE id=? AND integration_status='QUEUED'", (stamp(), task['id']))
            if cur.rowcount != 1:
                conn.rollback()
                return False
            reserved_branches = [
                item["integration_branch"] for item in conn.execute(
                    "SELECT integration_branch FROM tasks WHERE integration_status='PUSHED' "
                    "AND integration_branch IS NOT NULL AND id<>?", (task["id"],)
                )
            ]
            conn.commit()
        from .integration import IntegrationConflict, push_patch
        try:
            result = push_patch(self.integration_repo, int(task['id']), task['objective'],
                                task.get('patch_text') or '', task.get('allowed_files'), self.base_branch,
                                reserved_branches=reserved_branches)
            state, error = 'PUSHED', None
            branch, commit = result['branch'], result['commit']
        except IntegrationConflict as exc:
            state, error, branch, commit = 'CONFLICT', str(exc)[:2000], None, None
            attempts, retry_at = int(task.get("integration_attempts") or 0), None
        except Exception as exc:
            log.exception("No se pudo integrar la tarea %s", task['id'])
            attempts = int(task.get("integration_attempts") or 0) + 1
            if attempts < 8:
                delay = min(900, 30 * (2 ** (attempts - 1)))
                state, retry_at = 'QUEUED', stamp(utcnow() + timedelta(seconds=delay))
            else:
                state, retry_at = 'FAILED', None
            error, branch, commit = str(exc)[:2000], None, None
        else:
            attempts, retry_at = int(task.get("integration_attempts") or 0), None
        with self.db() as conn:
            conn.execute("UPDATE tasks SET integration_status=?,integration_attempts=?,integration_not_before=?,integration_branch=?,integration_commit=?,integration_error=?,updated_at=? WHERE id=?",
                         (state, attempts, retry_at, branch, commit, error, stamp(), task['id']))
            conn.execute("INSERT INTO audit_log(event,detail,created_at) VALUES(?,?,?)",
                         ("task.integration." + state.lower(), f"task={task['id']} branch={branch or '-'}", stamp()))
            conn.commit()
        return True

    def task_action(self, task_id: int, action: str):
        with self.db() as conn:
            row = conn.execute("SELECT status,integration_status,patch_text FROM tasks WHERE id=?", (task_id,)).fetchone()
            if not row:
                raise LookupError("Tarea inexistente")
            status = row["status"]
            if action == "retry-integration":
                if status != "DONE" or row["integration_status"] not in ("FAILED", "CONFLICT", "PATCH_READY") or not row["patch_text"]:
                    raise ValueError("La tarea no tiene una integración reintentable")
                if not self.auto_push or not self.integration_repo:
                    raise ValueError("Configurá HUB_AUTO_PUSH=true y TARGET_REPO en el Hub")
                conn.execute("UPDATE tasks SET integration_status='QUEUED',integration_attempts=0,integration_not_before=NULL,integration_error=NULL,updated_at=? WHERE id=?", (stamp(), task_id))
            elif action == "retry":
                if status not in ("FAILED", "CANCELLED"):
                    raise ValueError("Solo se pueden reintentar tareas FAILED o CANCELLED")
                conn.execute("""UPDATE tasks SET status='PENDING',attempts=0,assigned_worker=NULL,
                                lease_until=NULL,not_before=NULL,cancel_requested=0,last_error=NULL,result=NULL,patch_text=NULL,
                                integration_status='NONE',integration_attempts=0,integration_not_before=NULL,
                                integration_branch=NULL,integration_commit=NULL,integration_error=NULL,
                                branch_name=NULL,updated_at=? WHERE id=?""",
                             (stamp(), task_id))
            elif action == "cancel":
                if status == "PENDING":
                    conn.execute("UPDATE tasks SET status='CANCELLED',updated_at=? WHERE id=?", (stamp(), task_id))
                elif status == "RUNNING":
                    worker = conn.execute("SELECT w.metadata FROM workers w JOIN tasks t ON t.assigned_worker=w.id WHERE t.id=?",
                                          (task_id,)).fetchone()
                    try:
                        consent = bool(worker and json.loads(worker["metadata"] or "{}").get("remote_control", False))
                    except Exception:
                        consent = False
                    if not consent:
                        raise PermissionError("El Worker no aceptó la detención remota de tareas")
                    conn.execute("UPDATE tasks SET cancel_requested=1,updated_at=? WHERE id=?", (stamp(), task_id))
                else:
                    raise ValueError("Solo se pueden cancelar tareas PENDING o RUNNING")
            else:
                raise ValueError("Acción no válida")
            conn.commit()
        if action == "retry-integration":
            return {"ok": True, "status": "QUEUED"}
        return {"ok": True, "status": "PENDING" if action == "retry" else ("CANCEL_REQUESTED" if status == "RUNNING" else "CANCELLED")}


def make_handler(app: HubApplication):
    class Handler(BaseHTTPRequestHandler):
        server_version = "Fabrica247Hub/3.0"

        def log_message(self, fmt, *args):
            log.info("%s - %s", self.address_string(), fmt % args)

        def _send(self, status=200, payload=None, content_type="application/json; charset=utf-8", headers=None):
            if isinstance(payload, bytes):
                body = payload
            elif content_type.startswith("application/json"):
                body = _json_bytes(payload if payload is not None else {})
            else:
                body = (payload or "").encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "same-origin")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _error(self, status, message):
            self._send(status, {"error": message})

        def _body(self):
            return _read_json(self)

        def _session(self):
            cookie = self.headers.get("Cookie", "")
            cookies = {}
            for part in cookie.split(";"):
                if "=" in part:
                    k, v = part.strip().split("=", 1)
                    cookies[k] = v
            return app.parse_session(cookies.get("fabrica_session"))

        def _admin(self, mutation=False):
            session = self._session()
            if not session:
                self._error(401, "Iniciá sesión")
                return None
            if mutation and not hmac.compare_digest(str(self.headers.get("X-Fabrica-CSRF", "")), session["csrf"]):
                self._error(403, "Token CSRF inválido")
                return None
            return session

        def _worker(self):
            worker = app.worker_from_header(self.headers.get("Authorization"))
            if not worker:
                self._error(401, "Worker no autenticado")
                return None
            return worker

        def do_GET(self):
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                self._static("index.html", "text/html; charset=utf-8"); return
            if path == "/assets/app.js":
                self._static("app.js", "text/javascript; charset=utf-8"); return
            if path == "/assets/style.css":
                self._static("style.css", "text/css; charset=utf-8"); return
            if path == "/api/session":
                session = self._session()
                if not session:
                    self._send(200, {"authenticated": False}); return
                self._send(200, {"authenticated": True, "csrf": session["csrf"]}); return
            if path == "/api/admin/dashboard":
                if not self._admin(): return
                self._send(200, app.dashboard_data()); return
            patch_match = re.fullmatch(r"/api/admin/tasks/(\d+)/patch", path)
            if patch_match:
                if not self._admin(): return
                with app.db() as conn:
                    row = conn.execute("SELECT patch_text FROM tasks WHERE id=?", (int(patch_match.group(1)),)).fetchone()
                if not row or not row["patch_text"]:
                    self._error(404, "No hay patch disponible para esta tarea"); return
                self._send(200, row["patch_text"], "text/x-diff; charset=utf-8", {
                    "Content-Disposition": f"attachment; filename=fabrica-task-{patch_match.group(1)}.patch"
                }); return
            self._error(404, "No encontrado")

        def _static(self, filename, mime):
            path = app.web_dir / filename
            if not path.is_file():
                self._error(404, "Interfaz no instalada"); return
            self._send(200, path.read_bytes(), mime)

        def do_POST(self):
            path = urlparse(self.path).path
            try:
                data = self._body()
                if path == "/api/logout":
                    if not self._admin(mutation=True): return
                    self._send(200, {"ok": True}, headers={"Set-Cookie": "fabrica_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"})
                    return
                if path == "/api/login":
                    password = str(data.get("password", ""))
                    if not hmac.compare_digest(password, app.admin_password):
                        self._error(401, "Contraseña incorrecta"); return
                    cookie, csrf = app.new_session()
                    secure = "; Secure" if self.headers.get("X-Forwarded-Proto", "").lower() == "https" else ""
                    self._send(200, {"ok": True, "csrf": csrf}, headers={
                        "Set-Cookie": f"fabrica_session={cookie}; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200{secure}"
                    }); return
                if path == "/api/worker/enroll":
                    self._send(201, app.enroll_worker(data)); return
                if path.startswith("/api/worker/"):
                    worker = self._worker()
                    if not worker: return
                    if path == "/api/worker/heartbeat":
                        self._send(200, app.worker_heartbeat(worker, data)); return
                    if path == "/api/worker/claim":
                        self._send(200, app.claim_task(worker, data)); return
                    match = re.fullmatch(r"/api/worker/tasks/(\d+)/result", path)
                    if match:
                        self._send(200, app.finish_task(worker, int(match.group(1)), data)); return
                    self._error(404, "No encontrado"); return
                if not self._admin(mutation=True): return
                if path == "/api/admin/projects":
                    self._send(201, app.create_project(data)); return
                if path == "/api/admin/tasks":
                    self._send(201, app.create_task(data)); return
                if path == "/api/admin/invites":
                    self._send(201, app.create_invite(data)); return
                match = re.fullmatch(r"/api/admin/workers/([a-f0-9]+)/control", path)
                if match:
                    self._send(200, app.update_worker_control(match.group(1), data)); return
                match = re.fullmatch(r"/api/admin/workers/([a-f0-9]+)/revoke", path)
                if match:
                    with app.db() as conn:
                        cur = conn.execute("UPDATE workers SET enabled=0,status='REVOKED' WHERE id=?", (match.group(1),))
                        conn.commit()
                    self._send(200, {"ok": cur.rowcount == 1}); return
                match = re.fullmatch(r"/api/admin/tasks/(\d+)/(retry-integration|retry|cancel)", path)
                if match:
                    self._send(200, app.task_action(int(match.group(1)), match.group(2))); return
                self._error(404, "No encontrado")
            except PermissionError as e:
                self._error(403, str(e))
            except LookupError as e:
                self._error(404, str(e))
            except (ValueError, json.JSONDecodeError) as e:
                self._error(400, str(e))
            except sqlite3.IntegrityError as e:
                self._error(409, "Conflicto: el elemento ya existe o la referencia no es válida")
            except Exception:
                log.exception("Error atendiendo POST %s", path)
                self._error(500, "Error interno del Hub")

        def do_PATCH(self):
            path = urlparse(self.path).path
            try:
                if not self._admin(mutation=True): return
                data = self._body()
                match = re.fullmatch(r"/api/admin/projects/([a-z0-9-]+)/prompt", path)
                if match:
                    self._send(200, app.update_project_prompt(match.group(1), data)); return
                match = re.fullmatch(r"/api/admin/workers/([a-f0-9]+)/priority", path)
                if match:
                    try:
                        priority = max(-100, min(100, int(data.get("priority", 0))))
                        project_id = int(data.get("project_id"))
                        enabled = 1 if data.get("enabled", True) else 0
                    except (ValueError, TypeError):
                        raise ValueError("Prioridad o proyecto inválido")
                    with app.db() as conn:
                        conn.execute("""INSERT INTO worker_project_priority(worker_id,project_id,priority,enabled)
                                      VALUES(?,?,?,?) ON CONFLICT(worker_id,project_id) DO UPDATE SET
                                      priority=excluded.priority,enabled=excluded.enabled""",
                                     (match.group(1), project_id, priority, enabled))
                        conn.commit()
                    self._send(200, {"ok": True}); return
                match = re.fullmatch(r"/api/admin/tasks/(\d+)", path)
                if match:
                    task_id = int(match.group(1))
                    fields = []
                    values = []
                    if "priority" in data:
                        try:
                            priority = max(-100, min(100, int(data["priority"])))
                        except (ValueError, TypeError):
                            raise ValueError("Prioridad no válida")
                        fields.append("priority=?")
                        values.append(priority)
                    if "task_prompt" in data:
                        prompt = str(data.get("task_prompt", "")).strip()
                        if len(prompt) > 8000:
                            raise ValueError("El prompt de tarea no puede superar 8000 caracteres")
                        fields.append("task_prompt=?")
                        values.append(prompt)
                    if not fields:
                        raise ValueError("No hay campos para actualizar")
                    fields.append("updated_at=?")
                    values.extend([stamp(), task_id])
                    with app.db() as conn:
                        row = conn.execute("SELECT id FROM tasks WHERE id=?", (task_id,)).fetchone()
                        if not row:
                            self._error(404, "Tarea inexistente"); return
                        conn.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id=?", values)
                        conn.execute("INSERT INTO audit_log(event,detail,created_at) VALUES(?,?,?)",
                                     ("task.updated", f"task={task_id} fields={','.join(k for k in ('priority','task_prompt') if k in data)}", stamp()))
                        conn.commit()
                    self._send(200, {"ok": True}); return
                self._error(404, "No encontrado")
            except ValueError as e:
                self._error(400, str(e))
            except Exception:
                log.exception("Error atendiendo PATCH %s", path)
                self._error(500, "Error interno del Hub")

        def do_DELETE(self):
            path = urlparse(self.path).path
            if not self._admin(mutation=True): return
            self._error(405, "Usá la acción de revocar para deshabilitar un worker")

    return Handler


def serve_hub(home: Path, host="127.0.0.1", port=8765, integration_repo=None, auto_push=False, base_branch="main"):
    if auto_push and not integration_repo:
        raise RuntimeError("HUB_AUTO_PUSH=true requiere TARGET_REPO apuntando al clon Git del Hub")
    app = HubApplication(home, integration_repo=integration_repo, auto_push=auto_push, base_branch=base_branch)
    app.recover_interrupted_integrations()
    server = ThreadingHTTPServer((host, int(port)), make_handler(app))
    server.daemon_threads = True
    integration_stop = threading.Event()
    integration_thread = None
    if app.auto_push:
        def _integrate_loop():
            while not integration_stop.wait(2):
                try:
                    while app.process_one_integration():
                        pass
                except Exception:
                    log.exception("Bucle de integración interrumpido; se reintentará")
        integration_thread = threading.Thread(target=_integrate_loop, name="fabrica-integrator", daemon=True)
        integration_thread.start()
    print(f"Fabrica247 Hub disponible en http://{host}:{port}/")
    if host in ("0.0.0.0", "::"):
        print("AVISO: escucha en todas las interfaces. Para acceso remoto usá una VPN privada (p. ej. Tailscale) o HTTPS detrás de un proxy; no publiques el puerto sin protección.")
    print(f"Contraseña de administrador: {app.password_path}")
    if app.auto_push:
        print(f"Integración automática activa: {app.integration_repo} -> origin/{app.base_branch}")
        print("Cada tarea se publica en fabrica/task-ID; main nunca recibe push automático.")
    else:
        print("Integración automática desactivada; los patches quedan disponibles en el panel.")
    print("Ctrl+C para detener. Los workers se conectan hacia este servidor.")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("\nDeteniendo Hub...")
    finally:
        integration_stop.set()
        if integration_thread is not None:
            integration_thread.join(timeout=3)
        server.server_close()
