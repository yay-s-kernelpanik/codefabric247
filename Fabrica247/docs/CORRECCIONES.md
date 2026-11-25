# Correcciones respecto a la versión anterior

| # | Problema | Solución |
|---|---|---|
| 1 | `db.py` usaba `Path` sin importar | El esquema vive embebido en `db.py`; ya no se lee `schema.sql` |
| 2 | `cd` en el instalador rompía `pip install -r requirements.txt` | Sin dependencias de terceros: no hay `pip` ni `cd` en los instaladores |
| 3 | PEP 668 (`externally-managed-environment`) | Idem: nada se instala con pip |
| 4 | `start.sh` redirigía a `logs/` inexistente | `init`/`start` crean `logs/`, `run/`, `worktrees/` |
| 5 | Se arrancaba el supervisor dentro del venv de kiro-gateway | El supervisor nunca activa venvs; cada servicio usa su propio intérprete en su `command` |
| 6 | Reintento fallaba: worktree/rama ya existían y mataba el bucle | `create_worktree` limpia restos y usa rama nueva; el bucle captura toda excepción (test incluido) |
| 7 | `validate()` siempre daba verdadero | Se guarda `base_commit`; el supervisor hace el commit y exige `commits_since(base) > 0` |
| 8 | Worktrees sobre el repo equivocado | `TARGET_REPO` obligatorio, validado (repo con ≥1 commit) |
| 9 | La DB no existía / faltaba `sqlite3` CLI | `fabrica init` y `fabrica add` (sin CLI de sqlite) |
| 10 | `supervisor.log` nunca se escribía | `logging` con rotación en `logs/supervisor.log` |
| 11 | Faltaba bloque `models` en OpenCode | Generado desde `FABRICA_MODEL` |
| 12 | Se sobrescribía `opencode.jsonc` del usuario | Config propia + `OPENCODE_CONFIG`; no se toca `~/.config/opencode` |
| 13 | Paquete npm incorrecto | Instalador oficial y, si falla, `opencode-ai` (con prefijo de usuario ante `EACCES`) |
| 14 | Windows: `opencode.cmd` no se encontraba | `shutil.which` + paso del prompt por archivo para shims `.cmd` |
| 15 | Python 3.11 instalado, `py -3.12` usado | Se instala 3.12 y se usa `py -3`/`python` con comprobación de versión |
| 16 | `winget` no actualiza el PATH | `Refresh-Path` tras instalar |
| 17 | `Get-Process ... CommandLine` no existe en PS 5.1 | PID files + comprobación de salud HTTP |
| 18 | BOM en JSON desde PS 5.1 | La config la escribe Python (UTF-8 sin BOM) |
| 19 | `~\.local\bin` inexistente / estructura supuesta de HyperRouter | Ya no se copian archivos; HyperRouter se declara en `services.json` |
| 20 | HyperRouter es TUI y se lanzaba sin TTY | Servicio opcional, deshabilitado hasta confirmar su modo servidor; Fabrica247 solo necesita la URL |
| 21 | `npm -g` con `EACCES` | Reintento con `--prefix ~/.local` |
| 22 | Puertos sin coordinar | `health_url`/`HYPERROUTER_URL` explícitos |
| 23 | No se esperaba a los servicios | `wait_http` + comprobación del router antes de cada tarea |
| 24 | Caída del router quemaba reintentos | Clasificación `infra`: espera con backoff sin consumir reintentos |
| 25 | `returncode == 0` no garantiza trabajo | `evaluate()` exige cambios/respuesta según el tipo |
| 26 | Tareas atascadas en `RUNNING` | Recuperación al arrancar y al parar; parada por señal las devuelve a `PENDING` |
| 27 | Timeout solo mataba al hijo directo | `kill_tree` (grupo de procesos / `taskkill /T`) |
| 28 | `test_command` sin timeout | `TEST_TIMEOUT` |
| 29 | Código muerto | `classify_task` se usa; `allowed_files` se aplica; eliminados `model_health`, `python-dotenv`, `LOG_DIR` |
| 30 | `datetime.now()` en SQLite (deprecado 3.12) | Marcas UTC en texto |
| 31 | `str \| None` exige 3.10 | `from __future__ import annotations` + comprobación ≥ 3.9 |
| 32 | `pgrep -f` y `stop` inexistentes | PID files y `stop` real (cierra árboles) |
| 33 | Archivos prometidos y ausentes | `__init__`, `.env.example`, `.gitignore`, `README`, `stop.*` incluidos |
| 34 | Solo pacman/apt, fallo silencioso | pacman, apt, dnf, zypper, brew; error claro si no hay gestor |

## Afirmaciones corregidas
- *"Un solo comando"*: instalador + 3 pasos manuales inevitables (`TARGET_REPO`, router, credenciales).
- *"Ninguna tarea puede tocar tu rama"*: el trabajo va a ramas propias, pero el worktree no es un sandbox (ver README > Seguridad).
- *"24/7"*: units de systemd/tarea programada con reinicio automático.
- *"Sin gastar dinero / FAILED limpio al agotar cuotas"*: las tareas esperan en vez de fallar; el coste depende de lo que exponga tu router.
