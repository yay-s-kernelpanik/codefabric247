#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PY="$(command -v python3 || command -v python || true)"
[[ -n "$PY" ]] || { echo "Instalá Python 3.9+ para tu usuario y volvé a ejecutar." >&2; exit 1; }
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)' || { echo "Fabrica247 requiere Python 3.9 o superior." >&2; exit 1; }
exec "$PY" -m fabrica setup --edition mother
