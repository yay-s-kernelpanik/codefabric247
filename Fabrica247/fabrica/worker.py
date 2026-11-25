"""Cliente worker de Fabrica247. Solo usa conexiones salientes HTTPS/HTTP."""
from __future__ import annotations

import json
import logging
import os
import platform
import secrets
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

from . import gitops, proc
from .config import _parse_dotenv, find_opencode
from .hub import stamp
from .supervisor import build_prompt, classify_task, evaluate, save_log, run_agent

log = logging.getLogger("fabrica.worker")


def default_worker_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "Fabrica247"


def _restrict(path: Path):
    if os.name != "nt":
        try: path.chmod(0o600)
        except OSError: pass


def _http_json(url, method="GET", token=None, data=None, timeout=15):
    body = None if data is None else json.dumps(data, ensure_ascii=False).encode("utf-8")
    headers = {"Accept": "application/json", "User-Agent": "Fabrica247-Worker/3.0"}
    if body is not None: headers["Content-Type"] = "application/json"
    if token: headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read(2_000_000)
            return json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read(4000).decode("utf-8", "replace")
        try: detail = json.loads(detail).get("error", detail)
        except Exception: pass
        raise RuntimeError(f"Hub respondió HTTP {e.code}: {detail}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise RuntimeError(f"No se pudo conectar al Hub: {e}") from e


def write_worker_config(reply: dict, hub_url: str, name: str, config_path: Path,
                        project_slug: str | None = None, repo_path: str | None = None,
                        allow_remote_code=False, allow_shell=False, accept_remote_control=False):
    cfg = {
        "hub_url": hub_url.rstrip("/"),
        "worker_id": reply["worker_id"],
        "worker_name": reply.get("worker_name", name),
        "projects": {},
        "agent": {
            "enabled": True,
            "command": find_opencode(),
            "model": "router/auto",
            "providers": [
                {"id": "router", "name": "Router OpenAI-compatible", "package": "@opencode/ai/providers/openai-compatible",
                 "base_url": "http://127.0.0.1:8787/v1", "api_key_env": "FABRICA_ROUTER_API_KEY",
                 "models": {"auto": {"name": "Modelo automático"}}}
            ],
            "task_timeout": 900,
            "allow_remote_code": bool(allow_remote_code),
            "allow_shell": bool(allow_shell)
        },
        "poll_seconds": 10,
        "heartbeat_seconds": 20,
        "remote_control": {"enabled": bool(accept_remote_control)}
    }
    if project_slug and repo_path:
        cfg["projects"][project_slug] = {"path": str(Path(repo_path).expanduser().resolve()), "enabled": True}
    config_path = config_path.expanduser().resolve()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        try: config_path.parent.chmod(0o700)
        except OSError: pass
    config_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    token_path = config_path.with_name("worker.token")
    token_path.write_text(reply["worker_token"] + "\n", encoding="utf-8")
    env_path = config_path.with_name(".worker.env")
    if not env_path.exists():
        env_path.write_text("# Claves privadas de proveedores; referencialas mediante api_key_env en worker.json.\n", encoding="utf-8")
    _restrict(config_path); _restrict(token_path); _restrict(env_path)
    print(f"Equipo registrado: {reply.get('worker_name', name)} (ID {reply['worker_id']})")
    print(f"Configuración: {config_path}")
    print(f"Token privado: {token_path}")
    if not allow_remote_code:
        print("Seguridad: ejecución de cambios remotos DESACTIVADA.")
    if not allow_shell:
        print("Seguridad: shell del agente DESACTIVADO.")
    if not accept_remote_control:
        print("Control remoto administrativo DESACTIVADO.")
    else:
        print("Control remoto aceptado: el Hub podrá pausar/reanudar y editar instrucciones del agente.")
    return config_path


def join_worker(hub_url: str, invite: str, name: str, config_path: Path,
                project_slug: str | None = None, repo_path: str | None = None,
                allow_remote_code=False, allow_shell=False, accept_remote_control=False):
    hub_url = hub_url.rstrip("/")
    if not hub_url.startswith(("http://", "https://")):
        raise ValueError("Hub URL debe empezar con http:// o https://")
    if bool(allow_shell) and not bool(allow_remote_code):
        raise ValueError("--allow-shell requiere también --allow-remote-code")
    if bool(project_slug) != bool(repo_path):
        raise ValueError("--project y --repo deben indicarse juntos")
    if hub_url.startswith("http://") and not any(host in hub_url for host in ("127.0.0.1", "localhost", "192.168.", "10.", "100.")):
        print("ADVERTENCIA: HTTP no cifra la conexión. Para PCs fuera de tu red usá HTTPS o una VPN privada.")
    reply = _http_json(hub_url + "/api/worker/enroll", "POST", data={"invite": invite, "name": name})
    config_path = write_worker_config(reply, hub_url, name, config_path, project_slug, repo_path,
                                      allow_remote_code, allow_shell, accept_remote_control)
    print("Siguiente paso: revisá worker.json, configurá providers/model y las rutas de proyectos.")
    return config_path


def load_worker(config_path: Path):
    config_path = config_path.expanduser().resolve()
    if not config_path.is_file():
        raise FileNotFoundError(f"No existe {config_path}. Ejecutá worker join primero.")
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    base = config_path.parent
    token_path = Path(cfg.get("token_file") or (base / "worker.token"))
    if not token_path.is_absolute(): token_path = base / token_path
    if not token_path.is_file(): raise FileNotFoundError(f"No existe el token: {token_path}")
    token = token_path.read_text(encoding="utf-8").strip()
    if not token: raise ValueError("Token de worker vacío")
    env_path = Path(cfg.get("env_file") or (base / ".worker.env"))
    if not env_path.is_absolute(): env_path = base / env_path
    for key, value in _parse_dotenv(env_path).items():
        os.environ.setdefault(key, value)
    if not cfg.get("hub_url", "").startswith(("http://", "https://")):
        raise ValueError("hub_url inválida")
    if not isinstance(cfg.get("projects", {}), dict):
        raise ValueError("projects debe ser un objeto")
    return config_path, cfg, token


def worker_capabilities(cfg):
    agent = cfg.get("agent", {})
    if not agent.get("enabled", False): return []
    caps = ["reasoning", "light"]
    if agent.get("allow_remote_code", False): caps.append("implementation")
    return caps


def make_opencode_config(cfg, worker_dir: Path, task_type: str):
    """Generate an isolated OpenCode V2 config for one task and its local consent."""
    agent = cfg.get("agent", {})
    providers = {}
    for item in agent.get("providers", []):
        pid = str(item.get("id", "")).strip()
        if not pid:
            continue
        provider = {
            "name": item.get("name", pid),
            # `npm` is accepted as a migration alias for worker.json files made by v2.
            "package": item.get("package") or item.get("npm") or "@opencode/ai/providers/openai-compatible",
            "settings": {"baseURL": str(item.get("base_url") or item.get("baseURL") or "")},
            "models": item.get("models", {"auto": {"name": "Auto"}}),
        }
        env_key = str(item.get("api_key_env") or "").strip()
        if env_key:
            provider["env"] = [env_key]
        providers[pid] = provider
    if not providers:
        raise RuntimeError("No hay proveedores configurados en agent.providers")
    model = str(agent.get("model", ""))
    if "/" not in model or model.split("/", 1)[0] not in providers:
        raise RuntimeError("agent.model debe tener formato proveedor/modelo y coincidir con agent.providers")

    allow_edit = bool(agent.get("allow_remote_code", False)) and task_type != "reasoning"
    allow_shell = bool(agent.get("allow_shell", False)) and allow_edit
    # OpenCode V2 usa `permissions` (no el antiguo `permission` ni `bash`).
    # Se niega el acceso fuera del worktree y se protegen archivos .env.
    permissions = [
        {"action": "*", "resource": "*", "effect": "allow"},
        {"action": "external_directory", "resource": "*", "effect": "deny"},
        {"action": "edit", "resource": "*", "effect": "allow" if allow_edit else "deny"},
        {"action": "shell", "resource": "*", "effect": "allow" if allow_shell else "deny"},
        {"action": "read", "resource": "*.env", "effect": "deny"},
        {"action": "read", "resource": "*.env.*", "effect": "deny"},
        {"action": "edit", "resource": "*.env", "effect": "deny"},
        {"action": "edit", "resource": "*.env.*", "effect": "deny"},
    ]
    conf = {
        "$schema": "https://opencode.ai/config.json",
        "model": model,
        "providers": providers,
        "permissions": permissions,
    }
    dest = worker_dir / "config" / f"opencode-{task_type}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(conf, ensure_ascii=False, indent=2), encoding="utf-8")
    _restrict(dest)
    return dest


class Worker:
    def __init__(self, config_path: Path):
        self.config_path, self.cfg, self.token = load_worker(config_path)
        self.home = self.config_path.parent
        self.hub = self.cfg["hub_url"].rstrip("/")
        self.projects = {slug: item for slug, item in self.cfg.get("projects", {}).items()
                         if item.get("enabled", True) and item.get("path")}
        self.capabilities = worker_capabilities(self.cfg)
        self.current_task = None
        self.task_cancel_event = threading.Event()
        self.stop_event = threading.Event()
        self.remote_control_enabled = bool(self.cfg.get("remote_control", {}).get("enabled", False))
        self.server_control = {"desired_state": "RUNNING", "worker_prompt": ""}

    def request(self, endpoint, method="POST", data=None, timeout=20):
        return _http_json(self.hub + endpoint, method, self.token, data, timeout)

    def heartbeat(self):
        reply = self.request("/api/worker/heartbeat", data={
            "projects": list(self.projects), "capabilities": self.capabilities,
            "current_task_id": self.current_task, "platform": platform.platform(),
            "version": "3.0.0", "agent": self.cfg.get("agent", {}).get("model", "disabled"),
            "cpu": platform.processor(), "cores": os.cpu_count() or 0,
            "remote_control": self.remote_control_enabled
        })
        if self.remote_control_enabled:
            if self.current_task is not None and reply.get("cancel_current_task"):
                self.task_cancel_event.set()
            state = str(reply.get("desired_state", "RUNNING")).upper()
            self.server_control = {
                "desired_state": state if state in ("RUNNING", "PAUSED") else "PAUSED",
                "worker_prompt": str(reply.get("worker_prompt", ""))[:8000]
            }
        else:
            self.server_control = {"desired_state": "RUNNING", "worker_prompt": ""}
        return reply

    def _heartbeat_loop(self):
        interval = max(5, int(self.cfg.get("heartbeat_seconds", 20)))
        while not self.stop_event.wait(interval):
            try: self.heartbeat()
            except Exception as exc: log.warning("Heartbeat: %s", exc)

    def run_task(self, task):
        slug = task["project_slug"]
        project_cfg = self.projects.get(slug)
        if not project_cfg:
            return {"outcome": "fail", "error": f"No hay ruta local configurada para el proyecto {slug}"}
        repo = Path(project_cfg["path"]).expanduser().resolve()
        task_type = task.get("task_type", "implementation")
        if task_type == "auto": task_type = classify_task(task["objective"])
        agent = self.cfg.get("agent", {})
        if task_type == "implementation" and not agent.get("allow_remote_code", False):
            return {"outcome": "fail", "error": "Este equipo no habilitó la ejecución remota de cambios"}
        if not gitops.repo_ready(repo):
            return {"outcome": "fail", "error": f"Repo local inválido o sin commits: {repo}"}
        if not agent.get("enabled", False):
            return {"outcome": "fail", "error": "Agente local deshabilitado"}
        command = str(agent.get("command") or find_opencode())
        if not (proc.resolve_exe(command) and (proc.resolve_exe(command) != command or Path(command).exists())):
            return {"outcome": "fail", "error": f"No se encontró el ejecutable del agente: {command}"}
        worker_dir = self.home
        logs_dir = worker_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        wt_root = worker_dir / "worktrees" / slug
        wt = branch = None
        outcome = None
        succeeded = False
        try:
            wt, branch, base = gitops.create_worktree(repo, wt_root, int(task["id"]))
            config_file = make_opencode_config(self.cfg, worker_dir, task_type)
            safe_task = dict(task)
            safe_task["task_type"] = task_type
            safe_task["test_command"] = None  # El Hub no envía shell commands a PCs participantes.
            safe_task["last_error"] = task.get("last_error") or ""
            safe_task["task_prompt"] = task.get("task_prompt") or ""
            safe_task["project_prompt"] = task.get("project_prompt") or ""
            safe_task["worker_prompt"] = self.server_control.get("worker_prompt", "") if self.remote_control_enabled else ""
            safe_task["local_prompt"] = str(agent.get("local_prompt", ""))[:8000]
            safe_task.setdefault("retry_count", max(0, int(task.get("attempts", 1)) - 1))
            run_cfg = SimpleNamespace(
                opencode_bin=command, opencode_config=config_file,
                model=agent.get("model", ""), allow_all=False,
                task_timeout=max(30, min(7200, int(agent.get("task_timeout", 900)))),
                test_timeout=1, require_router=False,
                logs_dir=logs_dir
            )
            result = run_agent(run_cfg, safe_task, task_type, wt, cancel_event=self.task_cancel_event)
            log_path = save_log(SimpleNamespace(logs_dir=logs_dir), safe_task, int(task.get("attempts", 1)), result)
            if result.returncode == -2:
                return {"outcome": "cancelled", "error": "Agente detenido por solicitud remota autorizada.",
                        "result": result.stdout[-4000:]}
            outcome = evaluate(run_cfg, safe_task, task_type, wt, base, result)
            if outcome.kind == "ok":
                succeeded = True
                patch = gitops.git(["diff", "--binary", f"{base}..HEAD"], wt, timeout=180).stdout
                if len(patch.encode("utf-8")) > 3_500_000:
                    patch = ""
                    patch_note = " El diff supera 3.5 MB; revisá/pusheá la rama local manualmente."
                else:
                    patch_note = " Patch enviado al Hub para descargar y aplicar."
                return {"outcome": "done", "branch_name": branch, "patch": patch,
                        "result": f"Tarea completada. Rama local: {branch}. Log: {log_path}.{patch_note}\n{result.stdout[-6000:]}"}
            if outcome.kind == "infra":
                return {"outcome": "infra", "error": outcome.message, "result": result.stdout[-4000:]}
            return {"outcome": "fail", "error": outcome.message, "result": result.stdout[-4000:]}
        except Exception as exc:
            log.exception("Error procesando tarea %s", task.get("id"))
            return {"outcome": "fail", "error": str(exc)[:2500]}
        finally:
            if wt is not None:
                try: gitops.remove_worktree(repo, wt)
                except Exception: log.exception("No se pudo limpiar el worktree %s", wt)
            if branch and not succeeded:
                gitops.delete_branch(repo, branch)

    def run(self, once=False):
        if not self.capabilities:
            raise RuntimeError("Agente deshabilitado. Configurá agent.enabled=true para registrar capacidad.")
        if not self.projects:
            raise RuntimeError("No hay proyectos mapeados en worker.json. Configurá projects.<slug>.path.")
        agent = self.cfg.get("agent", {})
        command = str(agent.get("command") or find_opencode())
        if not (proc.resolve_exe(command) and (proc.resolve_exe(command) != command or Path(command).exists())):
            raise RuntimeError(f"No se encontró el ejecutable del agente: {command}. Instalá OpenCode y revisá agent.command.")
        # Valida proveedor/modelo antes de reclamar tareas.
        make_opencode_config(self.cfg, self.home, "reasoning")
        self.heartbeat()
        thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        thread.start()
        print(f"Worker {self.cfg.get('worker_name')} conectado a {self.hub}")
        print(f"Proyectos: {', '.join(self.projects)} | capacidades: {', '.join(self.capabilities)}")
        poll = max(3, int(self.cfg.get("poll_seconds", 10)))
        try:
            while not self.stop_event.is_set():
                self.current_task = None
                try:
                    self.heartbeat()
                    if self.remote_control_enabled and self.server_control.get("desired_state") == "PAUSED":
                        if once: break
                        self.stop_event.wait(poll)
                        continue
                    claim = self.request("/api/worker/claim", data={
                        "projects": list(self.projects), "capabilities": self.capabilities
                    })
                    task = claim.get("task")
                    if not task:
                        if once: break
                        self.stop_event.wait(poll); continue
                    self.current_task = int(task["id"])
                    self.task_cancel_event.clear()
                    print(f"\n[Tarea {task['id']}] {task['project_slug']}: {task['objective'][:100]}")
                    self.heartbeat()
                    result = self.run_task(task)
                    self.request(f"/api/worker/tasks/{task['id']}/result", data=result)
                    print(f"[Tarea {task['id']}] {result['outcome']}")
                    self.current_task = None
                    if once: break
                except KeyboardInterrupt:
                    raise
                except Exception as exc:
                    log.warning("Worker: %s", exc)
                    if once: raise
                    self.stop_event.wait(poll)
        except KeyboardInterrupt:
            print("\nParada solicitada por el usuario.")
        finally:
            self.stop_event.set()
            try: self.heartbeat()
            except Exception: pass
