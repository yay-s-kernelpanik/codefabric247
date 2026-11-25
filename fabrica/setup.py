"""Asistente de instalación guiada de Fabrica247. No instala software de terceros."""
from __future__ import annotations

import getpass
import json
import os
import platform
import re
import shutil
import sys
from pathlib import Path

from .config import BASE_DIR


def _ask(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def _yes(label: str, default: bool = False) -> bool:
    suffix = "S/n" if default else "s/N"
    value = input(f"{label} ({suffix}): ").strip().lower()
    return default if not value else value in ("s", "si", "sí", "y", "yes")


def _slug(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9-]+", "-", value)
    return re.sub(r"-+", "-", value).strip("-")[:48]


def _write_profile(config_path: Path, edition: str, model: str, provider: dict):
    doc = json.loads(config_path.read_text(encoding="utf-8"))
    agent = doc.setdefault("agent", {})
    agent["model"] = model
    agent["providers"] = [provider]
    agent.setdefault("local_prompt", "")
    doc["edition"] = edition
    config_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if os.name != "nt":
        try: config_path.chmod(0o600)
        except OSError: pass


def _provider_for(edition: str) -> tuple[str, dict]:
    heavy = edition.endswith("-heavy")
    if heavy:
        model_id = _ask("Modelo Ollama ya instalado (ejemplo: qwen2.5-coder:3b)", "qwen2.5-coder:3b")
        provider = {
            "id": "ollama", "name": "Ollama local", "package": "@opencode/ai/providers/openai-compatible",
            "base_url": _ask("URL OpenAI-compatible de Ollama", "http://127.0.0.1:11434/v1"),
            "api_key_env": "", "models": {model_id: {"name": model_id}}
        }
        return f"ollama/{model_id}", provider
    base_url = _ask("URL base del router/API OpenAI-compatible", "http://127.0.0.1:8787/v1").rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        raise SystemExit("La URL base debe empezar con http:// o https://")
    provider_id = _ask("Identificador del proveedor", "router")
    provider_id = re.sub(r"[^a-zA-Z0-9_-]", "", provider_id) or "router"
    model_id = _ask("Identificador del modelo que acepta ese endpoint", "auto")
    key_env = _ask("Variable de entorno para la API key (escribí 'ninguna' si no usa clave)", "FABRICA_ROUTER_API_KEY")
    if key_env.lower() in ("ninguna", "ninguno", "-", "no"):
        key_env = ""
    if key_env and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key_env):
        raise SystemExit("Nombre de variable de entorno no válido.")
    provider = {
        "id": provider_id, "name": _ask("Nombre visible del proveedor", "Router / OpenCode / Freebuff / Kiro Gateway"),
        "package": "@opencode/ai/providers/openai-compatible", "base_url": base_url,
        "api_key_env": key_env,
        "models": {model_id: {"name": model_id}}
    }
    return f"{provider_id}/{model_id}", provider


def _require_git():
    if not shutil.which("git"):
        raise SystemExit("No se encontró Git. Instalá Git desde https://git-scm.com/downloads y volvé a ejecutar el instalador.")


def _write_provider_secret(provider: dict, config_path: Path):
    env_key = str(provider.get("api_key_env") or "").strip()
    if not env_key:
        print("Este proveedor no requiere una API key.")
        return
    from .config import _parse_dotenv
    env_path = config_path.with_name(".worker.env")
    current = _parse_dotenv(env_path)
    if current.get(env_key) and current[env_key] != "PEGAR_CLAVE_LOCALMENTE":
        print(f"La variable {env_key} ya está configurada en {env_path}.")
        return
    print("La API key se guardará únicamente en esta PC y no se mostrará en pantalla.")
    try:
        secret = getpass.getpass("Pegá la API key (Enter para configurarla después): ").strip()
    except (EOFError, OSError):
        secret = ""
    if "\n" in secret or "\r" in secret:
        raise SystemExit("La API key debe ser una sola línea.")
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    lines = [line for line in lines if not line.strip().startswith(env_key + "=")]
    if secret:
        lines.append(f"{env_key}={secret}")
        print("API key guardada en el archivo privado local.")
    else:
        lines.extend([f"# Clave privada del proveedor {provider.get('id', 'API')}",
                      f"{env_key}=PEGAR_CLAVE_LOCALMENTE"])
        print(f"Podés completar {env_path} después; buscá la variable {env_key}.")
    env_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    if os.name != "nt":
        try: env_path.chmod(0o600)
        except OSError: pass


