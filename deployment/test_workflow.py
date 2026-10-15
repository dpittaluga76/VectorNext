"""Workflow truthfulness and exact-output regressions; no models or network."""
import copy
import io
import json
import shlex
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import client, workflow


def job(stage='Committed', **kw):
    return {'document_id':'mission','revision':'r1','stage':stage,'last_failure':None, **kw}


def ask(status='supported'):
    return {'request':{'question':'What is recorded?','history':[],'prose':False},
        'answer':{'status':status,'fields':{}},'evidence':[], 'ranked':[],
        'audit':{'assessment':{'status':status},'assessment_audit':{'model':{'model':'local-model'}}},
        'validation':{}, 'formatted':None}


def render(operation, value, **kw):
    return workflow.render(workflow.capture(operation,json.dumps(value),**kw))


class WorkflowTests(unittest.TestCase):
    def test_coverage_selection_explains_recorded_calls_without_claiming_correctness(self):
        value = ask('supported')
        value['selection'] = {'field_rankings': {'year': {}}, 'planned_primary_keys': ['a', 'b'], 'admitted_primary_keys': ['a']}
        out = render('ask', value)
        self.assertIn('Ranked candidates for 1 fields; planned 2 primary passages and admitted 1', out)
        self.assertIn('answers::coverage::select()', out)
        self.assertIn('not a correctness guarantee', out)

    def test_old_captures_show_handler_without_inventing_command(self):
        entry=workflow.capture('ask',json.dumps(ask()));entry.pop('invocation')
        out=workflow.render(entry)
        self.assertIn('Original client arguments were not recorded',out)
        self.assertIn('POST /v1/ask → Application::ask()',out)
        self.assertNotIn('python -m deployment.client',out)
        self.assertIn('not an instrumented call stack',out)

    def test_invocation_round_trips_special_arguments_inside_markdown_fence(self):
        args=['search','a "quote" and $HOME; $(whoami) `code`\n```\n# text', '--report',r'C:\folder with spaces\report.md']
        out=render('search',{},invocation={'arguments':args,'origin':'recorded'})
        command=out.split('````sh\n',1)[1].split('\n````\n',1)[0]
        self.assertEqual(shlex.split(command),['python','-m','deployment.client',*args])
        self.assertIn('Recorded client arguments',out)

    def test_recovered_invocation_is_distinguished_from_original_capture(self):
        out=render('ingest',job(),invocation={'arguments':['ingest','source.txt'],'origin':'saved_run_record'})
        self.assertIn('recovered from the saved run record',out)
        self.assertIn('report/capture switches omitted',out)
        self.assertNotIn('Recorded client arguments',out)
        with self.assertRaises(ValueError):
            render('ask',ask(),invocation={'arguments':'ask source.json','origin':'recorded'})

    def test_call_references_follow_reached_stages_and_format(self):
        out=render('ingest',job('Parsed',last_failure={'message':'Chunk budget exceeded'}),context={'media_type':'Txt'})
        self.assertIn('`ingestion::prepare::parse()`',out)
        self.assertIn('`ingestion::prepare::chunk()`',out)
        self.assertNotIn('`RemoteModels::embed()`',out)
        self.assertNotIn('`Database::commit_ingestion()`',out)
        out=render('ingest',job(),context={'media_type':'Pdf'})
        self.assertIn('`PdfProcessor::process()`',out)
        self.assertIn('`ingestion::pdf::chunk()`',out)
        self.assertNotIn('`ingestion::prepare::parse()`',out)

    def test_answer_calls_respect_assessment_and_disabled_reranker(self):
        value=ask('ambiguous');value['reranker']={'reranking':'disabled','score':'rrf'}
        out=render('ask',value)
        self.assertIn('Rerank passages — skipped',out)
        self.assertIn('kept the fused search scores',out)
        self.assertNotIn('`RemoteModels::rerank()`',out)
        self.assertIn('`model_worker.answers.generate(..., ASSESS_PROMPT)`',out)
        self.assertNotIn('`model_worker.answers.generate(..., PROMPT)`',out)
        self.assertNotIn('`answers::render()`',out)
        value['audit']={'operation':'no_evidence'}
        self.assertNotIn('`RemoteModels::extract()`',render('ask',value))

    def test_recorded_partial_job_does_not_claim_storage_or_embeddings(self):
        value=job('Parsed',last_failure={'stage':'Parsed','message':'Chunk budget exceeded'})
        out=render('ingest',value,context={'media_type':'Txt'})
        self.assertIn('Create chunks — failed',out)
        self.assertIn('Create embeddings — not reached',out)
        self.assertIn('Publish document — not reached',out)
        self.assertIn('Per-stage timing and cache reuse were not recorded',out)

    def test_superseded_document_cannot_supply_counts_or_model(self):
        out=render('ingest',job(),document={'document_id':'mission','revision':'r2','blocks':99,'chunks':88,'embedding_model':'wrong'})
        self.assertNotIn('99 blocks',out);self.assertNotIn('wrong',out)
        self.assertIn('counts were not recorded',out)

    def test_format_specific_pdf_and_json_steps(self):
        base={'document_id':'mission','revision':'r1','blocks':4,'chunks':3,'records':2,'policy':'structural'}
        out=render('ingest',job(),document=base|{'media_type':'Pdf','pdf_status':'partial','pdf_pages':2,'pdf_methods':{'Native':3,'Ocr':1},'warnings':[{'message':'Figure not interpreted'}]})
        self.assertIn('2 pages',out);self.assertIn('OCR/layout',out);self.assertIn('Figure not interpreted',out)
        out=render('ingest',job(),document=base|{'media_type':'Json'})
        self.assertIn('JSON record blocks: 2',out);self.assertIn('Optional generated context — skipped',out)

    def test_ambiguous_and_insufficient_skip_extraction(self):
        for status in ('ambiguous','insufficient_evidence'):
            out=render('ask',ask(status))
            self.assertIn('Extract fields — skipped',out);self.assertIn('Format answer — skipped',out)
            self.assertIn(workflow.OUTCOMES[status],out)

    def test_no_evidence_does_not_claim_model_call(self):
        value=ask('insufficient_evidence');value['audit']={'operation':'no_evidence'}
        out=render('ask',value)
        self.assertIn('Assess answerability — skipped',out)
        self.assertNotIn('Local generation model:',out)

    def test_error_has_no_invented_pipeline_progress(self):
        for status in (0,400,503):
            out=render('ask',{'error':{'message':'Missing JSON pointer'}},status=status,context={'question':'Depth?'})
            self.assertIn('Request — failed',out);self.assertIn('Missing JSON pointer',out)
            self.assertIn('this does not mean they never ran',out)
            self.assertNotIn('Validate answer — completed',out)

    def test_exact_decimal_large_integer_null_and_zero(self):
        value=ask();value['answer']['fields']={k:{'value':v,'evidence_id':'E1'} for k,v in [('zero',0),('null',None),('large',9007199254740993)]}
        raw=json.dumps(value).replace('"fields": {','"fields": {"precise":{"value":9007199254740993.00000000000001,"evidence_id":"E1"},',1)
        out=workflow.render(workflow.capture('ask',raw))
        for literal in ('9007199254740993.00000000000001','9007199254740993','**null**','**0**'):self.assertIn(literal,out)

    def test_sources_escape_markdown_and_show_locations(self):
        value=ask();value['evidence']=[{'id':'E1','key':{'document_id':'[click](https://bad)'},'text':'<script>bad()</script> ![img](bad)',
            'sources':[{'locator':{'Text':{'line_start':2,'line_end':4}}},{'locator':{'Json':{'pointer':'/features/0'}}},{'locator':{'Pdf':{'page':2,'extraction':'Ocr'}}}]}]
        out=render('ask',value)
        self.assertIn('lines 2–4',out);self.assertIn('page 2',out);self.assertIn('/features/0',out)
        self.assertNotIn('<script>',out);self.assertNotIn('![img]',out)

    def test_semantic_correctness_and_cache_are_not_invented(self):
        value=ask();value['validation']={k:'passed' for k in ['schema','source_references','mechanical_support']}
        out=render('ask',value)
        self.assertIn('Semantic correctness is not automatically established',out)
        self.assertIn('cache hits were not recorded per request',out)

    def test_keyword_search_skips_embeddings_rerank_and_llm(self):
        out=render('search',{'trace':{'request':{'text':'Voyager','vector':None},'corpus_chunks':2,'eligible_chunks':2,'keyword':[],'results':[]},'hits':[]})
        self.assertIn('Semantic search — skipped',out)
        self.assertIn('Rerank and answer — skipped',out)

    def test_structured_lookup_and_source_null_abstention(self):
        value=ask('insufficient_evidence');value['request']['scope']='structured_lookup'
        value['audit']={'operation':'complete_filtered_record_scan_v1','eligible_records':1,'source_null_abstention':{'reason':'null'}}
        out=render('ask',value)
        self.assertIn('Structured lookup — completed',out)
        self.assertIn('source contains null',out);self.assertIn('Assess answerability — skipped',out)

    def test_renderer_does_not_mutate_capture(self):
        entry=workflow.capture('ask',json.dumps(ask()));before=copy.deepcopy(entry)
        workflow.render(entry);self.assertEqual(entry,before)

    def test_string_null_stays_distinct_from_source_null(self):
        value=ask();value['answer']['fields']={'text':{'value':'null','evidence_id':'E1'},'raw':{'value':None,'evidence_id':'E1'}}
        out=render('ask',value)
        self.assertIn('**null** (string)',out);self.assertIn('**null** (null)',out)

    def test_supported_proofs_show_exact_quotes_instead_of_full_context(self):
        value=ask();value['answer']['fields']={'year':{'value':1977,'evidence_id':'E1','quote':'Launched in 1977'}}
        value['evidence']=[{'id':'E1','key':{'document_id':'Voyager'},'text':'Launched in 1977. '+('Unrelated text '*1000),'sources':[]}]
        value['audit']['model']={'model':'local-model'};value['formatted']='Launch: 1977'
        out=render('ask',value)
        self.assertIn('> Launched in 1977',out);self.assertNotIn('Unrelated text',out)
        self.assertIn('Extract fields — completed',out);self.assertIn('Launch: 1977',out)


