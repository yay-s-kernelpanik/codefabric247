"""Safe, serialized publication of Worker patches to per-task Git branches."""
from __future__ import annotations
import fnmatch, os, subprocess, tempfile
from pathlib import Path
from .gitops import GitError, git, repo_ready

class IntegrationError(RuntimeError):
    """An integration failed; the source patch remains stored in the Hub."""
class IntegrationConflict(IntegrationError):
    """A patch cannot be applied safely to the selected base."""

def _run(args, cwd, input_bytes=None, timeout=300):
    env=os.environ.copy()
    env["GIT_TERMINAL_PROMPT"]="0"
    env["GCM_INTERACTIVE"]="Never"
    p=subprocess.run(["git","-c","core.quotepath=off"]+list(args),cwd=str(cwd),
                     input=input_bytes,capture_output=True,timeout=timeout,env=env)
    return p.returncode,p.stdout.decode("utf-8","replace"),p.stderr.decode("utf-8","replace")

def _git(args,cwd,check=True):
    return git(args,cwd,check=check,timeout=300).stdout.strip()

def _allowed(path,patterns):
    path=path.replace("\\","/")
    if path.startswith("/") or any(x in ("",".","..") for x in path.split("/")):
        return False
    if path==".env" or (path.startswith(".env.") and path!=".env.example"):
        return False
    return any(
        (p.strip().endswith("/") and path.startswith(p.strip().replace("\\","/"))) or
        path==p.strip().replace("\\","/") or
        path.startswith(p.strip().replace("\\","/").rstrip("/")+"/") or
        fnmatch.fnmatchcase(path,p.strip().replace("\\","/"))
        for p in patterns if p.strip()
    )

def _remote_sha(repo,branch):
    out=_git(["ls-remote","--heads","origin","refs/heads/"+branch],repo)
    return out.split()[0] if out else None

def _has_marker(repo,ref,task_id):
    rc,out,_=_run(["show","-s","--format=%B",ref],repo)
    return rc==0 and f"Fabrica247-Task: {task_id}" in out

def push_patch(repo_path,task_id,objective,patch,allowed_files=None,base_branch="main"):
    """Apply one patch on origin/base and push fabrica/task-ID, never base itself."""
    repo=Path(repo_path).expanduser().resolve()
    if not repo_ready(repo): raise IntegrationError("TARGET_REPO debe ser un repositorio Git con commits")
    if not patch or not patch.strip(): raise IntegrationError("La tarea no contiene un patch")
    if not _git(["remote","get-url","origin"],repo,check=False): raise IntegrationError("TARGET_REPO necesita un remoto origin")
    base_branch=str(base_branch or "main").strip()
    if _run(["check-ref-format","--branch",base_branch],repo)[0]: raise IntegrationError("HUB_BASE_BRANCH no es válida")
    branch=f"fabrica/task-{int(task_id)}"
    local_ref="refs/heads/"+branch
    remote_ref="refs/remotes/origin/"+branch
    remote_sha=_remote_sha(repo,branch)
    if remote_sha:
        rc,_,_=_run(["fetch","--no-tags","origin",f"refs/heads/{branch}:{remote_ref}"],repo)
        if rc==0 and _has_marker(repo,remote_ref,task_id):
            return {"branch":branch,"commit":remote_sha,"already_pushed":True}
        raise IntegrationError("La rama remota reservada para esta tarea existe con otro contenido")
    _git(["fetch","--no-tags","origin",f"+refs/heads/{base_branch}:refs/remotes/origin/{base_branch}"],repo)
    base_ref="refs/remotes/origin/"+base_branch
    if _run(["rev-parse","--verify",base_ref],repo)[0]: raise IntegrationError("No se encontró origin/"+base_branch)
    if _run(["show-ref","--verify",local_ref],repo)[0]==0:
        if not _has_marker(repo,local_ref,task_id):
            raise IntegrationError("La rama local de esta tarea existe sin su marcador; se conserva para revisión")
        rc,_,err=_run(["push","origin",f"{local_ref}:{local_ref}"],repo)
        if rc: raise IntegrationError("Push pendiente; commit local conservado: "+err[-800:])
        return {"branch":branch,"commit":_git(["rev-parse",local_ref],repo),"already_pushed":False}
    with tempfile.TemporaryDirectory(prefix=f"fabrica247-task-{task_id}-",dir=str(repo.parent)) as tmp:
        wt=Path(tmp)/"worktree"; created=False; committed=False
        try:
            _git(["worktree","prune"],repo)
            _git(["worktree","add","-b",branch,str(wt),base_ref],repo); created=True
            raw=patch.encode("utf-8")
            rc,_,err=_run(["apply","--check","--binary","-"],wt,raw)
            if rc: raise IntegrationConflict("CONFLICT: el patch no aplica sobre la base: "+err[-1000:])
            rc,_,err=_run(["apply","--index","--binary","-"],wt,raw)
            if rc: raise IntegrationConflict("CONFLICT: no se pudo aplicar el patch: "+err[-1000:])
            changed=[p for p in _git(["diff","--cached","--name-only"],wt).splitlines() if p]
            patterns=str(allowed_files).split(",") if allowed_files else ["**"]
            bad=[p for p in changed if not _allowed(p,patterns)]
            if not changed: raise IntegrationConflict("El patch no contiene cambios nuevos")
            if bad: raise IntegrationConflict("Rutas no permitidas o protegidas: "+", ".join(bad[:8]))
            title=" ".join(str(objective).split())[:100] or "cambios de tarea"
            _git(["-c","user.name=Fabrica247","-c","user.email=fabrica247@localhost",
                  "commit","--no-verify","-m",f"Fabrica247 task #{task_id}: {title}",
                  "-m",f"Fabrica247-Task: {task_id}"],wt)
            committed=True
            sha=_git(["rev-parse","HEAD"],wt)
            rc,_,err=_run(["push","origin",f"HEAD:refs/heads/{branch}"],wt)
            if rc: raise IntegrationError("Commit conservado localmente; push falló y puede reintentarse: "+err[-1000:])
            return {"branch":branch,"commit":sha,"already_pushed":False}
        except GitError as exc:
            raise IntegrationError(str(exc)) from exc
        finally:
            if created:
                _run(["worktree","remove","--force",str(wt)],repo)
                _run(["worktree","prune"],repo)
            if not committed: _run(["branch","-D",branch],repo)
