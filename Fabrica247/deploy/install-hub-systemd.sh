#!/usr/bin/env bash
# Instala un servicio systemd DE USUARIO para el Hub (sin sudo).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$(command -v python3 || command -v python)"
HOST="${FABRICA_HUB_HOST:-127.0.0.1}"
PORT="${FABRICA_HUB_PORT:-8765}"
UNIT_DIR="$HOME/.config/systemd/user"
mkdir -p "$UNIT_DIR"
cat > "$UNIT_DIR/fabrica247-hub.service" <<EOF
[Unit]
Description=Fabrica247 Hub dashboard and task coordinator
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$ROOT
ExecStart=$PY -m fabrica hub serve --host $HOST --port $PORT
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now fabrica247-hub.service
printf 'Hub service installed. Status: systemctl --user status fabrica247-hub\n'
printf 'To survive logout, systemd user lingering may need to be enabled by your system administrator.\n'
