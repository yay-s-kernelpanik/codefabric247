#!/usr/bin/env bash
# Instala Fabrica247 como servicio de usuario systemd (reinicio automatico, arranque al iniciar sesion).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UNIT_DIR="$HOME/.config/systemd/user"
mkdir -p "$UNIT_DIR"
cat > "$UNIT_DIR/fabrica247.service" <<UNIT
[Unit]
Description=Fabrica247 supervisor
After=network-online.target

[Service]
Type=simple
WorkingDirectory=$ROOT
ExecStart=$ROOT/fabrica.sh start
ExecStop=$ROOT/fabrica.sh stop
Restart=always
RestartSec=15
KillMode=control-group

[Install]
WantedBy=default.target
UNIT
systemctl --user daemon-reload
systemctl --user enable --now fabrica247.service
echo "Servicio activo. Estado:  systemctl --user status fabrica247"
echo "Para que siga activo sin sesion abierta:  sudo loginctl enable-linger $USER"
