"""Explicit T09 smoke/recovery drill; uses a dedicated Compose project and retained data.

Run phases in order with --phase seed|answers|recovery|backup|isolation.
No benchmark labels are read. Never removes volumes or overwrites a backup.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from .client import Client

ROOT = Path(__file__).resolve().parents[1]


class Drill:
    def __init__(self, args):
        self.args = args
        self.out = ROOT / 'data' / 't09' / args.run
        self.out.mkdir(parents=True, exist_ok=True)
        self.client = Client(args.url)
        self.events = []

    def record(self, name, value):
        (self.out / (name+'.json')).write_text(json.dumps(value, indent=2), encoding='utf-8')

    def compose(self, *args, expected=0, env=None, name=None):
        result = subprocess.run(['docker','compose','-f','compose.app.yaml','-p',self.args.project,*args],
            cwd=ROOT, env=os.environ | (env or {}), capture_output=True, text=True, encoding='utf-8')
        if name:
            (self.out/(name+'.stdout')).write_text(result.stdout, encoding='utf-8')
            (self.out/(name+'.stderr')).write_text(result.stderr, encoding='utf-8')
        assert result.returncode == expected, (args, result.returncode, result.stderr[-3000:])
        return result.stdout

    def call(self, path, body=None, status=200, name=None):
        start=time.monotonic()
        code,value=self.client.request(path,body)
        self.events.append({'path':path,'status':code,'seconds':round(time.monotonic()-start,4)})
        if name: (self.out/(name+'.json')).write_bytes(self.client.raw)
        assert code==status,(path,code,value)
        return value

    def ready(self, generation=True):
        until=time.monotonic()+300
        while time.monotonic()<until:
            try:
                code,value=self.client.request('/readyz',timeout=5)
                caps=value['processor']['capabilities']
                if value['storage']['storage_ready'] and all(caps.get(k) for k in ('embedding','reranking','pdf')) and (not generation or code==200):
                    self.record('ready-'+self.args.phase,value); return
            except (OSError,KeyError): pass
            time.sleep(2)
        raise TimeoutError('capabilities did not become ready')

    def upload(self, doc, source, media, policy='structural', pointer=''):
        payload={'job_id':doc+'-v1','document_id':doc,'media_type':media,'policy':policy,
            'record_pointer':pointer,'source_base64':base64.b64encode(source).decode()}
        job=self.call('/v1/ingest',payload,status=202,name=doc+'-uploaded')
        return payload,job

    def wait(self, job, failed=False):
        status,value=self.client.wait(job)
        self.record(job+'-completed' if not failed else job+'-failed',value)
        assert status==200 and bool(value['last_failure'])==failed,value
        if not failed: assert value['stage']=='Committed',value
        return value

    def snapshot(self, name):
        documents=self.call('/v1/documents',name=name+'-documents')
        jobs=self.call('/v1/jobs',name=name+'-jobs')
        for doc in documents['documents']:
            self.call('/v1/document',{'document_id':doc['document_id']},name=name+'-'+doc['document_id'])
        return documents,jobs

    def seed(self):
        self.ready()
        assert self.call('/v1/documents')['generation']==0,'seed requires a fresh dedicated volume'
        for filename,media,pointer in [('fictional_matches.txt','Txt',''),('array_matches.json','Json',''),
            ('nested_matches.json','Json','/matches'),('equipment_guide.pdf','Pdf',''),('scanned_note.pdf','Pdf','')]:
            doc=Path(filename).stem
            source=(ROOT/'evals/fixtures'/filename).read_bytes()
            start=time.monotonic()
            payload,_=self.upload(doc,source,media,pointer=pointer)
            done=self.wait(doc+'-v1')
            again=self.call('/v1/ingest',payload,status=202)
            assert again['receipt']==done['receipt']
            self.events.append({'document':doc,'source_sha256':hashlib.sha256(source).hexdigest(),'seconds':round(time.monotonic()-start,3)})
            print('committed',doc,flush=True)
        assert self.call('/v1/documents')['generation']==5
        self.snapshot('seed')

    def answers(self):
        self.ready()
        for mode in ('keyword','hybrid'):
            result=self.call('/v1/search',{'text':'Pele Argentina 1954','mode':mode},name=mode)
            assert result['hits'] and result['hits'][0]['key']['document_id']=='fictional_matches'
        request=json.loads((ROOT/'tests/fixtures/answers/pele.json').read_text())
        answer=self.call('/v1/ask',{'request':request},name='pele-answer')
        assert answer['answer']['status']=='supported',answer
        assert {k:v['value'] for k,v in answer['answer']['fields'].items()}=={'year':1954,'goals':3,'opponent':'Argentina'}
        request={'question':'What is the required torque for J2?', 'filter':{'DocumentIds':['scanned_note']},'fields':{'torque':{'kind':'integer'},'unit':{'kind':'string'}}}
        answer=self.call('/v1/ask',{'request':request},name='scan-answer')
        assert answer['answer']['status']=='supported' and answer['answer']['fields']['torque']['value']==6,answer
        print('actual GPU TXT and scanned PDF answers verified',flush=True)

    def recovery(self):
        self.compose('stop','llm',name='stop-llm')
        self.call('/readyz',status=503,name='generation-offline')
        self.call('/v1/search',{'text':'Pele','mode':'keyword'},name='offline-keyword')
        request={'question':'Read the original goals and assists for m-001.','scope':'structured_lookup',
            'filter':{'All':[{'DocumentIds':['nested_matches']},{'Attribute':{'key':'record','pointer':'/id','predicate':{'Eq':'m-001'},'trust':'SourceOrDeterministic'}}]},
            'fields':{'goals':{'kind':'integer','pointer':'/stats/goals'},'assists':{'kind':'integer','nullable':True,'pointer':'/stats/assists'}}}
        answer=self.call('/v1/ask',{'request':request},name='offline-lookup')
        assert answer['answer']['fields']['goals']['value']==0 and answer['answer']['fields']['assists']['value'] is None
        request=json.loads((ROOT/'tests/fixtures/answers/pele.json').read_text())
        self.call('/v1/ask',{'request':request},status=503,name='offline-answer-error')
        source=b'# Restart drill\n\nThe fictional Aurora team played Riverton in 2024.\n\nIn that match, they scored four goals.\n'
        payload,_=self.upload('recovery',source,'Txt','generated')
        failed=self.wait('recovery-v1',failed=True)
        assert failed['stage']=='Chunked'
        before=self.snapshot('before-recreate')
        self.compose('up','-d','--force-recreate','processor','vectornext',name='recreate')
        self.ready(generation=False)
        assert self.snapshot('after-recreate')==before
        self.compose('up','-d','llm',name='restart-llm')
        self.ready()
        self.call('/v1/retry',{'job_id':'recovery-v1'},status=202)
        until=time.monotonic()+30
        while time.monotonic()<until:
            health=self.call('/healthz')
            if health['active_job']=='recovery-v1': break
            time.sleep(.05)
        else: raise AssertionError('background work was not observed')
        reads=[]
        for _ in range(10):
            start=time.monotonic()
            result=self.call('/v1/search',{'text':'Pele','mode':'keyword'})
            assert result['generation']==5
            reads.append(time.monotonic()-start)
        self.record('concurrent-keyword-seconds',reads)
        self.compose('stop','-t','1','vectornext','processor',name='interrupt-stage')
        self.compose('up','-d','processor',name='restart-processor')
        # Admission must finish warming before the automatic stage resumes.
        until=time.monotonic()+90
        while time.monotonic()<until:
            raw=self.compose('exec','-T','processor','python','-c',
                "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8090/health').read().decode())")
            caps=json.loads(raw)['capabilities']
            if all(caps.get(k) for k in ('embedding','reranking','pdf')): break
            time.sleep(2)
        self.compose('up','-d','vectornext',name='restart-owner')
        self.ready()
        done=self.wait('recovery-v1')
        assert done['failure_count']==1 and done['receipt']['generation']==6,done
        assert self.call('/v1/ingest',payload,status=202)['receipt']==done['receipt']
        self.snapshot('recovered')
        print('outage, recreation, concurrent reads and interrupted-stage recovery verified',flush=True)

    def backup(self):
        target='/backups/'+self.args.run
        self.compose('run','--rm','admin','export','/storage/db',target,expected=1,name='live-export-rejected')
        self.compose('stop','vectornext',name='backup-stop')
        before=self.compose('run','--rm','admin','inspect','/storage/db',name='original-inspect')
        manifest=self.compose('run','--rm','admin','export','/storage/db',target,name='export')
        restored=self.compose('run','--rm','admin','restore',target,'/storage/restored',name='restore')
        assert json.loads(manifest)==json.loads(restored)
        after=self.compose('run','--rm','admin','inspect','/storage/restored',name='restored-inspect')
        assert before==after,'restored documents/jobs/receipts must be byte-identical'
        self.compose('run','--rm','admin','restore',target,'/storage/restored',expected=1,name='overwrite-rejected')
        self.compose('up','-d','vectornext',env={'VECTORNEXT_DATA':'/storage/restored'},name='start-restored')
        self.ready()
        self.call('/v1/search',{'text':'Pele','mode':'keyword'},name='restored-search')
        old=self.call('/v1/job',{'job_id':'recovery-v1'})
        assert self.call('/v1/retry',{'job_id':'recovery-v1'},status=202)['receipt']==old['receipt']
        assert self.call('/v1/documents')['generation']==6
        self.upload('after-restore',b'[{"id":"exact","number":9007199254740993.00000000000001,"zero":0,"unknown":null}]','Json')
        self.wait('after-restore-v1')
        assert self.call('/v1/documents')['generation']==7
        self.snapshot('restored-final')
        exact=self.compose('run','--rm','client','document','after-restore',name='exact-client-output')
        assert '9007199254740993.00000000000001' in exact
        print('offline export, exact restore, no overwrite and new writes verified',flush=True)

    def isolation(self):
        ids=self.compose('ps','-q').split()
        value=json.loads(subprocess.check_output(['docker','inspect',*ids],text=True))
        for container in value:
            service=container['Config']['Labels']['com.docker.compose.service']
            assert bool(container['HostConfig']['DeviceRequests'])==(service=='llm')
            if service!='vectornext':
                assert not container['HostConfig']['PortBindings']
                assert all(m['Destination']!='/storage' for m in container['Mounts'])
        self.record('containers',value)
        self.call('/v1/ingest',{'job_id':'invalid','document_id':'invalid','media_type':'Txt','source_base64':'!'},status=400,name='invalid-upload')
        self.compose('stop','processor','llm',name='stop-model-services')
        self.call('/readyz',status=503,name='all-models-offline')
        self.call('/v1/search',{'text':'Pele','mode':'keyword'},name='all-offline-keyword')
        self.call('/v1/search',{'text':'Pele','mode':'hybrid'},status=503,name='all-offline-hybrid-error')
        request={'question':'Read the exact number.','scope':'structured_lookup','filter':{'DocumentIds':['after-restore']},
            'fields':{'number':{'kind':'number','pointer':'/number'}}}
        answer=self.call('/v1/ask',{'request':request},name='all-offline-exact-number')
        assert answer['answer']['status']=='supported' and b'9007199254740993.00000000000001' in self.client.raw
        assert self.call('/v1/documents')['generation']==7
        print('GPU/mount isolation, full model outage and exact source reads verified',flush=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--phase',choices=['seed','answers','recovery','backup','isolation'],required=True)
    p.add_argument('--project',default='vectornext-t09'); p.add_argument('--run',default='20261014-t09')
    p.add_argument('--url',default='http://127.0.0.1:8088')
    a=p.parse_args()
    if not a.project.startswith('vectornext-t09'): p.error('use a dedicated vectornext-t09 project')
    if not a.run.replace('-','').isalnum(): p.error('run must use letters, digits and hyphens')
    drill=Drill(a)
    try: getattr(drill,a.phase)()
    finally: drill.record(a.phase+'-events',drill.events)


if __name__=='__main__': main()
