"""Operaciones git sobre el repositorio OBJETIVO y sus worktrees."""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import uuid
from pathlib import Path

IDENT = ["-c", "user.name=Fabrica247", "-c", "user.email=fabrica247@localhost"]


class GitError(RuntimeError):
    pass


def git(args, cwd, check=True, timeout=300):
    r = subprocess.run(
        ["git", "-c", "core.quotepath=off"] + list(args), cwd=str(cwd),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, stdin=subprocess.DEVNULL,
    )
    if check and r.returncode != 0:
        raise GitError(f"git {' '.join(args)} fallo: {(r.stderr or r.stdout).strip()}")
    return r


def repo_ready(repo) -> bool:
    """Es un repo git con al menos un commit."""
    if not repo or not Path(repo).is_dir():
        return False
    return git(["rev-parse", "--verify", "HEAD"], repo, check=False).returncode == 0


def head(repo) -> str:
    return git(["rev-parse", "HEAD"], repo).stdout.strip()


def _rm_readonly(func, path, _exc):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def remove_worktree(repo, path: Path) -> None:
    git(["worktree", "remove", "--force", str(path)], repo, check=False)
    if path.exists():
        shutil.rmtree(path, onerror=_rm_readonly)
    git(["worktree", "prune"], repo, check=False)


def delete_branch(repo, branch) -> None:
    if branch:
        git(["branch", "-D", branch], repo, check=False)


def create_worktree(repo, root: Path, task_id: int):
    """Crea un worktree limpio y NUEVO (limpia restos de intentos anteriores)."""
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"task-{task_id}"
    remove_worktree(repo, path)
    base = head(repo)
    branch = f"fabrica/task-{task_id}-{uuid.uuid4().hex[:6]}"
    git(["worktree", "add", "-b", branch, str(path), base], repo)
    return path, branch, base


def is_dirty(wt) -> bool:
    return bool(git(["status", "--porcelain"], wt).stdout.strip())


def commit_all(wt, message) -> None:
    git(["add", "-A"], wt)
    git(IDENT + ["commit", "--no-verify", "-m", message], wt)


def commits_since(wt, base) -> int:
    return int(git(["rev-list", "--count", f"{base}..HEAD"], wt).stdout.strip() or 0)


def changed_files(wt, base) -> list:
    out = git(["diff", "--name-only", base, "HEAD"], wt).stdout
    return [l.strip() for l in out.splitlines() if l.strip()]
