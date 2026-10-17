"""One GPU backend, with an identity-bound lease spanning an entire attempt."""
import json
import subprocess
import threading
import time
from .generator_profile import load, verify, command, runtime_identity, answer_temperature, answer_adapter
from .scheduler import Scheduler, Rejected, BackendUncertain, backend_request, validate

from .generator_profile import MODEL_PROFILES as PROFILES


class Supervisor:
    def __init__(self, spawn=subprocess.Popen, backend=backend_request, verifier=verify, activation_seconds=240):
        self.spawn, self.backend, self.verifier = spawn, backend, verifier
        self.activation_seconds = activation_seconds
        self.condition = threading.Condition()
        self.child = self.scheduler = self.loaded = self.lease = None
        self.loading = self.failed = None
        self.calls = self.interactive_waiting = 0
        self.stopped = False
        self.initializing = False
        self.activations, self.available = [], {}
        self.reconciled_owner = None

    def status(self):
        with self.condition:
            return {'loaded_model': self.loaded, 'loading_model': self.loading,
                    'lease': None if self.lease is None else {k: self.lease[k] for k in ('model', 'priority', 'owner')},
                    'models': dict(self.available), 'failed': self.failed, 'stopped': self.stopped,
                    'active': bool(self.calls), 'interactive_waiting': self.interactive_waiting,
                    'queue_ready': not self.stopped and not self.initializing and any(self.available.values()),
                    'activations': self.activations[-20:]}

    def _retire(self):
        # Activation/reconciliation owns this operation; no inference is in flight.
        if self.scheduler:
            self.scheduler.close()
            self.scheduler.thread.join(timeout=5)
            self.scheduler = None
        if self.child:
            if self.child.poll() is None:
                self.child.terminate()
            try:
                self.child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.child.kill()
                self.child.wait(timeout=10)
            if self.child.poll() is None:
                raise BackendUncertain('old backend could not be reaped')
            self.child = None
        self.loaded = None

    def _activate(self, model):
        if self.loaded == model and not self.failed and self.child and self.child.poll() is None:
            return 0.0
        started = time.monotonic()
        with self.condition:
            self.loading = model
        try:
            self._retire()
            profile = load(PROFILES[model])
            self.verifier(profile)
            args = command(profile)
            args[args.index('--host')+1] = '127.0.0.1'
            args[args.index('--port')+1] = '8081'
            self.child = self.spawn(['/opt/llama/llama-server', *args])
            while time.monotonic() - started < self.activation_seconds:
                if self.child.poll() is not None:
                    raise BackendUncertain('backend exited during activation')
                try:
                    code, raw = self.backend('/health')
                    if code == 200:
                        code, raw = self.backend('/v1/models')
                        if code != 200 or profile['alias'] not in [v['id'] for v in json.loads(raw)['data']]:
                            raise ValueError('activated model alias does not match its profile')
                        self.scheduler = Scheduler(self.backend)
                        self.loaded, self.failed = model, None
                        self.available[model] = True
                        elapsed = time.monotonic() - started
                        self.activations.append({'model': model, 'seconds': elapsed, 'runtime': runtime_identity(profile),
                                                 'artifact_sha256': profile['artifact']['sha256']})
                        return elapsed
                except BackendUncertain:
                    pass
                time.sleep(.2)
            raise BackendUncertain('model activation exceeded 240 seconds')
        except Exception as error:
            self._retire()
            self.failed = str(error)
            raise
        finally:
            with self.condition:
                self.loading = None
                self.condition.notify_all()

    def acquire(self, value):
        model, token, owner, priority = (value.get(k) for k in ('model', 'token', 'owner', 'priority'))
        if model not in PROFILES or priority not in ('interactive', 'background'):
            raise Rejected('unsupported model or priority')
        if any(not isinstance(v, str) or not 16 <= len(v) <= 128 for v in (token, owner)):
            raise Rejected('invalid lease identity')
        with self.condition:
            if self.initializing and owner != 'supervisor-initial-load':
                raise Rejected('model lease admission busy; initial model verification/loading')
            if self.lease and self.lease['token'] == token:
                raise Rejected('lease acquisition already attempted; reconcile uncertain outcomes')
            deadline = time.monotonic() + 30
            self.interactive_waiting += priority == 'interactive'
            try:
                while self.lease or self.loading or (priority == 'background' and self.interactive_waiting):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise Rejected('model lease admission busy; request was not executed')
                    self.condition.wait(remaining)
                if self.stopped:
                    raise Rejected('supervisor stopped')
                self.lease = dict(model=model, token=token, owner=owner, priority=priority)
            finally:
                self.interactive_waiting -= priority == 'interactive'
        try:
            seconds = self._activate(model)
            profile = load(PROFILES[model])
            return {'token': token, 'model': model, 'alias': profile['alias'], 'profile': profile['name'],
                    'runtime': runtime_identity(profile), 'artifact_sha256': profile['artifact']['sha256'],
                    'activation_seconds': seconds}
        except Exception:
            with self.condition:
                self.lease = None
                self.condition.notify_all()
            raise

    def submit(self, path, body, priority, token, model):
        with self.condition:
            if (not self.lease or self.lease['token'] != token or self.lease['model'] != model
                    or self.lease['priority'] != priority or self.loaded != model or self.failed):
                raise Rejected('missing, stale or mismatched model lease')
            if self.lease.get('cancelled'):
                raise Rejected('answer cancelled; no further generation stages will run')
            profile = load(PROFILES[model])
            validate(path, body, priority, profile['alias'], answer_temperature(profile), answer_adapter(profile))
            self.calls += 1
        try:
            return self.scheduler.submit(path, body, priority)
        except BackendUncertain as error:
            with self.condition:
                self.failed = str(error)
            raise
        finally:
            with self.condition:
                self.calls -= 1
                self.condition.notify_all()

    def cancel(self, value):
        # Do not preempt the active backend call. Every subsequent operation,
        # including extraction after assessment in one worker RPC, is rejected.
        with self.condition:
            if self.lease and self.lease['token'] == value.get('token'):
                self.lease['cancelled'] = True
            return {'cancel_requested': True}

    def release(self, value):
        with self.condition:
            if not self.lease:
                return {'released': True}
            if self.lease['token'] != value.get('token'):
                raise Rejected('lease release identity mismatch')
            self.condition.wait_for(lambda: not self.calls)
            if self.failed:
                self._retire()
            self.lease = None
            self.condition.notify_all()
            return {'released': True}

    def reconcile(self, value):
        owner = value.get('owner')
        if not isinstance(owner, str) or not 16 <= len(owner) <= 128:
            raise Rejected('invalid coordinator identity')
        with self.condition:
            if self.reconciled_owner == owner:
                return {'reconciled': True}
            self.condition.wait_for(lambda: not self.calls and not self.loading and
                                    (not self.lease or self.lease['priority'] == 'interactive'))
            if self.lease or self.failed:
                self._retire()
                self.lease = None
            self.reconciled_owner = owner
            self.condition.notify_all()
            return {'reconciled': True}

    def initialize(self):
        for model, name in PROFILES.items():
            try:
                self.verifier(load(name))
                self.available[model] = True
            except Exception:
                self.available[model] = False
        token = 'supervisor-initial-load'
        try:
            self.acquire({'model': 'nuextract', 'token': token, 'owner': token, 'priority': 'background'})
        finally:
            self.release({'token': token})
            with self.condition:
                self.initializing = False
                self.condition.notify_all()

    def close(self):
        with self.condition:
            self.stopped = True
            self.condition.wait_for(lambda: not self.calls and not self.loading)
            self._retire()
            self.condition.notify_all()
