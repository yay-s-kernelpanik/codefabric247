"""Integration tests use a local bare remote and never contact GitHub."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from fabrica.integration import IntegrationConflict, push_patch


def git(args, cwd):
    p = subprocess.run(["git"] + list(args), cwd=str(cwd), capture_output=True, text=True)
    if p.returncode:
        raise AssertionError(p.stderr or p.stdout)
    return p.stdout.strip()


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.remote = self.tmp / "origin.git"
        self.repo = self.tmp / "hub"
        git(["init", "--bare", str(self.remote)], self.tmp)
        git(["init", "--initial-branch=main", str(self.repo)], self.tmp)
        git(["config", "user.name", "Test"], self.repo)
        git(["config", "user.email", "test@example.invalid"], self.repo)
        (self.repo / "README.md").write_text("base\n", encoding="utf-8")
        git(["add", "README.md"], self.repo)
        git(["commit", "-m", "base"], self.repo)
        git(["remote", "add", "origin", str(self.remote)], self.repo)
        git(["push", "-u", "origin", "main"], self.repo)
        self.base = git(["rev-parse", "HEAD"], self.repo)
        self.worker = self.tmp / "worker"
        git(["clone", str(self.remote), str(self.worker)], self.tmp)
        git(["config", "user.name", "Worker"], self.worker)
        git(["config", "user.email", "worker@example.invalid"], self.worker)

    def patch(self, path, content):
        target = self.worker / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        git(["add", path], self.worker)
        git(["commit", "-m", "worker change"], self.worker)
        return git(["diff", "--binary", self.base + "..HEAD"], self.worker)

    def test_task_branch_push_is_idempotent_and_does_not_touch_main(self):
        patch = self.patch("src/module.py", "print('ok')\n")
        result = push_patch(self.repo, 42, "Add module", patch, "src/", "main")
        self.assertEqual(result["branch"], "fabrica/task-42")
        self.assertEqual(git(["rev-parse", "main"], self.repo), self.base)
        self.assertTrue(git(["ls-remote", "--heads", "origin", "refs/heads/fabrica/task-42"], self.repo))
        again = push_patch(self.repo, 42, "Add module", patch, "src/", "main")
        self.assertTrue(again["already_pushed"])

    def test_paths_outside_allowed_scope_are_rejected(self):
        patch = self.patch("docs/unauthorized.txt", "not allowed\n")
        with self.assertRaises(IntegrationConflict):
            push_patch(self.repo, 43, "Docs", patch, "src/", "main")
        self.assertEqual(git(["rev-parse", "main"], self.repo), self.base)
        self.assertFalse(git(["ls-remote", "--heads", "origin", "refs/heads/fabrica/task-43"], self.repo))

    def test_secret_env_files_are_never_integrated(self):
        patch = self.patch(".env", "TOKEN=secret\n")
        with self.assertRaises(IntegrationConflict):
            push_patch(self.repo, 44, "env", patch, None, "main")


if __name__ == "__main__":
    unittest.main()
