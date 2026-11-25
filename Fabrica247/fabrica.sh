#!/usr/bin/env bash
# Wrapper: ./fabrica.sh <comando>   (equivale a python3 -m fabrica <comando>)
cd "$(dirname "$0")"
PY="$(command -v python3 || command -v python || true)"
[ -n "$PY" ] || { echo "Python no encontrado. Ejecuta ./install.sh" >&2; exit 1; }
exec "$PY" -m fabrica "$@"
