#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PY="$(command -v python3 || command -v python || true)"
[ -n "$PY" ] || { echo "Necesitás Python 3.9+ (no requiere pip ni permisos de administrador)." >&2; exit 1; }
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)' || { echo "Fabrica247 requiere Python 3.9 o superior." >&2; exit 1; }
echo "Inicializando Fabrica247 Hub (sin agente local)..."
"$PY" -m fabrica hub init
cat <<'EOF'

Hub instalado. Para iniciar el panel en esta PC:
  python3 -m fabrica hub serve

Para que otras PCs puedan entrar por una red privada:
  python3 -m fabrica hub serve --host 0.0.0.0 --port 8765

No publiques el puerto directamente en Internet. Usá una VPN privada o HTTPS.
EOF
