"""Configuracion: .env propio (sin dependencias) + variables de entorno."""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _parse_dotenv(path: Path) -> dict:
    data = {}
    if not path.is_file():
        return data
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:]
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        data[key] = value
    return data


def find_opencode() -> str:
    """Busca opencode en el PATH y en las ubicaciones habituales de instalacion."""
    found = shutil.which("opencode")
    if found:
        return found
    home = Path.home()
    names = ["opencode.exe", "opencode.cmd", "opencode"] if os.name == "nt" else ["opencode"]
    dirs = [home / ".opencode" / "bin", home / ".local" / "bin", home / ".npm-global" / "bin"]
    if os.name == "nt" and os.environ.get("APPDATA"):
        dirs.append(Path(os.environ["APPDATA"]) / "npm")
    for d in dirs:
        for n in names:
            if (d / n).is_file():
                return str(d / n)
    return "opencode"


@dataclass(frozen=True)
class Settings:
    home: Path
    db_path: Path
    logs_dir: Path
    run_dir: Path
    worktrees_dir: Path
    opencode_config: Path
    target_repo: object          # Path | None
    router_url: str
    api_key: str
    model: str
    opencode_bin: str
    task_timeout: int
    test_timeout: int
    poll_interval: int
    infra_backoff: int
    allow_all: bool
    require_router: bool


def load_settings() -> Settings:
    home = Path(os.environ.get("FABRICA_HOME") or BASE_DIR).expanduser().resolve()
    dotenv = _parse_dotenv(home / ".env")

    def get(key, default=""):
        return os.environ.get(key) or dotenv.get(key) or default

    def get_int(key, default):
        try:
            return int(get(key, str(default)))
        except ValueError:
            return default

    def get_bool(key, default):
        return get(key, str(default)).strip().lower() in ("1", "true", "yes", "si", "on")

    target = get("TARGET_REPO")
    return Settings(
        home=home,
        db_path=home / "fabrica247.db",
        logs_dir=home / "logs",
        run_dir=home / "run",
        worktrees_dir=home / "worktrees",
        opencode_config=home / "config" / "opencode.fabrica.jsonc",
        target_repo=Path(target).expanduser().resolve() if target else None,
        router_url=get("HYPERROUTER_URL", "http://127.0.0.1:8787/v1").rstrip("/"),
        api_key=get("HYPERROUTER_API_KEY", "no-necesaria"),
        model=get("FABRICA_MODEL", "hyperrouter/auto"),
        opencode_bin=get("OPENCODE_BIN") or find_opencode(),
        task_timeout=get_int("TASK_TIMEOUT", 900),
        test_timeout=get_int("TEST_TIMEOUT", 600),
        poll_interval=get_int("POLL_INTERVAL", 10),
        infra_backoff=get_int("INFRA_BACKOFF", 120),
        allow_all=get_bool("ALLOW_ALL_PERMISSIONS", True),
        require_router=get_bool("REQUIRE_ROUTER", True),
    )
