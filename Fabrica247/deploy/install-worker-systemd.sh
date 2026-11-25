#!/usr/bin/env bash
# Instala un servicio systemd DE USUARIO para el worker actualmente registrado.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$(command -v python3 || command -v python)"
CONFIG="${FABRICA_WORKER_CONFIG:-$HOME/.config/Fabrica247/worker.json}"
[ -n "$PY" ] || { echo "No se encontró Python." >&2; exit 1; }
[ -f "$CONFIG" ] || { echo "No existe $CONFIG. Ejecuta worker join primero." >&2; exit 1; }
UNIT_DIR="$HOME/.config/systemd/user"
mkdir -p "$UNIT_DIR"
quote_systemd() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  printf '"%s"' "$value"
}
cat > "$UNIT_DIR/fabrica247-worker.service" <<EOF
[Unit]
Description=Fabrica247 volunteer worker
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
WorkingDirectory=$(printf '"%s"' "$ROOT")
ExecStart=$(printf '"%s"' "$PY") -u -m fabrica worker run --config $(printf '"%s"' "$CONFIG")
Restart=always
RestartSec=10
KillSignal=SIGINT
TimeoutStopSec=60
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now fabrica247-worker.service
echo "Worker instalado: systemctl --user status fabrica247-worker"
if command -v loginctl >/dev/null 2>&1 && loginctl show-user "${USER:-$(id -un)}" -p Linger 2>/dev/null | grep -q 'Linger=yes'; then
  echo "Linger está activo: el Worker puede iniciar sin una sesión abierta."
else
  echo "Para que arranque al iniciar el equipo y siga activo al cerrar sesión:"
  echo "  sudo loginctl enable-linger ${USER:-$(id -un)}"
fi
