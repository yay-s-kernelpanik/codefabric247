#!/usr/bin/env bash
# Instala un servicio systemd DE USUARIO para el worker actualmente registrado.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$(command -v python3 || command -v python)"
CONFIG="${FABRICA_WORKER_CONFIG:-$HOME/.config/Fabrica247/worker.json}"
[ -f "$CONFIG" ] || { echo "No existe $CONFIG. Ejecuta worker join primero." >&2; exit 1; }
UNIT_DIR="$HOME/.config/systemd/user"
mkdir -p "$UNIT_DIR"
cat > "$UNIT_DIR/fabrica247-worker.service" <<EOF
[Unit]
Description=Fabrica247 volunteer worker
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$ROOT
ExecStart=$PY -m fabrica worker run --config $CONFIG
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now fabrica247-worker.service
printf 'Worker service installed. Stop it with: systemctl --user stop fabrica247-worker\n'
