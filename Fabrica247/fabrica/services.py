"""Servicios auxiliares (router, proxies, ollama...) definidos en services.json."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from . import proc
from .health import http_ok, wait_http

log = logging.getLogger("fabrica")


def _x(value):
    return os.path.expandvars(os.path.expanduser(value)) if isinstance(value, str) else value


def load_services(cfg) -> list:
    for name in ("services.local.json", "services.json"):
        path = cfg.home / name
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            return [s for s in data.get("services", [])]
    return []


def enabled_services(cfg) -> list:
    return [s for s in load_services(cfg) if s.get("enabled", False)]


def _pidfile(cfg, name):
    return cfg.run_dir / f"svc-{name}.pid"


def start_service(cfg, svc) -> bool:
    name = svc["name"]
    url = _x(svc.get("health_url"))
    timeout = float(svc.get("health_timeout", 60))
    if url and http_ok(url, timeout=3):
        log.info("[%s] ya responde en %s", name, url)
        return True
    pidfile = _pidfile(cfg, name)
    pid = proc.read_pid(pidfile)
    if not (pid and proc.pid_alive(pid)):
        cmd = svc["command"]
        cmd = _x(cmd) if isinstance(cmd, str) else [_x(c) for c in cmd]
        cwd = _x(svc.get("cwd")) or str(cfg.home)
        env = os.environ.copy()
        env.update({k: _x(v) for k, v in svc.get("env", {}).items()})
        pid = proc.spawn_detached(cmd, cwd, env, cfg.logs_dir / f"{name}.log")
        cfg.run_dir.mkdir(parents=True, exist_ok=True)
        pidfile.write_text(str(pid))
        log.info("[%s] lanzado (PID %s), log: logs/%s.log", name, pid, name)
    if url:
        ok = wait_http(url, timeout)
    else:
        import time
        time.sleep(2)
        ok = proc.pid_alive(pid)
    log.info("[%s] %s", name, "listo" if ok else "NO respondio a tiempo")
    return ok


def start_all(cfg) -> bool:
    """Arranca los servicios habilitados. False si falla alguno marcado required."""
    all_ok = True
    for svc in enabled_services(cfg):
        ok = start_service(cfg, svc)
        if not ok and svc.get("required", True):
            all_ok = False
    return all_ok


def stop_all(cfg) -> None:
    for svc in reversed(load_services(cfg)):
        pidfile = _pidfile(cfg, svc["name"])
        pid = proc.read_pid(pidfile)
        if pid and proc.pid_alive(pid):
            proc.terminate_tree(pid)
            log.info("[%s] detenido (PID %s)", svc["name"], pid)
        pidfile.unlink(missing_ok=True)


def install_all(cfg) -> None:
    """Clona y ejecuta los comandos 'install' de los servicios habilitados."""
    from .gitops import git
    for svc in enabled_services(cfg):
        inst = svc.get("install")
        if not inst:
            continue
        target = Path(_x(inst.get("dir") or svc.get("cwd"))).resolve()
        if inst.get("repo") and not target.exists():
            print(f"[{svc['name']}] clonando {inst['repo']} -> {target}")
            git(["clone", inst["repo"], str(target)], cfg.home)
        for command in inst.get("commands", []):
            print(f"[{svc['name']}] $ {command}")
            r = proc.run_cmd(_x(command), cwd=target, shell=True, timeout=1800)
            if r.returncode != 0:
                print(f"  ERROR ({r.returncode}): {r.stderr.strip()[-500:]}")
                break
