#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PY="$(command -v python3 || command -v python || true)"
[ -n "$PY" ] || { echo "Necesitás Python 3.9+ (no requiere pip ni permisos de administrador)." >&2; exit 1; }
command -v git >/dev/null 2>&1 || { echo "Necesitás Git instalado para ejecutar tareas en worktrees." >&2; exit 1; }
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)' || { echo "Fabrica247 requiere Python 3.9 o superior." >&2; exit 1; }
HUB=""; INVITE=""; NAME="$(hostname 2>/dev/null || echo Worker)"; PROJECT=""; REPO=""; ALLOW_CODE=0; ALLOW_SHELL=0; ACCEPT_REMOTE=0; CONFIG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --hub) HUB="$2"; shift 2;;
    --invite) INVITE="$2"; shift 2;;
    --name) NAME="$2"; shift 2;;
    --project) PROJECT="$2"; shift 2;;
    --repo) REPO="$2"; shift 2;;
    --config) CONFIG="$2"; shift 2;;
    --allow-remote-code) ALLOW_CODE=1; shift;;
    --allow-shell) ALLOW_SHELL=1; shift;;
    --accept-remote-control) ACCEPT_REMOTE=1; shift;;
    *) echo "Opción desconocida: $1" >&2; exit 2;;
  esac
done
[ -n "$HUB" ] && [ -n "$INVITE" ] || { echo "Uso: ./install-worker.sh --hub https://hub --invite CODIGO [--name PC] [--project slug --repo /ruta] [--allow-remote-code] [--allow-shell] [--accept-remote-control]" >&2; exit 2; }
ARGS=(worker join --hub "$HUB" --invite "$INVITE" --name "$NAME")
[ -n "$PROJECT" ] && ARGS+=(--project "$PROJECT")
[ -n "$REPO" ] && ARGS+=(--repo "$REPO")
[ -n "$CONFIG" ] && ARGS+=(--config "$CONFIG")
[ "$ALLOW_CODE" -eq 1 ] && ARGS+=(--allow-remote-code)
[ "$ALLOW_SHELL" -eq 1 ] && ARGS+=(--allow-shell)
[ "$ACCEPT_REMOTE" -eq 1 ] && ARGS+=(--accept-remote-control)
"$PY" -m fabrica "${ARGS[@]}"
cat <<'EOF'

PC registrada. Editá worker.json para configurar:
  - projects.<slug>.path: ruta local del proyecto
  - agent.providers: APIs compatibles, router u Ollama
  - agent.model: proveedor/modelo
  - .worker.env: claves API como variables FABRICA_...

Instalá OpenCode por separado si esta PC va a ejecutar un agente de código.
Luego: python3 -m fabrica worker doctor && python3 -m fabrica worker run
EOF