def _install_worker(edition: str, hub_url: str | None = None, invite: str | None = None,
                   project: str | None = None, repo: str | None = None,
                   local_admin: bool = False):
    from .worker import default_worker_dir, join_worker
    print("\n=== Fabrica247 · instalación de worker ===")
    print(f"Edición: {edition}")
    _require_git()
    hub_url = hub_url or _ask("Dirección del Hub (URL Tailscale/VPN o HTTPS)", "http://127.0.0.1:8765")
    invite = invite or _ask("Código de invitación de un solo uso")
    if not invite:
        raise SystemExit("Falta el código de invitación. Pedíselo al administrador del Hub.")
    name = _ask("Nombre para identificar esta PC", platform.node() or "Fabrica-worker")
    project = project or _ask("ID/slug del proyecto (debe coincidir con el Hub)")
    repo = repo or _ask("Ruta local del repositorio Git (dejá vacío para clonarlo desde una URL)")
    if not project:
        raise SystemExit("Se necesita el slug del proyecto.")
    import subprocess
    if repo:
        repo_path = Path(repo).expanduser()
        if not repo_path.exists() or not repo_path.is_dir():
            raise SystemExit(f"La carpeta del repositorio no existe: {repo_path}")
        git_check = subprocess.run(["git", "-C", str(repo_path), "rev-parse", "--is-inside-work-tree"],
                                   capture_output=True, text=True)
        if git_check.returncode != 0:
            raise SystemExit("La carpeta indicada no es un repositorio Git válido.")
    else:
        clone_url = _ask("URL Git del proyecto (el dueño debe autorizar el acceso)")
        if not clone_url:
            raise SystemExit("Falta la URL del repositorio Git.")
        clone_root = default_worker_dir() / "projects"
        clone_root.mkdir(parents=True, exist_ok=True)
        repo_path = clone_root / _slug(project)
        if repo_path.exists():
            raise SystemExit(f"Ya existe {repo_path}; indicá esa ruta como repositorio local.")
        print(f"Clonando el repositorio en {repo_path}...")
        try:
            subprocess.run(["git", "clone", clone_url, str(repo_path)], check=True)
        except subprocess.CalledProcessError as exc:
            raise SystemExit("No se pudo clonar. Verificá la URL y los permisos del repositorio.") from exc
    repo = str(repo_path)
    allow_code = local_admin or _yes("¿Aceptar tareas que modifiquen código en este repositorio?", False)
    remote_control = local_admin or _yes("¿Permitir al administrador pausar/reanudar y editar instrucciones de este agente?", False)
    if not allow_code:
        print("Este worker solo recibirá tareas de análisis y tareas ligeras; no implementación.")
    print("La ejecución de comandos shell del agente seguirá DESACTIVADA.")
    # Pedimos y validamos el proveedor antes de gastar la invitación de un solo uso.
    model, provider = _provider_for(edition)
    config_path = default_worker_dir() / "worker.json"
    join_worker(hub_url, invite, name, config_path, project, repo,
                allow_remote_code=allow_code, allow_shell=False,
                accept_remote_control=remote_control)
    _write_profile(config_path, edition, model, provider)
    print("\nPerfil aplicado. Las claves API no se guardan en worker.json.")
    _write_provider_secret(provider, config_path)
    print("\nAntes de ejecutar tareas:")
    print("  1. Instalá OpenCode CLI y Git si todavía no están instalados.")
    if edition.endswith("-heavy"):
        print("  2. Instalá Ollama, iniciá su servicio y descargá el modelo elegido con ollama pull <modelo>.")
    print("  3. Ejecutá: python -m fabrica worker doctor")
    print("  4. Ejecutá: python -m fabrica worker run")
    print("Para detenerlo localmente: Ctrl+C. El propietario conserva siempre ese control.")


