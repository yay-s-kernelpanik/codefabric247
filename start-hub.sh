#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PY="$(command -v python3 || command -v python)"
exec "$PY" -m fabrica hub serve --host 127.0.0.1 --port 8765
