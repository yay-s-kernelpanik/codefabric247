"""Comprobaciones de salud HTTP (solo libreria estandar)."""
from __future__ import annotations

import time
import urllib.error
import urllib.request


def http_ok(url: str, timeout: float = 5.0, headers: dict | None = None) -> bool:
    """True si el servidor responde con cualquier codigo < 500 (esta vivo)."""
    try:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status < 500
    except urllib.error.HTTPError as e:
        return e.code < 500
    except Exception:
        return False


def wait_http(url: str, timeout: float) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if http_ok(url, timeout=3):
            return True
        time.sleep(1)
    return False


def router_ok(cfg) -> bool:
    return http_ok(cfg.router_url + "/models", headers={"Authorization": f"Bearer {cfg.api_key}"})
