"""Local CPU service. No database mount; separate bounded interactive/background lanes."""
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_RPC = 4 * 1024 * 1024
MAX_PDF = 16 * 1024 * 1024
OPS = {'profile', 'stats', 'count', 'embed', 'generate', 'rerank', 'answer_tokens', 'answer', 'rewrite', 'plan_fields'}


class Busy(Exception): pass


class Lane:
    def __init__(self, command=None):
        self.command = command or [os.environ.get('MODEL_PYTHON', '/opt/model-env/bin/python'), '-m', 'model_worker.server']
        self.lock = threading.Lock()
        self.child = None
        self.ready = False
        self.error = None
        self.metrics_lock = threading.Lock()
        self.metrics = {}

    def stop(self):
        if self.child is not None:
            self.child.kill()
            self.child.wait(timeout=5)
            self.child.stdin.close(); self.child.stdout.close()
            self.child = None
        self.ready = False

    def exchange(self, body, timeout=420):
        """Caller owns lane admission. Bound both writing and reading the child pipes."""
        if len(body) > MAX_RPC or b'\n' in body: raise ValueError('invalid model frame')
        started = time.monotonic()
        operation = json.loads(body).get('op', 'unknown')
        operation = operation if operation in OPS else 'unknown'
        try:
            if self.child is None or self.child.poll() is not None:
                self.stop()
                self.child = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=sys.stderr, bufsize=0, env=os.environ | {'PYTHONPATH': '/app'})
                os.set_blocking(self.child.stdin.fileno(), False)
                os.set_blocking(self.child.stdout.fileno(), False)
            outgoing = body + b'\n'; sent = 0; response = bytearray()
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0: raise TimeoutError('CPU worker deadline exceeded')
                readable, writable, _ = select.select([self.child.stdout], [self.child.stdin] if sent < len(outgoing) else [], [], remaining)
                if writable:
                    sent += os.write(self.child.stdin.fileno(), outgoing[sent:sent+65536])
                if readable:
                    chunk = os.read(self.child.stdout.fileno(), 65536)
                    if not chunk: raise RuntimeError('CPU worker disconnected')
                    response.extend(chunk)
                    if len(response) > MAX_RPC: raise ValueError('CPU worker reply exceeds limit')
                    if b'\n' in response:
                        if not response.endswith(b'\n') or response.count(b'\n') != 1: raise ValueError('invalid CPU worker frame')
                        parsed = json.loads(response)
                        if not isinstance(parsed, dict) or set(parsed) not in ({'result'}, {'error'}): raise ValueError('invalid CPU worker envelope')
                        self.ready = True; self.error = None
                        return bytes(response)
        except Exception as error:
            self.error = type(error).__name__
            self.stop()
            raise
        finally:
            with self.metrics_lock:
                count, seconds = self.metrics.get(operation, (0, 0.0))
                self.metrics[operation] = (count+1, seconds+time.monotonic()-started)

    def call(self, body, timeout=420):
        if not self.lock.acquire(blocking=False): raise Busy('CPU lane busy; retry later')
        try: return self.exchange(body, timeout)
        finally: self.lock.release()

    def status(self):
        with self.metrics_lock: metrics = dict(self.metrics)
        return {'ready': self.ready, 'busy': self.lock.locked(), 'last_transport_error': self.error,
            'operations_calls_seconds': metrics}