class FakeStdout:
    def __init__(self):self.buffer=io.BytesIO()


class ClientTests(unittest.TestCase):
    def run_cli(self,args,request=None,execute=None):
        out=FakeStdout()
        with patch('sys.argv',['client',*args]),patch('sys.stdout',out),patch.object(client.Client,'request',request or self.no_network):
            if execute:
                with patch.object(client,'execute',execute): client.main()
            else:client.main()
        return out.buffer.getvalue()

    def no_network(self,*args,**kw):raise AssertionError('Unexpected API call')

    def test_default_stdout_is_exact_server_bytes(self):
        raw=b'{"value":9007199254740993.00000000000001}'
        def request(c,*args):c.raw=raw;return 200,json.loads(raw)
        self.assertEqual(self.run_cli(['documents'],request),raw+b'\n')

    def test_readable_save_keeps_json_and_matching_document(self):
        raw=json.dumps(job()).encode()
        def request(c,path,body):
            if path=='/v1/job':c.raw=raw;return 200,json.loads(raw)
            c.raw=b'{"document":{}}'
            return 200,{'document':{'document_id':'mission','revision':'r1','media_type':'Txt','blocks':[],'chunks':[]}}
        with tempfile.TemporaryDirectory() as temp:
            report=Path(temp)/'report.md';capture=Path(temp)/'capture.json'
            out=self.run_cli(['job','id','--report',str(report),'--capture',str(capture)],request)
            self.assertEqual(out,raw+b'\n')
            self.assertEqual(json.loads(capture.read_text())['response_json'],raw.decode())
            self.assertIn('Stored and searchable',report.read_text(encoding='utf-8'))
            saved=json.loads(capture.read_text())
            self.assertEqual(saved['invocation'],{'arguments':['job','id','--report',str(report),'--capture',str(capture)],'origin':'recorded'})
            self.assertEqual(self.run_cli(['explain',str(capture)]),report.read_bytes())

    def test_offline_explain_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'capture.json';path.write_text(json.dumps(workflow.capture('ask',json.dumps(ask()))))
            out=self.run_cli(['explain',str(path)])
            self.assertIn(b'VectorNext workflow',out)
            with patch('sys.stderr',io.StringIO()),self.assertRaises(SystemExit):
                self.run_cli(['ask','unused','--report',str(path)])

    def test_transport_error_writes_report_and_exits_failure(self):
        def fail(*args):raise TimeoutError('Connection timed out')
        with tempfile.TemporaryDirectory() as temp:
            report=Path(temp)/'error.md'
            with self.assertRaises(SystemExit) as failure:self.run_cli(['job','id','--report',str(report)],execute=fail)
            self.assertEqual(failure.exception.code,1)
            self.assertIn('Connection timed out',report.read_text(encoding='utf-8'))

    def test_report_and_capture_cannot_share_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            path=str(Path(temp)/'output')
            with patch('sys.stderr',io.StringIO()),self.assertRaises(SystemExit):self.run_cli(['job','id','--report',path,'--capture',path])


    def test_ask_preserves_request_and_response_numeric_literals(self):
        raw=b'{"answer":{"status":"insufficient_evidence","fields":{}},"precise":9007199254740993.00000000000001}'
        class Response(io.BytesIO):status=200
        class Opener:
            def open(self,request,timeout):
                self.seen=request.data
                return Response(raw)
        opener=Opener()
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'ask.json'
            path.write_text('{"question":"Value?","filter":{"value":9007199254740993.00000000000001}}')
            with patch('urllib.request.build_opener',return_value=opener):
                out=self.run_cli(['ask',str(path)])
            self.assertEqual(out,raw+b'\n')
            self.assertIn(b'9007199254740993.00000000000001',opener.seen)
            with patch('urllib.request.build_opener',return_value=opener):
                out=self.run_cli(['ask',str(path),'--evidence-strategy','coverage_v1'])
            self.assertEqual(out,raw+b'\n')
            self.assertIn(b'9007199254740993.00000000000001',opener.seen)
            self.assertEqual(json.loads(opener.seen)['options'],{'evidence_strategy':'coverage_v1'})


if __name__=='__main__':unittest.main()
