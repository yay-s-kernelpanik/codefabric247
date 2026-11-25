#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PY="$(command -v python3 || command -v python || true)"
if [[ -z "$PY" ]]; then
  echo "No encuentro Python 3.9+. Instalalo para tu usuario y vuelve a ejecutar." >&2
  exit 1
fi
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)' || {
  echo "Fabrica247 requiere Python 3.9 o superior." >&2; exit 1;
}
exec "$PY" -m fabrica setup --edition linux
