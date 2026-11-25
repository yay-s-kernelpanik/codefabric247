"""Safe, serialized publication of Worker patches to per-task Git branches."""
from __future__ import annotations

import fnmatch
import os
import subprocess
import tempfile
from pathlib import Path

from .gitops import GitError, git, repo_ready


class IntegrationError(RuntimeError):
    """An integration failed; the source patch remains stored in the Hub."""


class IntegrationConflict(IntegrationError):
    """A patch cannot be applied safely to the selected base."""


def _run(args, cwd, input_bytes=None, timeout=300):
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "Never"
    proc = subprocess.run(
        ["git", "-c", "core.quotepath=off"] + list(args),
        cwd=str(cwd), input=input_bytes, capture_output=True, timeout=timeout,
        env=env,
    )
    stdout = proc.stdout.decode("utf-8", "replace")
    stderr = proc.stderr.decode("utf-8", "replace")
    return proc.returncode, stdout, stderr


def _git(args, cwd, check=True):
    result = git(args, cwd, check=check, timeout=300)
    return result.stdout.strip()


def _allowed(path: str, patterns: list[str]) -> bool:
    path = path.replace("\\", "/")
    if path.startswith("/") or any(part in ("", ".", "..") for part in path.split("/")):
        return False
    if path == ".env" or (path.startswith(".env.") and path != ".env.example"):
        return False
    for raw in patterns:
        pattern = raw.strip().replace("\\", "/")
        if not pattern:
            continue
        if pattern.endswith("/") and path.startswith(pattern):
            return True
        if path == pattern or path.startswith(pattern.rstrip("/") + "/"):
            return True
        if fnmatch.fnmatchcase(path, pattern):
            return True
    return False


def _remote_branch_sha(repo: Path, branch: str) -> str | None:
    output = _git(["ls-remote", "--heads", "origin", "refs/heads/" + branch], repo)
    return output.split()[0] if output else None


def _has_marker(repo: Path, ref: str, task_id: int) -> bool:
    rc, out, _ = _run(["show", "-s", "--format=%B", ref], repo)
    return rc == 0 and f"Fabrica247-Task: {task_id}" in out


def push_patch(repo_path, task_id: int, objective: str, patch: str,
               allowed_files=None, base_branch="main") -> dict:
    """Apply a patch on the latest origin/base and push fabrica/task-ID.

    This function never checks out, updates, or force-pushes the base branch.
    It is called by the Hub's single integration loop, not by Workers.
    """
    repo = Path(repo_path).expanduser().resolve()
    if not repo_ready(repo):
        raise IntegrationError("TARGET_REPO debe ser un repositorio Git con commits")
    if not patch or not patch.strip():
        raise IntegrationError("La tarea no contiene un patch")
    remote = _git(["remote", "get-url", "origin"], repo, check=False)
    if not remote:
        raise IntegrationError("TARGET_REPO necesita un remoto origin")
    base_branch = str(base_branch or "main").strip()
    if _run(["check-ref-format", "--branch", base_branch], repo)[0]:
        raise IntegrationError("HUB_BASE_BRANCH no es una rama Git válida")
    branch = f"fabrica/task-{int(task_id)}"
    local_ref = f"refs/heads/{branch}"
    remote_ref = f"refs/remotes/origin/{branch}"
    marker = f"Fabrica247-Task: {int(task_id)}"

    # Recover an already-pushed branch after a Hub crash (idempotent).
    remote_sha = _remote_branch_sha(repo, branch)
    if remote_sha:
        rc, _, _ = _run(["fetch", "--no-tags", "origin",
                         f"refs/heads/{branch}:{remote_ref}"], repo)
        if rc == 0 and _has_marker(repo, remote_ref, task_id):
            return {"branch": branch, "commit": remote_sha, "already_pushed": True}
        raise IntegrationError("La rama remota reservada para esta tarea existe con otro contenido")

    _git(["fetch", "--no-tags", "origin", base_branch], repo)
    base_ref = f"refs/remotes/origin/{base_branch}"
    if _run(["rev-parse", "--verify", base_ref], repo)[0]:
        raise IntegrationError(f"No se encontró origin/{base_branch}")

    # Retry a push that failed after the commit was written locally.
    if not _run(["show-ref", "--verify", local_ref], repo)[0]:
        pass
    else:
        if not _has_marker(repo, local_ref, task_id):
            raise IntegrationError("La rama local de esta tarea existe pero no contiene su marcador")
        rc, _, err = _run(["push", "origin", f"{local_ref}:{local_ref}"], repo)
        if rc:
            raise IntegrationError("Push pendiente; el commit local se conservó: " + err[-800:])
        return {"branch": branch, "commit": _git(["rev-parse", local_ref], repo), "already_pushed": False}

    with tempfile.TemporaryDirectory(prefix=f"fabrica247-task-{task_id}-", dir=str(repo.parent)) as tmp:
        wt = Path(tmp) / "worktree"
        created = False
        committed = False
        try:
            _git(["worktree", "prune"], repo)
            _git(["worktree", "add", "-b", branch, str(wt), base_ref], repo)
            created = True
            raw = patch.encode("utf-8")
            rc, _, err = _run(["apply", "--check", "--binary", "-"], wt, raw)
            if rc:
                raise IntegrationConflict("CONFLICT: el patch no aplica sobre la base actual: " + err[-1000:])
            rc, _, err = _run(["apply", "--index", "--binary", "-"], wt, raw)
            if rc:
                raise IntegrationConflict("CONFLICT: no se pudo aplicar el patch: " + err[-1000:])

            changed = [p for p in _git(["diff", "--cached", "--name-only"], wt).splitlines() if p]
            if not changed:
                raise IntegrationConflict("El patch no contiene cambios nuevos")
            if any(not _allowed(p, str(allowed_files).split(",") if allowed_files else ["**"]) for p in changed):
                bad = [p for p in changed if not _allowed(p, str(allowed_files).split(",") if allowed_files else ["**"])]
                raise IntegrationConflict("El patch modifica rutas no permitidas o protegidas: " + ", ".join(bad[:8]))

            title = " ".join(str(objective).split())[:100] or "cambios de tarea"
            _git(["-c", "user.name=Fabrica247", "-c", "user.email=fabrica247@localhost",
                  "commit", "--no-verify", "-m", f"Fabrica247 task #{task_id}: {title}",
                  "-m", marker], wt)
            committed = True
            commit_sha = _git(["rev-parse", "HEAD"], wt)
            rc, _, err = _run(["push", "origin", f"HEAD:refs/heads/{branch}"], wt)
            if rc:
                raise IntegrationError("El commit quedó guardado localmente; push falló y puede reintentarse: " + err[-1000:])
            return {"branch": branch, "commit": commit_sha, "already_pushed": False}
        except GitError as exc:
            raise IntegrationError(str(exc)) from exc
        finally:
            if created:
                _run(["worktree", "remove", "--force", str(wt)], repo)
                _run(["worktree", "prune"], repo)
            if not committed:
                _run(["branch", "-D", branch], repo)
