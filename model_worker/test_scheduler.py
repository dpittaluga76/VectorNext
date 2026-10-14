import concurrent.futures
import json
import threading
import time
import unittest
from .scheduler import Scheduler, Rejected, BackendUncertain, validate


def until(predicate):
    deadline = time.monotonic() + 3
    while not predicate():
        if time.monotonic() > deadline: raise AssertionError("condition timed out")
        time.sleep(.005)


class SchedulerTests(unittest.TestCase):
    def test_priority_fifo_nonpreemption_and_health_state(self):
        active = threading.Event(); release = threading.Event(); order = []
        def backend(path, body):
            order.append(path)
            if path == "active": active.set(); self.assertTrue(release.wait(3))
            return 200, body
        scheduler = Scheduler(backend, wait_seconds=3)
        self.addCleanup(scheduler.close)
        with concurrent.futures.ThreadPoolExecutor(4) as pool:
            first = pool.submit(scheduler.submit, "active", b"a", "background")
            self.assertTrue(active.wait(3))
            background = pool.submit(scheduler.submit, "background", b"b", "background")
            until(lambda: scheduler.status()["background_waiting"] == 1)
            interactive = pool.submit(scheduler.submit, "interactive", b"c", "interactive")
            until(lambda: scheduler.status()["interactive_waiting"] == 1)
            last = pool.submit(scheduler.submit, "last", b"d", "interactive")
            until(lambda: scheduler.status()["interactive_waiting"] == 2)
            self.assertTrue(scheduler.status()["active"])
            release.set()
            for f in (first, background, interactive, last): self.assertEqual(f.result()[0], 200)
        self.assertEqual(order, ["active", "interactive", "last", "background"])
        metrics = scheduler.status()
        self.assertEqual(metrics['completed'], 4)
        self.assertGreater(metrics['queue_seconds'], 0)
        self.assertGreater(metrics['backend_seconds'], 0)

    def test_capacity_deadline_and_no_execution_after_expiry(self):
        active = threading.Event(); release = threading.Event(); seen = []
        def backend(path, body):
            seen.append(path); active.set(); release.wait(3); return 200, body
        scheduler = Scheduler(backend, capacity=2, wait_seconds=.12)
        self.addCleanup(scheduler.close)
        with concurrent.futures.ThreadPoolExecutor(3) as pool:
            a = pool.submit(scheduler.submit, "active", b"", "background")
            self.assertTrue(active.wait(3))
            b = pool.submit(scheduler.submit, "expired", b"", "background")
            until(lambda: scheduler.status()["background_waiting"] == 1)
            with self.assertRaisesRegex(Rejected, "full"):
                scheduler.submit("full", b"", "background")
            with self.assertRaisesRegex(Rejected, "deadline"): b.result()
            release.set(); a.result()
        self.assertEqual(seen, ["active"])

    def test_uncertain_backend_poisons_later_admission(self):
        def backend(*_): raise BackendUncertain("timeout")
        scheduler = Scheduler(backend)
        self.addCleanup(scheduler.close)
        with self.assertRaises(BackendUncertain): scheduler.submit("first", b"", "interactive")
        with self.assertRaises(Rejected): scheduler.submit("next", b"", "interactive")
        self.assertEqual(scheduler.status()["completed"], 1)

    def test_request_bounds(self):
        good = {"model": "vectornext-gemma4-26b-a4b", "max_tokens": 768, "temperature": 0}
        validate("/v1/chat/completions", json.dumps(good), "interactive")
        with self.assertRaises(Rejected): validate("/v1/chat/completions", json.dumps(good), "background")
        for change in ({"stream": True}, {"n": 2}, {"max_tokens": -1}, {"model": "other"}, {"n_predict": -1}):
            with self.assertRaises(Rejected): validate("/v1/chat/completions", json.dumps(good | change), "interactive")
        with self.assertRaises(Rejected): validate("/completion", "{}", "interactive")


if __name__ == "__main__": unittest.main()
