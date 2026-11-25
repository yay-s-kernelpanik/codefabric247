#!/usr/bin/env bash
# Instala un servicio systemd DE USUARIO para el Hub (sin sudo).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$(command -v python3 || command -v python)"
HOST="${FABRICA_HUB_HOST:-127.0.0.1}"
PORT="${FABRICA_HUB_PORT:-8765}"
[ -n "$PY" ] || { echo "No se encontró Python." >&2; exit 1; }
UNIT_DIR="$HOME/.config/systemd/user"
mkdir -p "$UNIT_DIR"
quote_systemd() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  printf '"%s"' "$value"
}
cat > "$UNIT_DIR/fabrica247-hub.service" <<EOF
[Unit]
Description=Fabrica247 Hub dashboard and task coordinator
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
WorkingDirectory=$(quote_systemd "$ROOT")
ExecStart=$(quote_systemd "$PY") -u -m fabrica hub serve --host $(quote_systemd "$HOST") --port $(quote_systemd "$PORT")
Restart=always
RestartSec=5
KillSignal=SIGINT
TimeoutStopSec=60
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now fabrica247-hub.service
printf 'Hub service installed. Status: systemctl --user status fabrica247-hub\n'
if command -v loginctl >/dev/null 2>&1 && loginctl show-user "${USER:-$(id -un)}" -p Linger 2>/dev/null | grep -q 'Linger=yes'; then
  echo "Linger está activo."
else
  echo "Para mantener el Hub tras cerrar sesión y arrancarlo al boot:"
  echo "  sudo loginctl enable-linger ${USER:-$(id -un)}"
fi
