"""Verify the pinned local artifact before starting the pinned llama.cpp binary."""
import signal
import subprocess
import threading
import sys
from model_worker.generator_profile import load, verify, validate_command

profile = load()
args = validate_command(profile, list(sys.argv[1:]))
verify(profile)
from model_worker.scheduler import Scheduler, Server, backend_request

for name, value in (("--host", "127.0.0.1"), ("--port", "8081")):
    args[args.index(name) + 1] = value
backend = subprocess.Popen(["/opt/llama/llama-server", *args])
scheduler = Scheduler(backend_request)
server = Server(scheduler, model_alias=profile['alias'])

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
