import sys
import threading
import time
import unittest

from fabrica import proc


class ProcessCancelTests(unittest.TestCase):
    def test_authorized_cancel_terminates_only_launched_process_tree(self):
        cancel = threading.Event()
        def request_cancel():
            time.sleep(0.6)
            cancel.set()
        thread = threading.Thread(target=request_cancel, daemon=True)
        thread.start()
        started = time.monotonic()
        result = proc.run_cmd([sys.executable, "-c", "import time; time.sleep(20)"],
                              timeout=30, cancel_event=cancel)
        elapsed = time.monotonic() - started
        thread.join(timeout=2)
        self.assertEqual(result.returncode, -2)
        self.assertIn("detenido por solicitud", result.stderr)
        self.assertLess(elapsed, 5)


if __name__ == "__main__":
    unittest.main()
