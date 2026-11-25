"""Utilidades de procesos multiplataforma: ejecutar con timeout, matar arboles, PIDs."""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from typing import NamedTuple

IS_WIN = os.name == "nt"


class Result(NamedTuple):
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool


def _group_kwargs() -> dict:
    if IS_WIN:
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def resolve_exe(cmd0: str) -> str:
    """Resuelve el ejecutable via PATH/PATHEXT (encuentra opencode.cmd en Windows)."""
    return shutil.which(cmd0) or cmd0


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if IS_WIN:
        import ctypes
        k32 = ctypes.windll.kernel32
        handle = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ok = k32.GetExitCodeProcess(handle, ctypes.byref(code))
        k32.CloseHandle(handle)
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    try:  # recoge zombies si el proceso es hijo nuestro
        done, _ = os.waitpid(pid, os.WNOHANG)
        if done:
            return False
    except ChildProcessError:
        pass
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def kill_tree(pid: int) -> None:
    """Mata el proceso y todos sus descendientes."""
    if IS_WIN:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True, stdin=subprocess.DEVNULL)
        return
    try:
        os.killpg(pid, signal.SIGKILL)  # pid es lider de sesion/grupo (start_new_session)
    except (ProcessLookupError, PermissionError):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def terminate_tree(pid: int, grace: float = 5.0) -> None:
    """Parada educada (SIGTERM al grupo) y, si no cede, a la fuerza."""
    if not pid_alive(pid):
        return
    if not IS_WIN:
        try:
            os.killpg(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
        end = time.time() + grace
        while time.time() < end and pid_alive(pid):
            time.sleep(0.2)
    if pid_alive(pid):
        kill_tree(pid)


def run_cmd(cmd, cwd=None, env=None, timeout=None, shell=False, cancel_event=None) -> Result:
    """Ejecuta un proceso; respeta timeout y una cancelación explícita del Worker.

    La cancelación remota solo se utiliza para detener el proceso del agente de una
    tarea asignada. Nunca recibe ni ejecuta comandos arbitrarios desde el Hub.
    """
    if IS_WIN and not shell and isinstance(cmd, (list, tuple)) and cmd:
        exe = str(cmd[0]).lower()
        if exe.endswith((".cmd", ".bat")):
            cmd = subprocess.list2cmdline([str(x) for x in cmd])
            shell = True
    p = subprocess.Popen(
        cmd, cwd=str(cwd) if cwd else None, env=env, shell=shell,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", **_group_kwargs(),
    )
    deadline = time.monotonic() + timeout if timeout is not None else None
    try:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                terminate_tree(p.pid, grace=2.0)
                try:
                    out, err = p.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    kill_tree(p.pid)
                    out, err = p.communicate()
                return Result(-2, out or "", (err or "") + "\n[detenido por solicitud remota autorizada]", False)
            remaining = None if deadline is None else deadline - time.monotonic()
            if remaining is not None and remaining <= 0:
                raise subprocess.TimeoutExpired(cmd, timeout)
            interval = 0.25 if remaining is None else min(0.25, remaining)
            try:
                out, err = p.communicate(timeout=interval)
                return Result(p.returncode, out or "", err or "", False)
            except subprocess.TimeoutExpired:
                continue
    except subprocess.TimeoutExpired:
        kill_tree(p.pid)
        try:
            out, err = p.communicate(timeout=15)
        except Exception:
            out, err = "", ""
        return Result(-1, out or "", (err or "") + f"\n[timeout tras {timeout}s]", True)
    except BaseException:
        kill_tree(p.pid)
        raise


def spawn_detached(cmd, cwd, env, log_path) -> int:
    """Lanza un proceso desacoplado de esta terminal, con salida a un log."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    shell = isinstance(cmd, str)
    if not shell:
        cmd = [resolve_exe(cmd[0])] + list(cmd[1:])
    kwargs = {}
    if IS_WIN:
        kwargs["creationflags"] = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                                   | subprocess.CREATE_NO_WINDOW)
    else:
        kwargs["start_new_session"] = True
    with open(log_path, "ab") as log:
        p = subprocess.Popen(cmd, cwd=str(cwd) if cwd else None, env=env, shell=shell,
                             stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                             close_fds=True, **kwargs)
    return p.pid


def read_pid(path) -> int:
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return 0
