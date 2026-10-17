import json
from pathlib import Path
import tempfile
import unittest
from .run_benchmark import run,request_id,schedule
from .review import sha


class RunnerTests(unittest.TestCase):
    def fixture(self,root):
        cases=[{'case_id':'first','family':'family','split':'development','document':'doc.txt','question':'Synthetic count?'}]
        requests=json.dumps(cases).encode();(root/'requests.json').write_bytes(requests)
        (root/'protocol.md').write_bytes(b'synthetic test protocol')
        files={p:sha((root/p).read_bytes()) for p in ('requests.json','protocol.md')}
        manifest=json.dumps({'files':files}).encode();(root/'manifest.json').write_bytes(manifest)
        acceptance=json.dumps({'status':'independent_review_accepted','manifest_sha256':sha(manifest)}).encode()
        (root/'acceptance.json').write_bytes(acceptance)
        repo=Path(__file__).resolve().parents[2]
        freeze={'version':1,'model':'nuextract','split':'development','package_manifest':'manifest.json',
            'review_acceptance':'acceptance.json','review_acceptance_sha256':sha(acceptance),
            'files':files,'protocol':'protocol.md','requests':'requests.json',
            'code_files':{'evals/measurement/run_benchmark.py':sha((repo/'evals/measurement/run_benchmark.py').read_bytes())},
            'warmup_capture_sha256':'synthetic','arms':['five','two','facet'],
            'bindings':{'doc.txt':{'state':'committed','document_id':'d','revision':'r'}}}
        (root/'freeze.json').write_text(json.dumps(freeze),encoding='utf-8')
        return freeze,cases

    def test_submission_timeout_reconciles_and_completion_resume_never_posts(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);freeze,cases=self.fixture(root); posts=[]
            def transport(path,body=None):
                if path.endswith('library'):
                    return 200,b'{"documents":[{"document_id":"d","revision":"r","processing":false}]}'
                if body:
                    posts.append(json.loads(body));raise TimeoutError('uncertain delivery')
                return 200,json.dumps({'terminal':True,'total_ms':100,'request_id':path.rsplit('/',1)[-1],
                    'mode':'nuextract','result':{'outcome':'insufficient_evidence'}}).encode()
            result=run(root,root/'freeze.json','http://unused',root/'out',transport=transport,check_runtime=False)
            self.assertEqual(result['planned_requests'],3)
            self.assertEqual(len(posts),3)
            run(root,root/'freeze.json','http://unused',root/'out',transport=transport,check_runtime=False)
            self.assertEqual(len(posts),3)
            for p in posts:
                self.assertEqual(p['mode'],'nuextract');self.assertNotIn('fields',p['payload'])

    def test_started_uncertain_not_found_stops_without_resending(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);freeze,cases=self.fixture(root);posts=[]
            def transport(path,body=None):
                if path.endswith('library'):
                    return 200,b'{"documents":[{"document_id":"d","revision":"r","processing":false}]}'
                if body: posts.append(body);raise OSError('connection lost')
                return 404,b'{}'
            for _ in range(2):
                with self.assertRaisesRegex(RuntimeError,'uncertain'):
                    run(root,root/'freeze.json','http://unused',root/'out',transport=transport,check_runtime=False)
            self.assertEqual(len(posts),1)

    def test_ingestion_failures_count_for_every_arm_without_queries(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);freeze,cases=self.fixture(root)
            freeze['bindings']['doc.txt']={'state':'failed','error':'synthetic'}
            (root/'freeze.json').write_text(json.dumps(freeze),encoding='utf-8')
            def transport(path,body=None):
                self.assertIsNone(body);self.assertTrue(path.endswith('library'))
                return 200,b'{"documents":[]}'
            run(root,root/'freeze.json','http://unused',root/'out',transport=transport,check_runtime=False)
            records=[json.loads(p.read_text()) for p in (root/'out').glob('*/finished.json')]
            self.assertEqual(len(records),3)
            self.assertTrue(all(r['state']=='ingestion_failed' for r in records))

    def test_family_rotation_stable_and_ids_bound_to_freeze(self):
        cases=[{'case_id':'a','family':'same'},{'case_id':'b','family':'same'}]
        arms=[arm for _,arm in schedule(cases,['five','two','facet'])]
        self.assertEqual(arms[:3],arms[3:])
        self.assertNotEqual(request_id('a','case','five'),request_id('b','case','five'))
