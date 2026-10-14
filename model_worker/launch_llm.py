"""Verify the pinned local artifact before starting the pinned llama.cpp binary."""
import hashlib
import json
import signal
import subprocess
import threading
from pathlib import Path
import sys

spec = json.loads(Path("/models.lock.json").read_text())["models"]["generator"]
artifact = next(f for f in spec["files"] if f["path"].endswith(".gguf"))
path = Path("/models") / spec["directory"] / artifact["path"]
with path.open("rb") as f:
    actual = hashlib.file_digest(f, "sha256").hexdigest()
if path.stat().st_size != artifact["size"] or actual != artifact["sha256"]:
    raise ValueError("missing/corrupt generation artifact")
from scheduler import Scheduler, Server, backend_request

args = list(sys.argv[1:])
for name, value in (("--host", "127.0.0.1"), ("--port", "8081")):
    args[args.index(name) + 1] = value
backend = subprocess.Popen(["/opt/llama/llama-server", *args])
scheduler = Scheduler(backend_request)
server = Server(scheduler)

def stop(*_):
    scheduler.close()
    backend.terminate()
    # shutdown must run outside the serve_forever thread.
    threading.Thread(target=server.shutdown, daemon=True).start()

def watch():
    backend.wait()
    scheduler.poison("llama.cpp exited; restart required")

threading.Thread(target=watch, daemon=True).start()
signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
try:
    server.serve_forever()
finally:
    scheduler.close()
    backend.terminate()
    try: backend.wait(timeout=10)
    except subprocess.TimeoutExpired:
        backend.kill()
        backend.wait()
    server.server_close()