def _install_hub(cfg, mother: bool = False):
    from .hub import HubApplication, init_hub
    db_path, _ = init_hub(cfg.home)
    app = HubApplication(cfg.home)
    print("\n=== Fabrica247 · Hub administrador ===")
    print(f"Base de datos: {db_path}")
    print(f"Contraseña inicial: {app.password_path}")
    local_worker_created = False
    if mother:
        name = _ask("Nombre del proyecto personal", "Mi proyecto")
        slug = _slug(_ask("Slug del proyecto", _slug(name)))
        prompt = _ask("Instrucciones iniciales del proyecto (opcional)", "")
        app.create_project({"name": name, "slug": slug, "agent_prompt": prompt})
        if _yes("¿Querés que esta PC también trabaje como Worker local?", True):
            _require_git()
            repo = _ask("Ruta del repositorio Git local")
            if not repo:
                print("No se creó un Worker local. Podés agregarlo después desde otra terminal.")
            else:
                import subprocess
                repo_path = Path(repo).expanduser().resolve()
                if not repo_path.is_dir():
                    raise SystemExit(f"No existe la carpeta: {repo_path}")
                check = subprocess.run(["git", "-C", str(repo_path), "rev-parse", "--is-inside-work-tree"],
                                       capture_output=True, text=True)
                if check.returncode != 0:
                    raise SystemExit("La carpeta indicada no es un repositorio Git válido.")
                print("\nElegí el proveedor del Worker local:")
                print("  1. Liviano: router/API online")
                print("  2. Pesado: Ollama local ya instalado")
                provider_choice = _ask("Opción", "1")
                model, provider = _provider_for("linux-heavy" if provider_choice == "2" else "linux-lite")
                invite = app.create_invite({"uses": 1, "hours": 48, "label": "Worker local de la PC madre"})["token"]
                name_pc = platform.node() or "PC-madre"
                reply = app.enroll_worker({"invite": invite, "name": name_pc})
                from .worker import default_worker_dir, write_worker_config
                worker_cfg = write_worker_config(
                    reply, "http://127.0.0.1:8765", name_pc, default_worker_dir() / "worker.json",
                    project_slug=slug, repo_path=str(repo_path), allow_remote_code=True,
                    allow_shell=False, accept_remote_control=True)
                _write_profile(worker_cfg, "mother", model, provider)
                local_worker_created = True
                _write_provider_secret(provider, worker_cfg)
                print(f"Worker local creado: {worker_cfg}")
                print("El Worker local acepta administración remota; el shell permanece desactivado.")
    print("\nPara iniciar el Hub en esta PC:")
    print("  python -m fabrica hub serve --host 127.0.0.1 --port 8765")
    print("Para que otras PCs lleguen mediante VPN privada:")
    print("  python -m fabrica hub serve --host 0.0.0.0 --port 8765")
    print("No publiques HTTP directamente en Internet; usá una VPN privada o HTTPS.")
    if local_worker_created:
        print("En otra terminal, para iniciar tu Worker local: python -m fabrica worker doctor && python -m fabrica worker run")


def run_setup(edition: str | None, cfg):
    os_name = platform.system().lower()
    native = "windows" if os_name == "windows" else "linux"
    selected = edition or native
    valid = {"windows", "linux", "windows-lite", "linux-lite", "windows-heavy", "linux-heavy", "mother", "linux-mother", "hub"}
    if selected not in valid:
        raise SystemExit("Edición no válida. Elegí windows, linux, windows-lite, linux-lite, windows-heavy, linux-heavy, mother, linux-mother o hub.")
    if selected in ("mother", "linux-mother", "hub"):
        if selected == "linux-mother" and os_name == "windows":
            raise SystemExit("linux-mother solo se puede ejecutar en Linux.")
        _install_hub(cfg, mother=(selected != "hub"))
        return
    if selected in ("windows", "linux"):
        print("\nElegí el tipo de worker:")
        print("  1. Liviano: APIs/router online, sin modelo local")
        print("  2. Pesado: Ollama y modelo local")
        choice = _ask("Opción", "1")
        selected = f"{selected}-heavy" if choice == "2" else f"{selected}-lite"
    _install_worker(selected)
