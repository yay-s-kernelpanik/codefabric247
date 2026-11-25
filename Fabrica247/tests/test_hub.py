"""Pruebas del coordinador distribuido sin APIs ni modelos reales."""
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from pathlib import Path

from fabrica.hub import HubApplication, init_hub, make_handler, stamp, utcnow
from datetime import timedelta
from fabrica.worker import worker_capabilities, make_opencode_config, join_worker, Worker


class HubTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        init_hub(self.tmp)
        self.app = HubApplication(self.tmp)
        self.project_a = self.app.create_project({"name": "Proyecto A", "slug": "proyecto-a"})
        self.project_b = self.app.create_project({"name": "Proyecto B", "slug": "proyecto-b"})
        self.invite = self.app.create_invite({"uses": 2, "hours": 2})["token"]
        one = self.app.enroll_worker({"invite": self.invite, "name": "Worker A"})
        two = self.app.enroll_worker({"invite": self.invite, "name": "Worker B"})
        self.worker_a = {"id": one["worker_id"]}
        self.worker_b = {"id": two["worker_id"]}

    def test_invite_is_limited_and_tokens_are_not_stored_plaintext(self):
        invite = self.app.create_invite({"uses": 1, "hours": 1})["token"]
        result = self.app.enroll_worker({"invite": invite, "name": "One use"})
        self.assertTrue(result["worker_token"])
        with self.assertRaises(PermissionError):
            self.app.enroll_worker({"invite": invite, "name": "Second use"})
        with self.app.db() as conn:
            row = conn.execute("SELECT token_hash FROM workers WHERE id=?", (result["worker_id"],)).fetchone()
            self.assertNotEqual(row["token_hash"], result["worker_token"])

    def test_dashboard_never_exposes_worker_token_hash(self):
        data = self.app.dashboard_data()
        self.assertTrue(data["workers"])
        self.assertNotIn("token_hash", data["workers"][0])

    def test_worker_priority_changes_project_claim_order(self):
        self.app.create_task({"project_slug": "proyecto-a", "objective": "Tarea A", "task_type": "reasoning", "priority": 0})
        self.app.create_task({"project_slug": "proyecto-b", "objective": "Tarea B", "task_type": "reasoning", "priority": 0})
        with self.app.db() as conn:
            conn.execute("INSERT INTO worker_project_priority(worker_id,project_id,priority,enabled) VALUES(?,?,?,1)",
                         (self.worker_a["id"], self.project_b["id"], 50))
            conn.commit()
        claim = self.app.claim_task(self.worker_a, {"projects": ["proyecto-a", "proyecto-b"], "capabilities": ["reasoning"]})
        self.assertEqual(claim["task"]["project_slug"], "proyecto-b")

    def test_worker_capability_does_not_receive_implementation_by_default(self):
        self.app.create_task({"project_slug": "proyecto-a", "objective": "Implementar X", "task_type": "implementation"})
        claim = self.app.claim_task(self.worker_a, {"projects": ["proyecto-a"], "capabilities": ["reasoning", "light"]})
        self.assertIsNone(claim["task"])

    def test_patch_is_stored_and_visible_as_downloadable(self):
        tid = self.app.create_task({"project_slug": "proyecto-a", "objective": "Editar archivo", "task_type": "implementation"})["id"]
        with self.app.db() as conn:
            conn.execute("UPDATE tasks SET status='RUNNING',assigned_worker=?,attempts=1 WHERE id=?",
                         (self.worker_a["id"], tid))
            conn.commit()
        patch = "diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n+hello\n"
        result = self.app.finish_task(self.worker_a, tid, {"outcome": "done", "branch_name": "fabrica/task-1", "patch": patch})
        self.assertEqual(result["status"], "DONE")
        data = self.app.dashboard_data()
        self.assertTrue(data["tasks"][0]["patch_available"])
        with self.app.db() as conn:
            row = conn.execute("SELECT patch_text,integration_status FROM tasks WHERE id=?", (tid,)).fetchone()
            self.assertEqual(row["patch_text"], patch)
            self.assertEqual(row["integration_status"], "PATCH_READY")

    def test_auto_integration_queue_records_pushed_branch_and_commit(self):
        self.app.auto_push = True
        self.app.integration_repo = self.tmp / "target-repo"
        tid = self.app.create_task({"project_slug": "proyecto-a", "objective": "Editar archivo",
                                    "task_type": "implementation"})["id"]
        with self.app.db() as conn:
            conn.execute("UPDATE tasks SET status='RUNNING',assigned_worker=?,attempts=1 WHERE id=?",
                         (self.worker_a["id"], tid))
            conn.commit()
        patch_text = "diff --git a/src/a.py b/src/a.py\\n"
        self.app.finish_task(self.worker_a, tid, {"outcome": "done", "patch": patch_text})
        with self.app.db() as conn:
            row = conn.execute("SELECT integration_status FROM tasks WHERE id=?", (tid,)).fetchone()
        self.assertEqual(row["integration_status"], "QUEUED")

        with patch("fabrica.integration.push_patch",
                   return_value={"branch": f"fabrica/task-{tid}", "commit": "abc123", "already_pushed": False}):
            self.assertTrue(self.app.process_one_integration())
        with self.app.db() as conn:
            row = conn.execute("SELECT integration_status,integration_branch,integration_commit "
                               "FROM tasks WHERE id=?", (tid,)).fetchone()
        self.assertEqual(row["integration_status"], "PUSHED")
        self.assertEqual(row["integration_branch"], f"fabrica/task-{tid}")
        self.assertEqual(row["integration_commit"], "abc123")

    def test_transient_integration_error_retries_with_backoff(self):
        self.app.auto_push = True
        self.app.integration_repo = self.tmp / "target-repo"
        tid = self.app.create_task({"project_slug": "proyecto-a", "objective": "Editar archivo",
                                    "task_type": "implementation"})["id"]
        with self.app.db() as conn:
            conn.execute("UPDATE tasks SET status='DONE',patch_text='patch',integration_status='QUEUED' WHERE id=?", (tid,))
            conn.commit()
        with patch("fabrica.integration.push_patch", side_effect=RuntimeError("temporary network failure")):
            self.assertTrue(self.app.process_one_integration())
        with self.app.db() as conn:
            row = conn.execute("SELECT status,integration_status,integration_attempts,integration_not_before "
                               "FROM tasks WHERE id=?", (tid,)).fetchone()
            self.assertEqual(row["status"], "DONE")
            self.assertEqual(row["integration_status"], "QUEUED")
            self.assertEqual(row["integration_attempts"], 1)
            self.assertTrue(row["integration_not_before"])
            conn.execute("UPDATE tasks SET integration_not_before=? WHERE id=?",
                         (stamp(utcnow() - timedelta(seconds=1)), tid))
            conn.commit()
        with patch("fabrica.integration.push_patch",
                   return_value={"branch": f"fabrica/task-{tid}", "commit": "abc123", "already_pushed": False}):
            self.assertTrue(self.app.process_one_integration())
        with self.app.db() as conn:
            row = conn.execute("SELECT integration_status,integration_attempts,integration_commit FROM tasks WHERE id=?",
                               (tid,)).fetchone()
        self.assertEqual(row["integration_status"], "PUSHED")
        self.assertEqual(row["integration_attempts"], 1)
        self.assertEqual(row["integration_commit"], "abc123")

    def test_interrupted_integration_is_requeued_after_hub_restart(self):
        tid = self.app.create_task({"project_slug": "proyecto-a", "objective": "Editar archivo",
                                    "task_type": "implementation"})["id"]
        with self.app.db() as conn:
            conn.execute("UPDATE tasks SET status='DONE',patch_text='patch',integration_status='INTEGRATING' WHERE id=?",
                         (tid,))
            conn.commit()
        self.app.recover_interrupted_integrations()
        with self.app.db() as conn:
            row = conn.execute("SELECT integration_status,integration_error FROM tasks WHERE id=?", (tid,)).fetchone()
        self.assertEqual(row["integration_status"], "QUEUED")
        self.assertIn("reiniciado", row["integration_error"])

    def test_failed_integration_can_be_retried_without_rerunning_worker(self):
        self.app.auto_push = True
        self.app.integration_repo = self.tmp / "target-repo"
        tid = self.app.create_task({"project_slug": "proyecto-a", "objective": "Editar archivo",
                                    "task_type": "implementation"})["id"]
        with self.app.db() as conn:
            conn.execute("UPDATE tasks SET status='DONE',patch_text='patch',integration_status='FAILED' WHERE id=?",
                         (tid,))
            conn.commit()
        self.assertEqual(self.app.task_action(tid, "retry-integration")["status"], "QUEUED")
        with self.app.db() as conn:
            row = conn.execute("SELECT status,integration_status FROM tasks WHERE id=?", (tid,)).fetchone()
        self.assertEqual(row["status"], "DONE")
        self.assertEqual(row["integration_status"], "QUEUED")

    def test_infrastructure_failure_does_not_consume_retry(self):
        tid = self.app.create_task({"project_slug": "proyecto-a", "objective": "Tarea", "task_type": "reasoning", "max_retries": 1})["id"]
        task = self.app.claim_task(self.worker_a, {"projects": ["proyecto-a"], "capabilities": ["reasoning"]})["task"]
        self.app.finish_task(self.worker_a, tid, {"outcome": "infra", "error": "API unavailable"})
        with self.app.db() as conn:
            row = conn.execute("SELECT status,attempts,max_retries FROM tasks WHERE id=?", (tid,)).fetchone()
            self.assertEqual(row["status"], "PENDING")
            self.assertEqual(row["attempts"], 0)

    def test_expired_worker_lease_requeues_without_spending_retry(self):
        tid = self.app.create_task({"project_slug": "proyecto-a", "objective": "Tarea", "task_type": "reasoning", "max_retries": 0})["id"]
        self.app.claim_task(self.worker_a, {"projects": ["proyecto-a"], "capabilities": ["reasoning"]})
        with self.app.db() as conn:
            conn.execute("UPDATE tasks SET lease_until=? WHERE id=?", (stamp(utcnow() - timedelta(minutes=5)), tid))
            conn.commit()
        claim = self.app.claim_task(self.worker_b, {"projects": ["proyecto-a"], "capabilities": ["reasoning"]})
        self.assertEqual(claim["task"]["id"], tid)
        self.assertEqual(claim["task"]["attempts"], 1)

    def test_worker_joins_over_http_and_sends_heartbeat(self):
        invite = self.app.create_invite({"uses": 1, "hours": 1})["token"]
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.app))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            config_path = self.tmp / "client" / "worker.json"
            join_worker(f"http://127.0.0.1:{server.server_port}", invite, "HTTP Worker", config_path)
            worker = Worker(config_path)
            self.assertTrue(worker.heartbeat()["ok"])
            data = self.app.dashboard_data()
            connected = [item for item in data["workers"] if item["name"] == "HTTP Worker"]
            self.assertEqual(len(connected), 1)
            self.assertTrue(connected[0]["last_seen"])
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)

    def test_dashboard_requires_login_and_csrf_for_mutations(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.app))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            req = urllib.request.Request(base + "/api/admin/dashboard")
            with self.assertRaises(urllib.error.HTTPError) as err:
                urllib.request.urlopen(req)
            self.assertEqual(err.exception.code, 401)

            body = json.dumps({"password": self.app.admin_password}).encode()
            req = urllib.request.Request(base + "/api/login", data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req) as response:
                login = json.loads(response.read())
                cookie = response.headers["Set-Cookie"].split(";", 1)[0]
            csrf = login["csrf"]

            body = json.dumps({"name": "HTTP project", "slug": "http-project"}).encode()
            req = urllib.request.Request(base + "/api/admin/projects", data=body,
                headers={"Content-Type": "application/json", "Cookie": cookie})
            with self.assertRaises(urllib.error.HTTPError) as err:
                urllib.request.urlopen(req)
            self.assertEqual(err.exception.code, 403)

            req = urllib.request.Request(base + "/api/admin/projects", data=body,
                headers={"Content-Type": "application/json", "Cookie": cookie, "X-Fabrica-CSRF": csrf})
            with urllib.request.urlopen(req) as response:
                self.assertEqual(response.status, 201)
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)


    def test_failed_task_can_be_retried_and_pending_task_cancelled(self):
        retry_id = self.app.create_task({"project_slug": "proyecto-a", "objective": "Will fail", "task_type": "reasoning", "max_retries": 0})["id"]
        self.app.claim_task(self.worker_a, {"projects": ["proyecto-a"], "capabilities": ["reasoning"]})
        self.app.finish_task(self.worker_a, retry_id, {"outcome": "fail", "error": "agent failed"})
        self.assertEqual(self.app.task_action(retry_id, "retry")["status"], "PENDING")
        cancel_id = self.app.create_task({"project_slug": "proyecto-a", "objective": "Cancel me", "task_type": "reasoning"})["id"]
        self.assertEqual(self.app.task_action(cancel_id, "cancel")["status"], "CANCELLED")
        with self.app.db() as conn:
            rows = {r["id"]: r["status"] for r in conn.execute("SELECT id,status FROM tasks WHERE id IN (?,?)", (retry_id, cancel_id))}
        self.assertEqual(rows[retry_id], "PENDING")
        self.assertEqual(rows[cancel_id], "CANCELLED")

    def test_running_task_cancel_requires_consent_and_is_delivered_by_heartbeat(self):
        task_id = self.app.create_task({"project_slug": "proyecto-a", "objective": "Long task",
                                        "task_type": "reasoning"})["id"]
        claim = self.app.claim_task(self.worker_a, {"projects": ["proyecto-a"], "capabilities": ["reasoning"]})
        self.assertEqual(claim["task"]["id"], task_id)
        with self.assertRaises(PermissionError):
            self.app.task_action(task_id, "cancel")
        worker = self._worker_record(self.worker_a["id"])
        self.app.worker_heartbeat(worker, {"remote_control": True, "current_task_id": task_id})
        worker = self._worker_record(self.worker_a["id"])
        request = self.app.task_action(task_id, "cancel")
        self.assertEqual(request["status"], "CANCEL_REQUESTED")
        heartbeat = self.app.worker_heartbeat(worker, {"remote_control": True, "current_task_id": task_id})
        self.assertTrue(heartbeat["cancel_current_task"])
        finished = self.app.finish_task(worker, task_id, {"outcome": "cancelled", "error": "remote stop"})
        self.assertEqual(finished["status"], "CANCELLED")
        self.assertFalse(self.app.dashboard_data()["tasks"][0]["cancel_requested"])

    def test_provider_config_is_generated_per_worker_and_honors_shell_opt_in(self):
        cfg = {"agent": {"enabled": True, "model": "local/test", "providers": [
            {"id": "local", "base_url": "http://127.0.0.1:11434/v1", "models": {"test": {"name": "Test"}}}
        ], "allow_remote_code": True, "allow_shell": False}}
        target = make_opencode_config(cfg, self.tmp, "implementation")
        doc = json.loads(target.read_text())
        self.assertIn("providers", doc)
        self.assertNotIn("provider", doc)
        self.assertEqual(doc["providers"]["local"]["package"], "@opencode/ai/providers/openai-compatible")
        rules = doc["permissions"]
        self.assertEqual(next(r["effect"] for r in reversed(rules) if r["action"] == "shell" and r["resource"] == "*"), "deny")
        self.assertEqual(next(r["effect"] for r in reversed(rules) if r["action"] == "edit" and r["resource"] == "*"), "allow")
        self.assertEqual(worker_capabilities(cfg), ["reasoning", "light", "implementation"])

    def test_remote_control_requires_owner_consent_and_can_pause_resume(self):
        task_id = self.app.create_task({"project_slug": "proyecto-a", "objective": "Do work", "task_type": "reasoning"})["id"]
        worker = self._worker_record(self.worker_a["id"])
        with self.assertRaises(PermissionError):
            self.app.update_worker_control(self.worker_a["id"], {"desired_state": "PAUSED", "admin_prompt": ""})
        self.app.worker_heartbeat(worker, {"remote_control": True, "projects": ["proyecto-a"], "capabilities": ["reasoning"]})
        worker = self._worker_record(self.worker_a["id"])
        updated = self.app.update_worker_control(self.worker_a["id"], {
            "desired_state": "PAUSED", "admin_prompt": "Prioriza respuestas breves y pruebas reproducibles."
        })
        self.assertEqual(updated["desired_state"], "PAUSED")
        refreshed = self.app.worker_heartbeat(worker, {"remote_control": True})
        self.assertEqual(refreshed["desired_state"], "PAUSED")
        self.assertIn("pruebas reproducibles", refreshed["worker_prompt"])
        worker = self._worker_record(self.worker_a["id"])
        claim = self.app.claim_task(worker, {"projects": ["proyecto-a"], "capabilities": ["reasoning"]})
        self.assertIsNone(claim["task"])
        self.app.update_worker_control(self.worker_a["id"], {"desired_state": "RUNNING", "admin_prompt": "Instrucción de prueba"})
        worker = self._worker_record(self.worker_a["id"])
        claim = self.app.claim_task(worker, {"projects": ["proyecto-a"], "capabilities": ["reasoning"]})
        self.assertEqual(claim["task"]["id"], task_id)
        self.assertEqual(claim["task"]["worker_prompt"], "Instrucción de prueba")
        self.app.update_worker_control(self.worker_a["id"], {"desired_state": "PAUSED", "admin_prompt": "Prompt"})
        self.app.update_worker_control(self.worker_a["id"], {"admin_prompt": "Prompt actualizado"})
        self.assertEqual(self._worker_record(self.worker_a["id"])["desired_state"], "PAUSED")

    def test_local_opt_out_clears_remote_pause_prompt_and_pending_cancel(self):
        worker_id = self.worker_a["id"]
        task_id = self.app.create_task({"project_slug": "proyecto-a", "objective": "Long task",
                                        "task_type": "reasoning"})["id"]
        self.app.claim_task(self.worker_a, {"projects": ["proyecto-a"], "capabilities": ["reasoning"]})
        worker = self._worker_record(worker_id)
        self.app.worker_heartbeat(worker, {"remote_control": True, "current_task_id": task_id})
        self.app.update_worker_control(worker_id, {"desired_state": "PAUSED", "admin_prompt": "Prompt privado"})
        self.app.task_action(task_id, "cancel")
        worker = self._worker_record(worker_id)
        self.app.worker_heartbeat(worker, {"remote_control": False, "current_task_id": task_id})
        with self.app.db() as conn:
            row = conn.execute("SELECT desired_state,admin_prompt,metadata FROM workers WHERE id=?", (worker_id,)).fetchone()
            task = conn.execute("SELECT cancel_requested FROM tasks WHERE id=?", (task_id,)).fetchone()
        self.assertEqual(row["desired_state"], "RUNNING")
        self.assertEqual(row["admin_prompt"], "")
        self.assertFalse(json.loads(row["metadata"])["remote_control"])
        self.assertEqual(task["cancel_requested"], 0)

    def test_task_prompt_can_be_updated_through_dashboard_api(self):
        task_id = self.app.create_task({"project_slug": "proyecto-a", "objective": "Una tarea",
                                        "task_type": "reasoning"})["id"]
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.app))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            body = json.dumps({"password": self.app.admin_password}).encode()
            req = urllib.request.Request(base + "/api/login", data=body,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req) as response:
                login = json.loads(response.read())
                cookie = response.headers["Set-Cookie"].split(";", 1)[0]
            body = json.dumps({"task_prompt": "No agregues dependencias nuevas."}).encode()
            req = urllib.request.Request(base + f"/api/admin/tasks/{task_id}", data=body, method="PATCH",
                headers={"Content-Type": "application/json", "Cookie": cookie,
                         "X-Fabrica-CSRF": login["csrf"]})
            with urllib.request.urlopen(req) as response:
                self.assertEqual(response.status, 200)
            with self.app.db() as conn:
                saved = conn.execute("SELECT task_prompt FROM tasks WHERE id=?", (task_id,)).fetchone()[0]
            self.assertEqual(saved, "No agregues dependencias nuevas.")
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)

    def test_task_prompt_update_rejects_oversized_text(self):
        task_id = self.app.create_task({"project_slug": "proyecto-a", "objective": "Una tarea",
                                        "task_type": "reasoning"})["id"]
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.app))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            body = json.dumps({"password": self.app.admin_password}).encode()
            req = urllib.request.Request(base + "/api/login", data=body,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req) as response:
                login = json.loads(response.read())
                cookie = response.headers["Set-Cookie"].split(";", 1)[0]
            body = json.dumps({"task_prompt": "x" * 8001}).encode()
            req = urllib.request.Request(base + f"/api/admin/tasks/{task_id}", data=body, method="PATCH",
                headers={"Content-Type": "application/json", "Cookie": cookie,
                         "X-Fabrica-CSRF": login["csrf"]})
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(req)
            self.assertEqual(error.exception.code, 400)
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)

    def test_opencode_v2_provider_schema_and_default_shell_denial(self):
        cfg = {"agent": {"enabled": True, "model": "router/auto", "providers": [
            {"id": "router", "name": "Router", "base_url": "https://router.example/v1",
             "api_key_env": "FABRICA_KEY", "models": {"auto": {"name": "Auto"}}}
        ], "allow_remote_code": True, "allow_shell": False}}
        target = make_opencode_config(cfg, self.tmp, "implementation")
        doc = json.loads(target.read_text())
        self.assertIn("providers", doc)
        self.assertNotIn("provider", doc)
        self.assertEqual(doc["providers"]["router"]["package"], "@opencode/ai/providers/openai-compatible")
        self.assertEqual(doc["providers"]["router"]["env"], ["FABRICA_KEY"])
        rules = doc["permissions"]
        self.assertEqual(next(r["effect"] for r in reversed(rules) if r["action"] == "shell" and r["resource"] == "*"), "deny")
        self.assertEqual(next(r["effect"] for r in reversed(rules) if r["action"] == "edit" and r["resource"] == "*"), "allow")
        reasoning = json.loads(make_opencode_config(cfg, self.tmp, "reasoning").read_text())
        self.assertEqual(next(r["effect"] for r in reversed(reasoning["permissions"]) if r["action"] == "edit" and r["resource"] == "*"), "deny")

    def _worker_record(self, worker_id):
        with self.app.db() as conn:
            return dict(conn.execute("SELECT * FROM workers WHERE id=?", (worker_id,)).fetchone())

    def test_project_and_task_prompts_are_persisted(self):
        self.app.update_project_prompt("proyecto-a", {"agent_prompt": "Usá español rioplatense y verificá cambios."})
        task_id = self.app.create_task({"project_slug": "proyecto-a", "objective": "Do work",
                                        "task_type": "reasoning", "task_prompt": "No modifiques archivos."})["id"]
        claim = self.app.claim_task(self.worker_a, {"projects": ["proyecto-a"], "capabilities": ["reasoning"]})
        self.assertEqual(claim["task"]["project_prompt"], "Usá español rioplatense y verificá cambios.")
        self.assertEqual(claim["task"]["task_prompt"], "No modifiques archivos.")
        self.assertEqual(claim["task"]["id"], task_id)


if __name__ == "__main__":
    unittest.main()
