import json
import threading
import time
import unittest
from unittest.mock import patch
from .supervisor import Supervisor, PROFILES
from .generator_profile import load
from .scheduler import Rejected, BackendUncertain


class Child:
    def __init__(self, args, children):
        assert all(c.code is not None for c in children), 'overlapping GPU backends'
        self.args, self.code = args, None
        children.append(self)
    def poll(self): return self.code
    def terminate(self): self.code = 0
    def kill(self): self.code = -9
    def wait(self, timeout=None): return self.code


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.children = []
        self.failure = None
        self.manager = Supervisor(spawn=lambda args: Child(args, self.children),
                                  backend=self.backend, verifier=lambda _: None, activation_seconds=.05)
    def tearDown(self): self.manager.close()
    def backend(self, path, body=None):
        if self.failure: raise self.failure
        if path == '/v1/models':
            args = self.children[-1].args
            return 200, json.dumps({'data':[{'id':args[args.index('--alias')+1]}]}).encode()
        return 200, b'{"status":"ok"}'
    def lease(self, model='nuextract', token='synthetic-lease-token', priority='interactive'):
        value = dict(model=model, token=token, owner='synthetic-owner-0001', priority=priority)
        self.manager.acquire(value)
        return value
    def test_three_transitions_reap_previous_and_keep_idle_model(self):
        for i, model in enumerate(['nuextract','gemma','nuextract']):
            lease = self.lease(model, f'synthetic-lease-{i:04}')
            self.assertEqual(self.manager.status()['loaded_model'], model)
            self.manager.release(lease)
            self.assertEqual(self.manager.loaded, model)
        self.assertEqual(len(self.children),3)
        self.assertIsNone(self.children[-1].poll())
    def test_wrong_model_and_token_never_reach_backend(self):
        lease = self.lease()
        for model, token in [('gemma',lease['token']),('nuextract','wrong')]:
            with self.assertRaises(Rejected): self.manager.submit('/tokenize',b'{}','interactive',token,model)
        self.assertEqual(self.manager.submit('/tokenize',b'{}','interactive',lease['token'],'nuextract')[0],200)
    def test_alias_temperature_and_native_template_are_validated(self):
        lease = self.lease()
        body = {'model':load(PROFILES['nuextract'])['alias'],'max_tokens':768,'temperature':.2}
        self.manager.submit('/v1/chat/completions',json.dumps(body),'interactive',lease['token'],'nuextract')
        for key, value in [('model',load('12b')['alias']),('temperature',0)]:
            with self.assertRaises(Rejected):
                self.manager.submit('/v1/chat/completions',json.dumps({**body,key:value}),'interactive',lease['token'],'nuextract')
    def test_activation_failure_reaps_and_does_not_silently_substitute(self):
        self.failure = BackendUncertain('backend offline')
        with self.assertRaises(BackendUncertain): self.lease()
        self.assertIsNone(self.manager.child)
        self.assertIsNone(self.manager.lease)
        self.assertEqual(len(self.children),1)
    def test_background_uses_selected_temperature_without_changing_saved_gemma(self):
        for model, temperature in [('nuextract',.2),('gemma',0)]:
            lease = self.lease(model, 'background-' + model, 'background')
            body = {'model':load(PROFILES[model])['alias'],'max_tokens':256,'temperature':temperature}
            self.manager.submit('/v1/chat/completions',json.dumps(body),'background',lease['token'],model)
            with self.assertRaises(Rejected):
                self.manager.submit('/v1/chat/completions',json.dumps({**body,'temperature':1}),'background',lease['token'],model)
            self.manager.release(lease)
    def test_artifact_failure_never_spawns_a_backend(self):
        self.manager.verifier = lambda _: (_ for _ in ()).throw(ValueError('corrupt artifact'))
        with self.assertRaisesRegex(ValueError,'corrupt'): self.lease()
        self.assertEqual(self.children,[])
    def test_uncertain_call_retires_scheduler_before_new_model(self):
        lease = self.lease()
        old = self.manager.scheduler
        self.failure = BackendUncertain('timeout')
        with self.assertRaises(BackendUncertain):
            self.manager.submit('/tokenize',b'{}','interactive',lease['token'],'nuextract')
        self.manager.release(lease)
        self.assertTrue(old.failed)
        self.failure = None
        self.lease('gemma','next-synthetic-token')
        self.assertIsNot(self.manager.scheduler,old)
        self.assertIsNotNone(self.children[0].poll())
    def test_restart_reconciliation_reaps_orphan_without_replaying(self):
        self.lease()
        self.manager.reconcile({'owner':'new-api-owner-0002'})
        self.assertIsNone(self.manager.lease)
        self.assertIsNone(self.manager.child)
        self.assertEqual(len(self.children),1)
    def test_active_call_is_not_preempted_by_switch_or_cancellation(self):
        lease = self.lease()
        entered, finish = threading.Event(), threading.Event()
        def slow(path, body): entered.set(); finish.wait(2); return 200,b'{}'
        self.manager.scheduler.backend = slow
        active = threading.Thread(target=lambda:self.manager.submit('/tokenize',b'{}','interactive',lease['token'],'nuextract'))
        active.start(); self.assertTrue(entered.wait(1))
        released = threading.Event()
        release = threading.Thread(target=lambda:(self.manager.release(lease),released.set()))
        release.start(); self.assertFalse(released.wait(.05))
        self.assertIsNone(self.children[0].poll())
        finish.set(); active.join(); release.join(); self.assertTrue(released.is_set())
    def test_interactive_waiter_precedes_waiting_background(self):
        initial = self.lease(priority='background')
        order=[]
        def attempt(priority):
            lease=self.lease('gemma',f'{priority}-synthetic-token',priority)
            order.append(priority); self.manager.release(lease)
        interactive=threading.Thread(target=attempt,args=('interactive',)); interactive.start()
        deadline=time.monotonic()+1
        while not self.manager.interactive_waiting and time.monotonic()<deadline: time.sleep(.001)
        background=threading.Thread(target=attempt,args=('background',)); background.start()
        self.manager.release(initial); interactive.join(2); background.join(2)
        self.assertEqual(order,['interactive','background'])

    def test_cancel_finishes_active_call_but_blocks_extraction(self):
        lease = self.lease()
        entered, finish = threading.Event(), threading.Event()
        def slow(path, body): entered.set(); finish.wait(2); return 200, b'{}'
        self.manager.scheduler.backend = slow
        active = threading.Thread(target=lambda:self.manager.submit('/tokenize',b'{}','interactive',lease['token'],'nuextract'))
        active.start(); self.assertTrue(entered.wait(1))
        self.manager.cancel(lease)
        self.assertEqual(self.manager.calls, 1)
        finish.set(); active.join()
        with self.assertRaisesRegex(Rejected, 'cancelled'):
            self.manager.submit('/tokenize',b'{}','interactive',lease['token'],'nuextract')
        self.manager.release(lease)


if __name__ == '__main__': unittest.main()
