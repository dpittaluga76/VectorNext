"""T13 operational behavior without models or network."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from .client import Client, main
from .workflow import capture, render

BUSY=(503,{'error':{'code':'busy','message':'CPU admission busy'}})


class ReliabilityTests(unittest.TestCase):
    def test_cli_keeps_raw_success_and_saves_rejected_admission_attempts(self):
        raw=b'{"stage":"Uploaded","precise":9007199254740993.00000000000001}'
        calls=[]
        def request(client,path,body,timeout):
            calls.append(body)
            status,value=BUSY if len(calls)==1 else (202,json.loads(raw))
            client.raw=json.dumps(value).encode() if status==503 else raw
            return status,value
        class Output:
            buffer=io.BytesIO()
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'source.txt';source.write_text('Source evidence.')
            capture_path=Path(temp)/'capture.json';output=Output()
            args=['client','ingest',str(source),'--document','fixed','--job','fixed-v1','--capture',str(capture_path)]
            with patch('sys.argv',args),patch('sys.stdout',output),patch.object(Client,'request_once',request),patch('time.sleep'),contextlib.redirect_stderr(io.StringIO()):
                main()
            saved=json.loads(capture_path.read_text())
            self.assertEqual(saved['response_json'],raw.decode())
            self.assertEqual(output.buffer.getvalue(),raw+b'\n')
            self.assertEqual(len(saved['context']['admission_attempts']),1)
            self.assertEqual(calls[0],calls[1])

    def test_busy_retry_reuses_body_and_preserves_every_rejected_attempt(self):
        client=Client();client.busy_retries=3
        body={'job_id':'fixed','source_base64':'eA=='}
        with patch.object(client,'request_once',side_effect=[BUSY,BUSY,(202,{'job_id':'fixed'})]) as request,patch('time.sleep') as sleep,contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(client.request('/v1/ingest',body)[0],202)
        self.assertEqual([call.args for call in request.call_args_list],[('/v1/ingest',body,900)]*3)
        self.assertEqual([call.args for call in sleep.call_args_list],[(1,),(2,)])
        self.assertEqual(len(client.admission_attempts),2)
        self.assertEqual(stderr.getvalue().count('Admission rejected:'),2)
        report=render(capture('ingest','{"stage":"Uploaded"}',context={'admission_attempts':client.admission_attempts}))
        self.assertIn('Admission attempt 2',report)

    def test_busy_retry_budget_exhausts_without_unbounded_wait(self):
        client=Client();client.busy_retries=2
        with patch.object(client,'request_once',return_value=BUSY) as request,patch('time.sleep'),contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(client.request('/v1/retry',{'job_id':'fixed'}),BUSY)
        self.assertEqual(request.call_count,3)
        self.assertEqual(len(client.admission_attempts),3)
        self.assertIsNone(client.admission_attempts[-1]['retry_in_seconds'])

    def test_transport_unknown_capability_and_validation_failures_are_not_retried(self):
        for response in [(503,{'error':{'code':'capability_unavailable'}}),(400,{'error':{'code':'invalid_request'}})]:
            client=Client();client.busy_retries=3
            with patch.object(client,'request_once',return_value=response) as request:
                self.assertEqual(client.request('/v1/ingest',{}),response)
            self.assertEqual(request.call_count,1)
        with patch.object(client,'request_once',side_effect=TimeoutError('unknown outcome')) as request,self.assertRaises(TimeoutError):
            client.request('/v1/ingest',{})
        self.assertEqual(request.call_count,1)

    def test_wait_stops_when_coordinator_failed_without_claiming_job_failure(self):
        client=Client()
        job={'stage':'Parsed','last_failure':None,'coordinator':{'state':'failed','last_error':'panic','recovery':'Restart the API.'}}
        with patch.object(client,'request',return_value=(200,job)) as request:
            self.assertEqual(client.wait('fixed'),(200,job))
        self.assertEqual(request.call_count,1)
        report=render(capture('wait',json.dumps(job)))
        self.assertIn('Ingestion coordinator — failed',report)
        self.assertIn('Restart the API',report)
        self.assertIn('Create chunks — not reached',report)

    def test_pdf_diagnostics_visible_for_rejected_unpublished_job(self):
        job={'stage':'Uploaded','last_failure':{'message':'partial PDF rejected'},'pdf_diagnostics':{
            'status':'partial','allow_partial':False,'pages':[{'page':1}],'warning_count':1,
            'warnings':[{'page':1,'code':'uninterpreted_picture','message':'Illustration not interpreted'}],
            'next_action':'Submit a new job ID with --allow-partial after review.'}}
        report=render(capture('job',json.dumps(job),context={'media_type':'Pdf'}))
        self.assertIn('PDF diagnostics before publication',report)
        self.assertIn('Illustration not interpreted',report)
        self.assertIn('Publish document — not reached',report)

    def test_rejected_answer_report_keeps_unvalidated_draft_separate(self):
        raw='{"error":{"code":"answer_rejected","message":"missing pointer","diagnostics":{"stage":"resolve_json_values","question":"Value?","unvalidated_draft":{"fields":{"value":{"value":9007199254740993.00000000000001,"pointer":"/missing","evidence_id":"E1"}}},"evidence":[],"next_action":"Review pointers."}}}'
        report=render(capture('ask',raw,status=400))
        self.assertIn('9007199254740993.00000000000001',report)
        self.assertIn('not a supported answer',report)
        self.assertIn('/missing',report)
        self.assertNotIn('**Outcome: Supported answer',report)
        self.assertNotIn('Format answer — completed',report)


if __name__=='__main__':unittest.main()
