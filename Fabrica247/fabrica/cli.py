"""CLI unica y multiplataforma:  python -m fabrica <comando>"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import os
from pathlib import Path

from . import __version__, gitops, proc, services
from .config import BASE_DIR, load_settings
from .db import add_task, init_db, update_task
from .health import http_ok, router_ok
from .supervisor import classify_task, run_supervisor, setup_logging

MIN_PY = (3, 9)


def write_opencode_config(cfg) -> None:
    provider, _, model_id = cfg.model.partition("/")
    if not model_id:
        provider, model_id = "hyperrouter", cfg.model
    permissions = [
        {"action": "*", "resource": "*", "effect": "allow"},
        {"action": "external_directory", "resource": "*", "effect": "deny"},
        {"action": "read", "resource": "*.env", "effect": "deny"},
        {"action": "read", "resource": "*.env.*", "effect": "deny"},
        {"action": "edit", "resource": "*", "effect": "allow" if cfg.allow_all else "deny"},
        {"action": "shell", "resource": "*", "effect": "allow" if cfg.allow_all else "deny"},
        {"action": "edit", "resource": "*.env", "effect": "deny"},
        {"action": "edit", "resource": "*.env.*", "effect": "deny"},
    ]
    conf = {
        "$schema": "https://opencode.ai/config.json",
        "model": f"{provider}/{model_id}",
        "providers": {provider: {
            "name": "Fabrica247 Router",
            "package": "@opencode/ai/providers/openai-compatible",
            "env": ["FABRICA247_ROUTER_API_KEY"],
            "settings": {"baseURL": cfg.router_url, "apiKey": "{env:FABRICA247_ROUTER_API_KEY}"},
            "models": {model_id: {"name": model_id}},
        }},
        "permissions": permissions,
    }
    cfg.opencode_config.parent.mkdir(parents=True, exist_ok=True)
    cfg.opencode_config.write_text(json.dumps(conf, indent=2), encoding="utf-8")
    if os.name != "nt":
        try: cfg.opencode_config.chmod(0o600)
        except OSError: pass


def init_project(cfg) -> None:
    for d in (cfg.logs_dir, cfg.run_dir, cfg.worktrees_dir):
        d.mkdir(parents=True, exist_ok=True)
    env_file = cfg.home / ".env"
    example = BASE_DIR / ".env.example"
    if not env_file.exists() and example.exists():
        shutil.copy(example, env_file)
        print(f"Creado {env_file}  <- editalo (TARGET_REPO es obligatorio)")
    if os.name != "nt" and env_file.exists():
        try: env_file.chmod(0o600)
        except OSError: pass
    init_db(cfg).close()
    write_opencode_config(cfg)


def cmd_init(args, cfg):
    init_project(cfg)
    cfg = load_settings()
    print(f"Listo. DB: {cfg.db_path}\nConfig de OpenCode: {cfg.opencode_config}")
    if not cfg.target_repo:
        print("AVISO: define TARGET_REPO en .env (repo git sobre el que trabajaran los agentes).")


def cmd_doctor(args, cfg):
    bad = 0

    def line(ok, msg, fatal=True):
        nonlocal bad
        print(("[ OK ] " if ok else ("[FALLO] " if fatal else "[AVISO] ")) + msg)
        if not ok and fatal:
            bad += 1

    line(sys.version_info >= MIN_PY, f"Python {sys.version.split()[0]} (minimo {MIN_PY[0]}.{MIN_PY[1]})")
    line(shutil.which("git") is not None, "git instalado")
    import os
    oc_ok = bool(shutil.which(cfg.opencode_bin)) or os.path.isfile(cfg.opencode_bin)
    line(oc_ok, f"opencode encontrado ({cfg.opencode_bin})")
    line(bool(cfg.target_repo), "TARGET_REPO definido en .env")
    if cfg.target_repo:
        line(gitops.repo_ready(cfg.target_repo), f"TARGET_REPO es un repo git con commits ({cfg.target_repo})")
    line(cfg.opencode_config.is_file(), f"config de OpenCode generada ({cfg.opencode_config.name})")
    line(router_ok(cfg), f"router responde en {cfg.router_url}/models", fatal=False)
    for s in services.enabled_services(cfg):
        if s.get("health_url"):
            line(http_ok(s["health_url"]), f"servicio {s['name']} responde", fatal=False)
    sys.exit(1 if bad else 0)


def cmd_add(args, cfg):
    conn = init_db(cfg)
    ttype = args.type
    tid = add_task(conn, args.objective, ttype, args.files, args.test, args.priority, args.retries)
    print(f"Tarea {tid} creada (tipo: {ttype if ttype != 'auto' else 'auto -> ' + classify_task(args.objective)}).")


def cmd_list(args, cfg):
    conn = init_db(cfg)
    q, params = "SELECT * FROM tasks", []
    if args.status:
        q += " WHERE status=?"
        params.append(args.status.upper())
    q += " ORDER BY id DESC LIMIT ?"
    params.append(args.limit)
    print(f"{'ID':>4}  {'ESTADO':<10} {'TIPO':<15} {'REINT':>5}  OBJETIVO")
    for r in conn.execute(q, params):
        print(f"{r['id']:>4}  {r['status']:<10} {r['task_type']:<15} {r['retry_count']:>2}/{r['max_retries']:<2}  "
              f"{r['objective'][:70]}")


def cmd_show(args, cfg):
    conn = init_db(cfg)
    r = conn.execute("SELECT * FROM tasks WHERE id=?", (args.id,)).fetchone()
    if not r:
        sys.exit("No existe esa tarea.")
    for k in r.keys():
        print(f"{k:>15}: {r[k]}")


def cmd_retry(args, cfg):
    conn = init_db(cfg)
    update_task(conn, args.id, status="PENDING", retry_count=0, infra_failures=0, not_before=None)
    print(f"Tarea {args.id} devuelta a PENDING.")


def cmd_cancel(args, cfg):
    conn = init_db(cfg)
    update_task(conn, args.id, status="CANCELLED")
    print(f"Tarea {args.id} cancelada (si ya esta RUNNING terminara su intento actual).")


def cmd_run(args, cfg):
    run_supervisor(cfg, once=args.once)


def cmd_start(args, cfg):
    init_project(cfg)
    cfg = load_settings()
    setup_logging(cfg, console=not args.detach)
    if not args.no_services and not services.start_all(cfg):
        sys.exit("Un servicio 'required' no arranco. Revisa logs/<servicio>.log")
    if args.detach:
        pid = proc.spawn_detached([sys.executable, "-m", "fabrica", "run"], BASE_DIR, None,
                                  cfg.logs_dir / "supervisor.out")
        print(f"Supervisor en segundo plano (PID {pid}). Log: logs/supervisor.log")
    else:
        run_supervisor(cfg)


def cmd_stop(args, cfg):
    pid = proc.read_pid(cfg.run_dir / "supervisor.pid")
    if pid and proc.pid_alive(pid):
        proc.terminate_tree(pid, grace=10)
        print(f"Supervisor detenido (PID {pid}).")
    else:
        print("El supervisor no estaba en marcha.")
    if not args.keep_services:
        setup_logging(cfg)
        services.stop_all(cfg)
    conn = init_db(cfg)
    n = conn.execute("UPDATE tasks SET status='PENDING' WHERE status='RUNNING'").rowcount
    conn.commit()
    if n:
        print(f"{n} tarea(s) en RUNNING devueltas a PENDING.")


def cmd_status(args, cfg):
    pid = proc.read_pid(cfg.run_dir / "supervisor.pid")
    print(f"Supervisor : {'en marcha (PID %s)' % pid if pid and proc.pid_alive(pid) else 'detenido'}")
    print(f"Router     : {'OK' if router_ok(cfg) else 'NO responde'}  ({cfg.router_url})")
    for s in services.load_services(cfg):
        spid = proc.read_pid(cfg.run_dir / f"svc-{s['name']}.pid")
        h = http_ok(s["health_url"]) if s.get("health_url") else None
        print(f"Servicio {s['name']:<12}: {'habilitado' if s.get('enabled') else 'deshabilitado'}"
              f", pid={spid or '-'}, salud={h}")
    conn = init_db(cfg)
    counts = {r[0]: r[1] for r in conn.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status")}
    print("Tareas     : " + (", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "ninguna"))


def cmd_install_services(args, cfg):
    services.install_all(cfg)



def cmd_setup(args, cfg):
    from .setup import run_setup
    run_setup(args.edition, cfg)


def cmd_hub_init(args, cfg):
    from .hub import init_hub
    db_path, password = init_hub(cfg.home)
    print("Hub inicializado.")
    print(f"Base de datos: {db_path}")
    print(f"Contraseña de administrador (guardada con permisos privados): {db_path.parent / 'admin_password.txt'}")
    print("Copiala/consultala localmente. No la compartas ni la publiques.")
    print("Luego ejecutá: python -m fabrica hub serve --host 0.0.0.0")


def cmd_hub_serve(args, cfg):
    from .hub import serve_hub
    serve_hub(cfg.home, host=args.host, port=args.port)


def cmd_worker_join(args, cfg):
    from .worker import default_worker_dir, join_worker
    if args.allow_shell and not args.allow_remote_code:
        raise SystemExit("--allow-shell requiere también --allow-remote-code")
    if bool(args.project) != bool(args.repo):
        raise SystemExit("--project y --repo deben indicarse juntos")
    config_path = Path(args.config).expanduser() if args.config else default_worker_dir() / "worker.json"
    join_worker(args.hub, args.invite, args.name, config_path,
                project_slug=args.project, repo_path=args.repo,
                allow_remote_code=args.allow_remote_code, allow_shell=args.allow_shell,
                accept_remote_control=args.accept_remote_control)


def cmd_worker_run(args, cfg):
    from .worker import Worker
    worker = Worker(Path(args.config))
    worker.run(once=args.once)


def cmd_worker_doctor(args, cfg):
    from .worker import Worker
    worker = Worker(Path(args.config))
    print(f"Worker: {worker.cfg.get('worker_name')} ({worker.cfg.get('worker_id')})")
    print(f"Hub: {worker.hub}")
    agent = worker.cfg.get("agent", {})
    print(f"Agente: {'habilitado' if agent.get('enabled') else 'deshabilitado'}")
    if agent.get("enabled"):
        import shutil as _shutil
        executable = str(agent.get("command") or __import__("fabrica.config", fromlist=["find_opencode"]).find_opencode())
        found = _shutil.which(executable) or (executable if Path(executable).is_file() else None)
        print(f"OpenCode: {'OK' if found else 'FALTA'} ({executable})")
        print(f"Modelo: {agent.get('model', 'sin configurar')}")
    print(f"Capacidades: {', '.join(worker.capabilities) or 'ninguna'}")
    for slug, item in worker.projects.items():
        from .gitops import repo_ready
        repo = Path(item['path']).expanduser()
        print(f"Proyecto {slug}: {'OK' if repo_ready(repo) else 'REVISAR'} ({repo})")
    reply = worker.heartbeat()
    print(f"Conexión con Hub: {'OK' if reply.get('ok') else 'ERROR'}")


def build_parser():
    p = argparse.ArgumentParser(prog="fabrica", description=f"Fabrica247 v{__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_):
        sp = sub.add_parser(name, help=help_)
        sp.set_defaults(fn=fn)
        return sp

    add("init", cmd_init, "crea .env, carpetas, DB y config de OpenCode")
    add("doctor", cmd_doctor, "diagnostico completo del entorno")
    a = add("add", cmd_add, "encola una tarea")
    a.add_argument("objective")
    a.add_argument("--type", choices=["auto", "implementation", "reasoning", "light"], default="auto")
    a.add_argument("--files", help="rutas permitidas, separadas por coma (prefijo con / final o glob)")
    a.add_argument("--test", help="comando de validacion (se ejecuta en el worktree)")
    a.add_argument("--priority", type=int, default=0)
    a.add_argument("--retries", type=int, default=2, help="reintentos tras el primer intento")
    l = add("list", cmd_list, "lista tareas")
    l.add_argument("--status")
    l.add_argument("--limit", type=int, default=30)
    add("show", cmd_show, "detalle de una tarea").add_argument("id", type=int)
    add("retry", cmd_retry, "reencola una tarea").add_argument("id", type=int)
    add("cancel", cmd_cancel, "cancela una tarea").add_argument("id", type=int)
    r = add("run", cmd_run, "solo el supervisor (sin servicios)")
    r.add_argument("--once", action="store_true", help="procesa lo pendiente y termina")
    s = add("start", cmd_start, "servicios + supervisor")
    s.add_argument("--detach", action="store_true", help="supervisor en segundo plano")
    s.add_argument("--no-services", action="store_true")
    t = add("stop", cmd_stop, "detiene supervisor y servicios")
    t.add_argument("--keep-services", action="store_true")
    add("status", cmd_status, "estado general")
    add("install-services", cmd_install_services, "instala servicios habilitados en services.json")
    setup = add("setup", cmd_setup, "asistente de instalación guiada para las ediciones de Fabrica247")
    setup.add_argument("--edition", choices=["windows", "linux", "windows-lite", "linux-lite", "windows-heavy", "linux-heavy", "mother", "hub"])

    hub = sub.add_parser("hub", help="servidor central y dashboard web")
    hub_sub = hub.add_subparsers(dest="hub_cmd", required=True)
    hi = hub_sub.add_parser("init", help="inicializa base de datos y contraseña de administrador")
    hi.set_defaults(fn=cmd_hub_init)
    hs = hub_sub.add_parser("serve", help="inicia el dashboard y la API central")
    hs.add_argument("--host", default=os.environ.get("FABRICA_HUB_HOST", "127.0.0.1"))
    hs.add_argument("--port", type=int, default=int(os.environ.get("FABRICA_HUB_PORT", "8765")))
    hs.set_defaults(fn=cmd_hub_serve)

    worker = sub.add_parser("worker", help="registrar y ejecutar un worker remoto")
    worker_sub = worker.add_subparsers(dest="worker_cmd", required=True)
    wj = worker_sub.add_parser("join", help="registrar esta PC con una invitación del Hub")
    wj.add_argument("--hub", required=True)
    wj.add_argument("--invite", required=True)
    wj.add_argument("--name", default=__import__("platform").node())
    wj.add_argument("--config")
    wj.add_argument("--project", help="slug del proyecto a mapear opcionalmente")
    wj.add_argument("--repo", help="ruta local del repositorio para --project")
    wj.add_argument("--allow-remote-code", action="store_true", help="consiente tareas que modifican código")
    wj.add_argument("--allow-shell", action="store_true", help="consiente al agente ejecutar comandos de shell")
    wj.add_argument("--accept-remote-control", action="store_true",
                    help="permite que el Hub pause/reanude este worker y edite sus instrucciones")
    wj.set_defaults(fn=cmd_worker_join)
    wr = worker_sub.add_parser("run", help="conecta y procesa tareas continuamente")
    wr.add_argument("--config", default=str(__import__("fabrica.worker", fromlist=["default_worker_dir"]).default_worker_dir() / "worker.json"))
    wr.add_argument("--once", action="store_true")
    wr.set_defaults(fn=cmd_worker_run)
    wd = worker_sub.add_parser("doctor", help="comprueba configuración y conexión del worker")
    wd.add_argument("--config", default=str(__import__("fabrica.worker", fromlist=["default_worker_dir"]).default_worker_dir() / "worker.json"))
    wd.set_defaults(fn=cmd_worker_doctor)
    return p


def main(argv=None):
    if sys.version_info < MIN_PY:
        sys.exit(f"Se requiere Python {MIN_PY[0]}.{MIN_PY[1]}+")
    args = build_parser().parse_args(argv)
    try:
        args.fn(args, load_settings())
    except KeyboardInterrupt:
        sys.exit(130)
