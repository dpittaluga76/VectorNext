import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from .oracle import capture


class OracleTests(unittest.TestCase):
    def fixture(self,root):
        raw=b'{"question":"Synthetic test count?","history":[],"fields":{"count":{"kind":"number","nullable":false}},"evidence":[{"id":"E1","text":"{\\\"count\\\":9007199254740993.123456789}","record":{"count":9007199254740993.123456789}}],"constrain_pointers":true}'
        (root/'input.json').write_bytes(raw)
        (root/'review.json').write_text(json.dumps({'approved':True,'reviewer':'synthetic-test-only',
            'independent_of_implementation':True,'date':'test-fixture','split':'development',
            'approved_inputs':{'test':hashlib.sha256(raw).hexdigest()}}),encoding='utf-8')
        return raw

    def test_same_exact_input_and_lease_no_retries(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); raw=self.fixture(root); calls=[]; lease={}
            def transport(path,body,timeout):
                calls.append((path,body))
                if path.endswith('acquire'):
                    lease.update(json.loads(body)); return json.dumps(lease).encode()
                if path.endswith('release'): return b'{"released":true}'
                self.assertIn(raw,body)
                self.assertEqual(json.loads(body)['lease'],lease)
                return b'{"result":100}' if b'answer_tokens' in body else b'{"result":{"answer":{"status":"insufficient_evidence","fields":{}}}}'
            result=capture(root/'input.json',root/'review.json','test','nuextract','http://processor:8090',root/'out',transport=transport)
            self.assertEqual(result['state'],'captured')
            self.assertEqual(len(calls),4)
            self.assertEqual((root/'out/input.json').read_bytes(),raw)
            with self.assertRaises(FileExistsError):
                capture(root/'input.json',root/'review.json','test','nuextract','http://processor:8090',root/'out',transport=transport)

    def test_budget_failure_keeps_attempt_and_releases_without_answer(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root);calls=[]
            def transport(path,body,timeout):
                calls.append(path)
                if path.endswith('acquire'): return body
                if path.endswith('release'): return b'{}'
                return b'{"result":3329}'
            result=capture(root/'input.json',root/'review.json','test','gemma','http://processor:8090',root/'out',transport=transport)
            self.assertEqual(result['state'],'failed_or_uncertain')
            self.assertEqual(len(calls),3)
            self.assertFalse((root/'out/answer.request.json').exists())

    def test_unreviewed_or_changed_inputs_never_contact_model(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);raw=self.fixture(root)
            (root/'input.json').write_bytes(raw+b' ')
            with self.assertRaisesRegex(ValueError,'reviewed bytes'):
                capture(root/'input.json',root/'review.json','test','gemma','http://processor:8090',root/'out')
            self.assertFalse((root/'out').exists())


if __name__=='__main__': unittest.main()
