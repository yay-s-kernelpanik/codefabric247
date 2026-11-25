"""Pruebas de humo con un 'opencode' falso (solo POSIX). Ejecutar: python -m unittest discover tests"""
import os
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FAKE = """#!{py}
import sys
prompt = sys.argv[-1]
if "FAKE_INFRA" in prompt:
    sys.stderr.write("Error: connect ECONNREFUSED 127.0.0.1:8787\\n"); sys.exit(1)
if "FAKE_FAIL" in prompt:
    sys.stderr.write("boom\\n"); sys.exit(1)
if "FAKE_NOOP" in prompt:
    print("no hice nada"); sys.exit(0)
if "FAKE_READ" in prompt:
    print("informe: todo bien"); sys.exit(0)
if "FAKE_DOCS" in prompt:
    import os; os.makedirs("docs", exist_ok=True); open("docs/a.md", "w").write("x")
    sys.exit(0)
open("out.txt", "w").write("hola")
print("hecho")
"""


class _H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"data":[]}')

    def log_message(self, *a):
        pass


@unittest.skipIf(os.name == "nt", "usa un opencode falso con shebang")
class Smoke(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = self.tmp / "target"
        self.repo.mkdir()
        g = lambda *a: subprocess.run(["git", *a], cwd=self.repo, check=True, capture_output=True)
        g("init", "-q"); g("config", "user.email", "t@t"); g("config", "user.name", "t")
        (self.repo / "README.md").write_text("hi"); g("add", "-A"); g("commit", "-qm", "init")
        fake = self.tmp / "fake_opencode"
        fake.write_text(FAKE.format(py=sys.executable)); fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        self.srv = HTTPServer(("127.0.0.1", 0), _H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.env = {"FABRICA_HOME": str(self.tmp / "home"), "TARGET_REPO": str(self.repo),
                    "OPENCODE_BIN": str(fake), "HYPERROUTER_URL": f"http://127.0.0.1:{self.srv.server_port}/v1",
                    "HYPERROUTER_API_KEY": "super-secret-test-key",
                    "POLL_INTERVAL": "1", "TASK_TIMEOUT": "30", "TEST_TIMEOUT": "30"}
        self.patch = mock.patch.dict(os.environ, self.env); self.patch.start()
        from fabrica.config import load_settings
        from fabrica.cli import init_project
        self.cfg = load_settings(); init_project(self.cfg)
        from fabrica import db
        self.db = db; self.conn = db.init_db(self.cfg)

    def tearDown(self):
        self.srv.shutdown(); self.srv.server_close(); self.patch.stop()

    def run_once(self):
        from fabrica.supervisor import run_supervisor
        run_supervisor(self.cfg, once=True)

    def test_opencode_config_does_not_store_router_secret(self):
        import json
        config = json.loads(self.cfg.opencode_config.read_text(encoding="utf-8"))
        provider = next(iter(config["providers"].values()))
        self.assertEqual(provider["settings"]["apiKey"], "{env:FABRICA247_ROUTER_API_KEY}")
        self.assertNotIn("super-secret-test-key", self.cfg.opencode_config.read_text(encoding="utf-8"))
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(self.cfg.opencode_config.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE((self.cfg.home / ".env").stat().st_mode), 0o600)

    def row(self, tid):
        return self.conn.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()

    def branches(self):
        return subprocess.run(["git", "branch", "--list", "fabrica/*"], cwd=self.repo,
                              capture_output=True, text=True).stdout

    def test_success_commits_on_branch_and_cleans_worktree(self):
        tid = self.db.add_task(self.conn, "Crear archivo", "implementation", allowed_files="out.txt")
        self.run_once()
        r = self.row(tid)
        self.assertEqual(r["status"], "DONE", r["last_error"])
        self.assertIn(r["branch_name"], self.branches())
        files = subprocess.run(["git", "show", "--name-only", "--format=", r["branch_name"]],
                               cwd=self.repo, capture_output=True, text=True).stdout
        self.assertIn("out.txt", files)
        self.assertFalse((self.cfg.worktrees_dir / f"task-{tid}").exists())

    def test_noop_retries_then_fails_without_crashing(self):
        tid = self.db.add_task(self.conn, "FAKE_NOOP", "implementation", max_retries=1)
        self.run_once()
        r = self.row(tid)
        self.assertEqual((r["status"], r["retry_count"]), ("FAILED", 2))
        self.assertEqual(self.branches().strip(), "")

    def test_infra_failure_does_not_consume_retries(self):
        tid = self.db.add_task(self.conn, "FAKE_INFRA", "implementation")
        self.run_once()
        r = self.row(tid)
        self.assertEqual((r["status"], r["retry_count"], r["infra_failures"]), ("PENDING", 0, 1))
        self.assertIsNotNone(r["not_before"])

    def test_allowed_files_violation_fails(self):
        tid = self.db.add_task(self.conn, "escribe algo", "implementation", allowed_files="docs/", max_retries=0)
        self.run_once()
        self.assertEqual(self.row(tid)["status"], "FAILED")
        tid2 = self.db.add_task(self.conn, "FAKE_DOCS", "implementation", allowed_files="docs/")
        self.run_once()
        self.assertEqual(self.row(tid2)["status"], "DONE")

    def test_reasoning_is_readonly_and_saves_output(self):
        tid = self.db.add_task(self.conn, "FAKE_READ", "reasoning")
        self.run_once()
        r = self.row(tid)
        self.assertEqual(r["status"], "DONE")
        self.assertIn("informe", Path(r["output_path"]).read_text())
        tid2 = self.db.add_task(self.conn, "modifica cosas", "reasoning", max_retries=0)
        self.run_once()
        self.assertEqual(self.row(tid2)["status"], "FAILED")

    def test_failing_test_command_fails_task(self):
        tid = self.db.add_task(self.conn, "x", "implementation", test_command="exit 3", max_retries=0)
        self.run_once()
        r = self.row(tid)
        self.assertEqual(r["status"], "FAILED"); self.assertIn("test_command", r["last_error"])

    def test_running_tasks_recovered_on_start(self):
        tid = self.db.add_task(self.conn, "x", "implementation")
        self.conn.execute("UPDATE tasks SET status='RUNNING' WHERE id=?", (tid,)); self.conn.commit()
        self.run_once()
        self.assertEqual(self.row(tid)["status"], "DONE")

    def test_router_down_leaves_tasks_pending(self):
        self.srv.shutdown(); self.srv.server_close()
        tid = self.db.add_task(self.conn, "x", "implementation")
        self.run_once()
        r = self.row(tid)
        self.assertEqual((r["status"], r["retry_count"]), ("PENDING", 0))

    def test_retry_after_failure_gets_fresh_worktree(self):
        tid = self.db.add_task(self.conn, "FAKE_FAIL", "implementation", max_retries=2)
        self.run_once()
        self.assertEqual(self.row(tid)["retry_count"], 3)  # 3 intentos sin NameError/CalledProcessError

    def test_classify(self):
        from fabrica.supervisor import classify_task, path_allowed
        self.assertEqual(classify_task("Revisa el codigo. Solo lectura"), "reasoning")
        self.assertEqual(classify_task("Genera un resumen"), "light")
        self.assertEqual(classify_task("Implementa X"), "implementation")
        self.assertTrue(path_allowed("src/a/b.rs", ["src/"]))
        self.assertFalse(path_allowed("srcx/a.rs", ["src/"]))
        self.assertTrue(path_allowed("src/a.rs", ["src/*.rs"]))


if __name__ == "__main__":
    unittest.main()