class Runtime:
    def __init__(self):
        self.lanes = {'interactive': Lane(), 'background': Lane()}
        self.pdf_ready = False
        self.reranker_ready = False
        self.pdf_error = None

    def warm(self):
        for name, lane in self.lanes.items():
            try:
                result = json.loads(lane.call(b'{"op":"profile"}', 45))
                if 'error' in result: raise ValueError('model profile unavailable')
                if name == 'interactive':
                    result = json.loads(lane.call(b'{"op":"rerank","input":{"query":"readiness","passages":["readiness"]}}', 45))
                    self.reranker_ready = 'result' in result
            except Exception as error:
                lane.ready = False; lane.error = type(error).__name__
        try:
            subprocess.run([sys.executable, '-m', 'processor.assets', 'verify', '/models'],
                check=True, timeout=45, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.pdf_ready = True
        except Exception as error: self.pdf_error = type(error).__name__

    def health(self):
        generation = {'ready': False}
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(os.environ.get('VECTORNEXT_LLM_URL', 'http://llm:8080')+'/health', timeout=1) as response:
                generation = {'ready': response.status == 200}
            with opener.open(os.environ.get('VECTORNEXT_LLM_URL', 'http://llm:8080')+'/scheduler', timeout=1) as response:
                generation['scheduler'] = json.load(response)
        except Exception as error: generation['error'] = type(error).__name__
        return {'service': 'processor', 'lanes': {n:l.status() for n,l in self.lanes.items()},
            'capabilities': {'embedding': self.lanes['interactive'].ready, 'reranking': self.reranker_ready and self.lanes['interactive'].ready,
                             'pdf': self.pdf_ready, 'generation': generation['ready']}, 'generation': generation,
            'pdf_error': self.pdf_error, 'gpu_access': False}

    def pdf(self, body):
        lane = self.lanes['background']
        if not lane.lock.acquire(blocking=False): raise Busy('background CPU lane busy; retry PDF upload later')
        try:
            with tempfile.TemporaryDirectory(prefix='vectornext-pdf-') as directory:
                root = Path(directory); (root/'source.pdf').write_bytes(body)
                with (root/'conversion.log').open('wb') as log:
                    child = subprocess.Popen([sys.executable, '-m', 'processor.pdf', str(root/'source.pdf'), str(root/'artifact.json')],
                        stdout=log, stderr=log, start_new_session=True)
                    try:
                        code = child.wait(timeout=185)
                    finally:
                        # Includes any OCR descendants even when the parent alarm exits first.
                        try: os.killpg(child.pid, signal.SIGKILL)
                        except ProcessLookupError: pass
                        child.wait(timeout=5)
                    if code != 0: raise ValueError(f'PDF conversion failed (exit {code}); no upload was committed')
                path = root/'artifact.json'
                if not path.is_file() or path.stat().st_size > MAX_PDF: raise ValueError('invalid PDF artifact size')
                self.pdf_ready = True; self.pdf_error = None
                return path.read_bytes()
        finally: lane.lock.release()


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 16
    def __init__(self, address, runtime):
        self.runtime = runtime; self.slots = threading.BoundedSemaphore(16)
        super().__init__(address, Handler)
    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            try:
                request.settimeout(1)
                body=b'{"code":"busy","error":"CPU HTTP admission full"}'
                request.sendall(b'HTTP/1.0 503 Busy\r\nContent-Type: application/json\r\nContent-Length: '+str(len(body)).encode()+b'\r\n\r\n'+body)
            finally: self.shutdown_request(request)
            return
        try: super().process_request(request, address)
        except Exception: self.slots.release(); raise
    def process_request_thread(self, request, address):
        try: super().process_request_thread(request, address)
        finally: self.slots.release()


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup(); self.connection.settimeout(15)
    def log_message(self, *_): pass
    def reply(self, code, value):
        body = value if isinstance(value, bytes) else json.dumps(value).encode()
        self.send_response(code); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(body))); self.end_headers()
        try: self.wfile.write(body)
        except OSError: pass
    def do_GET(self):
        if self.path == '/live': return self.reply(200, {'status':'ok'})
        if self.path == '/health': return self.reply(200, self.server.runtime.health())
        self.reply(404, {'error':'unknown endpoint'})
    def do_POST(self):
        try:
            if self.path in ('/generation/acquire', '/generation/release', '/generation/reconcile', '/generation/cancel'):
                size = int(self.headers.get('Content-Length', '0'))
                if self.headers.get('Transfer-Encoding') or not 0 < size <= 4096:
                    raise ValueError('invalid generation control request')
                body = self.rfile.read(size)
                if len(body) != size: raise ValueError('incomplete control request')
                url = os.environ.get('VECTORNEXT_LLM_URL', 'http://llm:8080') + self.path.replace('/generation/', '/control/')
                req = urllib.request.Request(url, data=body, headers={'Content-Type':'application/json'})
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                try:
                    response = opener.open(req, timeout=285)
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    return self.reply(response.status, response.read(65537))
            is_pdf = self.path == '/pdf'
            if not is_pdf and self.path not in ('/rpc/interactive','/rpc/background'): return self.reply(404, {'error':'unknown endpoint'})
            size = int(self.headers.get('Content-Length','0'))
            if self.headers.get('Transfer-Encoding') or not 0 < size <= (MAX_PDF if is_pdf else MAX_RPC): raise ValueError('invalid body size')
            body = self.rfile.read(size)
            if len(body) != size: raise ValueError('incomplete body')
            if is_pdf: return self.reply(200, self.server.runtime.pdf(body))
            parsed = json.loads(body)
            if not isinstance(parsed, dict) or parsed.get('op') not in OPS: raise ValueError('invalid model operation')
            lane = self.server.runtime.lanes[self.path.rsplit('/',1)[1]]
            # Compact exact bytes are supplied by Rust; no parsed source-number reserialization.
            timeout = 720 if parsed['op'] == 'answer' else 420
            self.reply(200, lane.call(body, timeout))
        except Busy as error: self.reply(503, {'code':'busy','error':str(error)})
        except (ValueError, OSError) as error: self.reply(400, {'error':str(error)[:1000]})
        except Exception as error: self.reply(503, {'error':type(error).__name__})


def main():
    runtime = Runtime(); server = Server(('0.0.0.0',8090), runtime)
    threading.Thread(target=runtime.warm, daemon=True).start()
    server.serve_forever()

if __name__ == '__main__': main()
