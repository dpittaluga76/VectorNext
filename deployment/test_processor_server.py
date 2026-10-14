import json
import sys
import unittest
from .processor_server import Lane, Busy


class LaneTests(unittest.TestCase):
    def lane(self, code):
        lane=Lane([sys.executable,'-u','-c',code]); self.addCleanup(lane.stop); return lane
    def test_exact_frames_and_reuse(self):
        lane=self.lane('import sys\nfor line in sys.stdin.buffer:\n sys.stdout.buffer.write(b\'{"result":\'+line.strip()+b\'}\\n\'); sys.stdout.buffer.flush()')
        raw=b'{"precise":9007199254740993.00000000000001}'
        self.assertIn(raw,lane.call(raw)); child=lane.child.pid
        lane.call(b'{"second":true}'); self.assertEqual(lane.child.pid,child)
    def test_background_admission_cannot_block_interactive_lane(self):
        one=self.lane('import sys\nfor line in sys.stdin: print(\'{"result":1}\',flush=True)')
        two=self.lane('import sys\nfor line in sys.stdin: print(\'{"result":2}\',flush=True)')
        one.lock.acquire()
        try:
            with self.assertRaises(Busy): one.call(b'{}')
            self.assertEqual(json.loads(two.call(b'{}'))['result'],2)
        finally: one.lock.release()
    def test_timeout_kills_worker_and_new_request_restarts(self):
        lane=self.lane('import time; time.sleep(20)')
        with self.assertRaises(TimeoutError): lane.call(b'{}',timeout=.05)
        self.assertIsNone(lane.child); self.assertFalse(lane.ready)
        lane.command=[sys.executable,'-u','-c','import sys\nfor line in sys.stdin: print(\'{"result":3}\',flush=True)']
        self.assertEqual(json.loads(lane.call(b'{}'))['result'],3)
    def test_invalid_and_oversized_frames_fail_closed(self):
        for code in ("print('invalid',flush=True)","print('x'*4194305,flush=True)"):
            lane=self.lane(code)
            with self.assertRaises((ValueError,RuntimeError)): lane.call(b'{}')
            self.assertIsNone(lane.child)

if __name__=='__main__': unittest.main()
