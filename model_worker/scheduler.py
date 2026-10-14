"""Bounded, non-preemptive admission to one local llama.cpp backend. Standard library only."""
from collections import deque
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
import threading
import time
import urllib.error
import urllib.request

MAX_BYTES = 4 * 1024 * 1024


class Rejected(Exception):
    pass


class BackendUncertain(Exception):
    """The backend may still be computing. Never schedule another request after this."""


@dataclass
class Job:
    path: str
    body: bytes
    deadline: float
    done: threading.Event = field(default_factory=threading.Event)
    started: bool = False
    result: object = None
    error: object = None
    admitted: float = field(default_factory=time.monotonic)
    started_at: float = 0.0


class Scheduler:
    def __init__(self, backend, capacity=16, wait_seconds=30):
        self.backend, self.capacity, self.wait_seconds = backend, capacity, wait_seconds
        self.condition = threading.Condition()
        self.queues = [deque(), deque()]
        self.active = None
        self.failed = None
        self.stopped = False
        self.completed = 0
        self.queue_seconds = 0.0
        self.backend_seconds = 0.0
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def status(self):
        with self.condition:
            return {"interactive_waiting": len(self.queues[0]), "background_waiting": len(self.queues[1]),
                    "active": self.active is not None, "failed": self.failed, "stopped": self.stopped,
                    "completed": self.completed, "capacity": self.capacity, "wait_seconds": self.wait_seconds,
                    "queue_seconds": self.queue_seconds, "backend_seconds": self.backend_seconds,
                    "active_behavior": "non_preemptive", "backend_timeout_seconds": 180}

    def submit(self, path, body, priority):
        if priority not in {"interactive", "background"}:
            raise Rejected("unknown priority")
        job = Job(path, body, time.monotonic() + self.wait_seconds)
        with self.condition:
            if self.failed or self.stopped:
                raise Rejected(self.failed or "scheduler stopped")
            # Reserve one waiting slot for interactive work during enrichment bursts.
            limit = self.capacity if priority == "interactive" else max(1, self.capacity - 1)
            if sum(map(len, self.queues)) >= limit:
                raise Rejected("generation queue full; retry later")
            self.queues[priority == "background"].append(job)
            self.condition.notify_all()
        while not job.done.wait(max(0.001, job.deadline - time.monotonic())):
            with self.condition:
                if not job.started and not job.done.is_set():
                    for queue in self.queues:
                        if job in queue: queue.remove(job)
                    job.error = Rejected("queue wait deadline exceeded; request was not executed")
                    job.done.set()
                started = job.started
            if started:
                # Backend calls have their own enforced timeout; do not cancel and overlap them.
                job.done.wait()
        if job.error: raise job.error
        return job.result

    def poison(self, reason):
        with self.condition:
            self.failed = str(reason)
            for queue in self.queues:
                while queue:
                    job = queue.popleft()
                    job.error = Rejected("backend state uncertain; restart required")
                    job.done.set()
            self.condition.notify_all()

    def close(self):
        self.poison("scheduler stopped")
        with self.condition:
            self.stopped = True
            self.condition.notify_all()

    def _run(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.stopped or (not self.failed and any(self.queues)))
                if self.stopped: return
                queue = self.queues[0] if self.queues[0] else self.queues[1]
                job = queue.popleft()
                if time.monotonic() >= job.deadline:
                    job.error = Rejected("queue wait deadline exceeded; request was not executed")
                    job.done.set()
                    continue
                job.started = True
                job.started_at = time.monotonic()
                self.queue_seconds += job.started_at - job.admitted
                self.active = job
            try:
                job.result = self.backend(job.path, job.body)
            except BackendUncertain as error:
                job.error = error
                self.poison(error)
            except Exception as error:
                job.error = error
            finally:
                with self.condition:
                    self.active = None
                    self.completed += 1
                    self.backend_seconds += time.monotonic() - job.started_at
                    job.done.set()


def backend_request(path, body=None):
    request = urllib.request.Request("http://127.0.0.1:8081" + path, data=body, headers={"Content-Type": "application/json"})
    timeout = 180 if path == "/v1/chat/completions" else (2 if body is None else 20)
    try:
        try:
            response = urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=timeout)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES: raise BackendUncertain("oversized backend response; restart required")
            return response.status, raw
    except (TimeoutError, socket.timeout, urllib.error.URLError, OSError) as error:
        raise BackendUncertain("backend disconnected or timed out; restart required") from error


def validate(path, body, priority):
    if path not in {"/apply-template", "/tokenize", "/v1/chat/completions"}:
        raise Rejected("unsupported model endpoint")
    data = json.loads(body)
    if not isinstance(data, dict): raise Rejected("expected an object")
    if path == "/v1/chat/completions":
        limit = 768 if priority == "interactive" else 256
        if (data.get("model") != "vectornext-gemma4-26b-a4b" or type(data.get("max_tokens")) is not int
                or not 1 <= data["max_tokens"] <= limit or data.get("stream", False) is not False
                or data.get("n", 1) != 1 or data.get("temperature") != 0):
            raise Rejected("invalid model, output budget, streaming, sample count, or temperature")
        allowed = {"model", "messages", "temperature", "seed", "max_tokens", "cache_prompt", "reasoning", "response_format", "stream", "n"}
        if set(data) - allowed: raise Rejected("unsupported generation option")
    return data


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 32

    def __init__(self, scheduler, address=("0.0.0.0", 8080)):
        self.scheduler = scheduler
        self.slots = threading.BoundedSemaphore(32)
        super().__init__(address, Handler)

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            try:
                request.settimeout(1)
                request.sendall(b"HTTP/1.0 503 Busy\r\nContent-Length: 0\r\n\r\n")
            finally: self.shutdown_request(request)
            return
        try: super().process_request(request, address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try: super().process_request_thread(request, address)
        finally: self.slots.release()


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *_):
        pass  # Never log source/request bodies.

    def reply(self, code, body):
        if not isinstance(body, bytes): body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try: self.wfile.write(body)
        except (OSError, TimeoutError): pass

    def do_GET(self):
        state = self.server.scheduler.status()
        if self.path == "/scheduler": return self.reply(200, state)
        if self.path != "/health": return self.reply(404, {"error": "unknown endpoint"})
        if state["failed"] or state["stopped"]: return self.reply(503, state)
        try: self.reply(*backend_request("/health"))
        except Exception: self.reply(503, {"status": "backend unavailable"})

    def do_POST(self):
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_BYTES or self.headers.get("Transfer-Encoding"):
                raise Rejected("invalid request size/encoding")
            body = self.rfile.read(size)
            if len(body) != size: raise Rejected("incomplete request")
            priority = self.headers.get("X-VectorNext-Priority", "background")
            validate(self.path, body, priority)
            code, response = self.server.scheduler.submit(self.path, body, priority)
            self.reply(code, response)
        except (Rejected, BackendUncertain) as error:
            self.reply(503, {"error": str(error)})
        except (ValueError, OSError) as error:
            self.reply(400, {"error": type(error).__name__})
        except Exception:
            self.reply(502, {"error": "backend operation failed"})
