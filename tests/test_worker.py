"""Prueba de ejecución distribuida con un OpenCode simulado (solo POSIX)."""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from fabrica.worker import Worker, join_worker
from fabrica.supervisor import build_prompt
from unittest.mock import patch


@unittest.skipIf(os.name == "nt", "el ejecutable simulado usa shebang POSIX")
class WorkerSmoke(unittest.TestCase):
    def test_invalid_join_options_do_not_consume_invitation(self):
        with patch("fabrica.worker._http_json") as request:
            with self.assertRaises(ValueError):
                join_worker("https://hub.example", "invite-token", "PC", Path("worker.json"),
                            project_slug="my-project", repo_path=None)
            request.assert_not_called()

    def test_worker_creates_branch_and_returns_patch_to_hub_payload(self):
        root = Path(tempfile.mkdtemp())
        repo = root / "project"
        repo.mkdir()
        def git(*args):
            return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
        git("init", "-q")
        git("config", "user.email", "worker@test")
        git("config", "user.name", "Worker Test")
        (repo / "README.md").write_text("initial\n", encoding="utf-8")
        git("add", "-A"); git("commit", "-qm", "initial")

        fake = root / "fake-opencode"
        fake.write_text(f"#!{sys.executable}\nfrom pathlib import Path\nPath('worker-output.txt').write_text('result from remote worker\\n')\nprint('simulated agent done')\n", encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)

        work = root / "worker-home"
        work.mkdir()
        config = {
            "hub_url": "http://127.0.0.1:8765",
            "worker_id": "testworker",
            "worker_name": "Test worker",
            "projects": {"test-project": {"path": str(repo), "enabled": True}},
            "agent": {
                "enabled": True,
                "command": str(fake),
                "model": "fake/test",
                "providers": [{"id": "fake", "name": "Fake", "base_url": "http://127.0.0.1:1/v1",
                               "models": {"test": {"name": "Test"}}}],
                "task_timeout": 30,
                "allow_remote_code": True,
                "allow_shell": False
            }
        }
        config_path = work / "worker.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        (work / "worker.token").write_text("secret-token\n", encoding="utf-8")
        worker = Worker(config_path)
        reply = worker.run_task({
            "id": 7,
            "project_slug": "test-project",
            "objective": "Create worker-output.txt",
            "task_type": "implementation",
            "allowed_files": "worker-output.txt",
            "test_command": None,
            "last_error": None,
            "attempts": 1,
            "retry_count": 0
        })
        self.assertEqual(reply["outcome"], "done", reply)
        self.assertIn("diff --git", reply["patch"])
        self.assertIn("worker-output.txt", reply["patch"])
        branches = subprocess.run(["git", "branch", "--list", "fabrica/task-7-*"], cwd=repo,
                                  check=True, capture_output=True, text=True).stdout
        self.assertTrue(branches.strip())
        self.assertFalse((work / "worktrees" / "test-project" / "task-7").exists())

    def test_worker_receives_cancel_signal_only_with_remote_control_consent(self):
        root = Path(tempfile.mkdtemp())
        cfg = {
            "hub_url": "http://127.0.0.1:8765", "worker_id": "test", "worker_name": "Worker",
            "projects": {"p": {"path": str(root)}},
            "agent": {"enabled": True, "model": "router/auto", "providers": [
                {"id": "router", "base_url": "http://127.0.0.1:1/v1", "models": {"auto": {}}}
            ], "allow_remote_code": False},
            "remote_control": {"enabled": True}
        }
        config = root / "worker.json"
        config.write_text(json.dumps(cfg), encoding="utf-8")
        (root / "worker.token").write_text("secret")
        worker = Worker(config)
        worker.current_task = 19
        with patch.object(worker, "request", return_value={"ok": True, "desired_state": "RUNNING",
                                                              "worker_prompt": "", "cancel_current_task": True}):
            worker.heartbeat()
        self.assertTrue(worker.task_cancel_event.is_set())

    def test_prompt_layers_are_included_in_agent_instructions(self):
        prompt = build_prompt({
            "objective": "Analiza este módulo", "allowed_files": None, "test_command": None,
            "last_error": None, "local_prompt": "No agregues dependencias.",
            "project_prompt": "Mantén compatibilidad con Python 3.9.",
            "worker_prompt": "Responde en español.", "task_prompt": "Incluye un resumen final."
        }, "reasoning")
        self.assertIn("No agregues dependencias.", prompt)
        self.assertIn("Mantén compatibilidad con Python 3.9.", prompt)
        self.assertIn("Responde en español.", prompt)
        self.assertIn("Incluye un resumen final.", prompt)


if __name__ == "__main__":
    unittest.main()
