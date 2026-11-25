"""Bucle principal: toma tareas de SQLite, las ejecuta con OpenCode en worktrees aislados."""
from __future__ import annotations

import fnmatch
import logging
import os
import re
import signal
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import NamedTuple

from . import gitops, proc, services
from .db import init_db, later, now, update_task
from .health import router_ok

log = logging.getLogger("fabrica")

INFRA_RE = re.compile(
    r"ECONNREFUSED|ECONNRESET|ENOTFOUND|connection refused|connection error|fetch failed|"
    r"\b429\b|rate.?limit|quota|exhaust|insufficient|\b50[234]\b|bad gateway|service unavailable|"
    r"no available|all models", re.I)


class Outcome(NamedTuple):
    kind: str      # ok | fail | infra
    message: str = ""


# ----------------------------------------------------------------- utilidades
def setup_logging(cfg, console=True):
    cfg.logs_dir.mkdir(parents=True, exist_ok=True)
    if log.handlers:
        return
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh = RotatingFileHandler(cfg.logs_dir / "supervisor.log", maxBytes=2_000_000,
                             backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    log.addHandler(fh)
    if console:
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        log.addHandler(sh)


def classify_task(objective: str) -> str:
    t = objective.lower()
    if any(w in t for w in ("solo lectura", "read-only", "read only", "planific", "revis", "audit",
                            "dise\u00f1", "analiz", "review", "investig")):
        return "reasoning"
    if any(w in t for w in ("resum", "summar", "list")):
        return "light"
    return "implementation"


def path_allowed(path: str, patterns: list) -> bool:
    path = path.replace("\\", "/")
    for p in patterns:
        p = p.strip().replace("\\", "/")
        if not p:
            continue
        if p.endswith("/"):
            if path.startswith(p):
                return True
        elif path == p or path.startswith(p + "/") or fnmatch.fnmatch(path, p):
            return True
    return False


def build_prompt(task, ttype: str) -> str:
    lines = [f"OBJETIVO: {task['objective']}", "",
             "REGLAS:",
             "- Trabaja de forma autonoma en el directorio actual (worktree git aislado).",
             "- Nadie puede responder preguntas: toma decisiones razonables y continua.",
             "- No toques nada fuera del directorio actual."]
    if ttype == "reasoning":
        lines.append("- SOLO LECTURA: no crees, modifiques ni borres archivos. "
                     "Entrega tu analisis completo como respuesta final.")
    else:
        lines.append("- Modifica solo lo necesario. No hace falta hacer commit: lo hace el supervisor.")
    if task["allowed_files"]:
        lines.append(f"- Solo puedes modificar estas rutas: {task['allowed_files']}")
    if task["test_command"]:
        lines.append(f"- El resultado se validara con: {task['test_command']}  (ejecutalo y corrige hasta que pase)")
    if task["last_error"]:
        lines.append(f"- El intento anterior fallo con: {task['last_error'][:600]}")
    for title, key in (("INSTRUCCIONES LOCALES DEL PROPIETARIO", "local_prompt"),
                       ("INSTRUCCIONES DEL PROYECTO (administrador del Hub)", "project_prompt"),
                       ("INSTRUCCIONES PARA ESTE WORKER (control remoto aceptado)", "worker_prompt"),
                       ("INSTRUCCIONES ESPECÍFICAS DE ESTA TAREA", "task_prompt")):
        value = str(task.get(key) or "").strip()
        if value:
            lines.extend(["", f"{title}:", value])
    return "\n".join(lines)


def _agent_args(cfg, task_id, prompt):
    """En Windows los shims .cmd de npm rompen comillas/saltos de linea: se pasa un puntero a archivo."""
    exe = proc.resolve_exe(cfg.opencode_bin)
    arg = prompt
    if proc.IS_WIN and exe.lower().endswith((".cmd", ".bat")):
        pf = cfg.logs_dir / "tasks" / f"task-{task_id}.prompt.md"
        pf.write_text(prompt, encoding="utf-8")
        arg = f"Lee el archivo {pf} y ejecuta exactamente las instrucciones que contiene."
    return [exe, "run", "--model", cfg.model, arg]


# ----------------------------------------------------------------- ejecucion
def run_agent(cfg, task, ttype, wt, cancel_event=None) -> proc.Result:
    env = os.environ.copy()
    env["OPENCODE_CONFIG"] = str(cfg.opencode_config)
    env["FABRICA247_ROUTER_API_KEY"] = str(getattr(cfg, "api_key", ""))
    args = _agent_args(cfg, task["id"], build_prompt(task, ttype))
    return proc.run_cmd(args, cwd=wt, env=env, timeout=cfg.task_timeout, cancel_event=cancel_event)


def evaluate(cfg, task, ttype, wt, base, res) -> Outcome:
    infra_hint = cfg.require_router and not router_ok(cfg)
    if res.timed_out:
        return Outcome("infra" if infra_hint else "fail", "timeout del agente")
    if res.returncode != 0:
        tail = (res.stderr + "\n" + res.stdout)[-1500:]
        if infra_hint or INFRA_RE.search(tail):
            return Outcome("infra", tail[-400:])
        return Outcome("fail", f"opencode salio con codigo {res.returncode}: {tail[-400:]}")

    if gitops.is_dirty(wt):
        gitops.commit_all(wt, f"fabrica247: tarea {task['id']}")
    commits = gitops.commits_since(wt, base)
    changed = gitops.changed_files(wt, base) if commits else []

    if ttype == "reasoning" and changed:
        return Outcome("fail", f"tarea de solo lectura que modifico archivos: {changed[:5]}")
    if task["allowed_files"]:
        pats = task["allowed_files"].split(",")
        bad = [f for f in changed if not path_allowed(f, pats)]
        if bad:
            return Outcome("fail", f"archivos fuera de allowed_files: {bad[:5]}")
    if ttype == "implementation" and not commits:
        return Outcome("fail", "el agente termino sin producir cambios")
    if ttype != "implementation" and not commits and not res.stdout.strip():
        return Outcome("fail", "sin cambios ni respuesta del agente")

    if task["test_command"]:
        t = proc.run_cmd(task["test_command"], cwd=wt, timeout=cfg.test_timeout, shell=True)
        if t.returncode != 0:
            return Outcome("fail", f"test_command fallo ({t.returncode}): "
                                   f"{(t.stdout + t.stderr)[-500:]}")
    return Outcome("ok")


def save_log(cfg, task, attempt, res) -> str:
    d = cfg.logs_dir / "tasks"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"task-{task['id']}-a{attempt}.log"
    path.write_text(f"## STDOUT\n{res.stdout}\n\n## STDERR\n{res.stderr}\n", encoding="utf-8")
    return str(path)


def process_task(conn, cfg, task) -> None:
    tid = task["id"]
    ttype = task["task_type"]
    if ttype == "auto":
        ttype = classify_task(task["objective"])
        update_task(conn, tid, task_type=ttype)
    repo = cfg.target_repo
    log.info("Tarea %s [%s]: %s", tid, ttype, task["objective"][:80])

    wt = branch = None
    out_path = None
    try:
        if not gitops.repo_ready(repo):
            raise gitops.GitError(f"TARGET_REPO invalido o sin commits: {repo}")
        if task["branch_name"]:                       # resto de un intento anterior
            gitops.delete_branch(repo, task["branch_name"])
        head_before = gitops.head(repo)
        wt, branch, base = gitops.create_worktree(repo, cfg.worktrees_dir, tid)
        update_task(conn, tid, branch_name=branch, base_commit=base)
        res = run_agent(cfg, task, ttype, wt)
        out_path = save_log(cfg, task, task["retry_count"] + task["infra_failures"] + 1, res)
        outcome = evaluate(cfg, task, ttype, wt, base, res)
        if gitops.head(repo) != head_before:
            log.warning("Tarea %s: el HEAD del repo objetivo cambio durante la ejecucion "
                        "(commit externo o agente fuera del worktree)", tid)
    except gitops.GitError as e:
        outcome = Outcome("fail", str(e))
    finally:
        if wt is not None:
            gitops.remove_worktree(repo, wt)

    if outcome.kind == "ok":
        update_task(conn, tid, status="DONE", assigned_model=cfg.model, last_error=None,
                    output_path=out_path, not_before=None)
        log.info("  OK tarea %s -> rama %s", tid, branch)
        return
    gitops.delete_branch(repo, branch)
    if outcome.kind == "infra":
        n = task["infra_failures"] + 1
        wait = min(cfg.infra_backoff * n, 3600)
        update_task(conn, tid, status="PENDING", infra_failures=n, last_error=outcome.message[:2000],
                    output_path=out_path, not_before=later(wait))
        log.warning("  INFRA tarea %s: reintento en %ss (no consume reintentos)", tid, wait)
        return
    retries = task["retry_count"] + 1
    status = "FAILED" if retries > task["max_retries"] else "PENDING"
    update_task(conn, tid, status=status, retry_count=retries, last_error=outcome.message[:2000],
                output_path=out_path, not_before=None)
    log.warning("  FALLO tarea %s -> %s (%s)", tid, status, outcome.message[:120])


# ----------------------------------------------------------------- bucle
def _has_ready(conn) -> bool:
    return conn.execute("SELECT 1 FROM tasks WHERE status='PENDING' AND "
                        "(not_before IS NULL OR not_before<=?) LIMIT 1", (now(),)).fetchone() is not None


def _claim_next(conn):
    conn.execute("BEGIN IMMEDIATE")
    row = conn.execute("SELECT * FROM tasks WHERE status='PENDING' AND "
                       "(not_before IS NULL OR not_before<=?) "
                       "ORDER BY priority DESC, id ASC LIMIT 1", (now(),)).fetchone()
    if row:
        conn.execute("UPDATE tasks SET status='RUNNING', updated_at=? WHERE id=?", (now(), row["id"]))
    conn.commit()
    return row


def _acquire_lock(cfg) -> Path:
    cfg.run_dir.mkdir(parents=True, exist_ok=True)
    lock = cfg.run_dir / "supervisor.pid"
    other = proc.read_pid(lock)
    if other and other != os.getpid() and proc.pid_alive(other):
        raise SystemExit(f"Ya hay un supervisor en marcha (PID {other}).")
    lock.write_text(str(os.getpid()))
    return lock


def _on_term(signum, frame):
    raise KeyboardInterrupt


def run_supervisor(cfg, once: bool = False) -> None:
    setup_logging(cfg)
    lock = _acquire_lock(cfg)
    conn = init_db(cfg)
    recovered = conn.execute("UPDATE tasks SET status='PENDING', updated_at=? WHERE status='RUNNING'",
                             (now(),)).rowcount
    conn.commit()
    if recovered:
        log.warning("Recuperadas %s tareas que quedaron en RUNNING", recovered)
    try:
        signal.signal(signal.SIGTERM, _on_term)
    except (ValueError, OSError):
        pass
    log.info("Supervisor iniciado. modelo=%s router=%s repo=%s", cfg.model, cfg.router_url, cfg.target_repo)

    current = None
    wait = cfg.poll_interval
    try:
        while True:
            if not _has_ready(conn):
                if once:
                    break
                time.sleep(cfg.poll_interval)
                continue
            if cfg.require_router and not router_ok(cfg):
                log.warning("Router no responde (%s). Tareas en espera, sin consumir reintentos.", cfg.router_url)
                if once:
                    break
                services.start_all(cfg)               # vigilancia: intenta relanzar servicios caidos
                time.sleep(wait)
                wait = min(wait * 2, cfg.infra_backoff)
                continue
            wait = cfg.poll_interval
            task = _claim_next(conn)
            if not task:
                continue
            current = task["id"]
            try:
                process_task(conn, cfg, dict(task))
            except Exception as e:                    # el bucle NUNCA muere por una tarea
                log.exception("Error inesperado en tarea %s", current)
                retries = task["retry_count"] + 1
                update_task(conn, current, status="FAILED" if retries > task["max_retries"] else "PENDING",
                            retry_count=retries, last_error=f"error interno: {e}"[:2000])
            current = None
    except KeyboardInterrupt:
        log.info("Detenido por senal.")
        if current is not None:
            update_task(conn, current, status="PENDING", last_error="interrumpida por parada del supervisor")
    finally:
        conn.close()
        if proc.read_pid(lock) == os.getpid():
            lock.unlink(missing_ok=True)
