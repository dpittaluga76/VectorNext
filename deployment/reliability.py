"""Explicit T13 CPU operational drill; keeps all captures and dedicated volumes.

Start with compose.app.yaml + compose.reliability.yaml, project vectornext-t13.
Requires a fresh database and existing local model assets. No GPU or gold labels.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import time
from .client import Client
from .workflow import capture, document_summary, render_many

ROOT=Path(__file__).resolve().parents[1]
COMPOSE=['docker','compose','-f','compose.app.yaml','-f','compose.reliability.yaml','-p','vectornext-t13']


class Drill:
    def __init__(self,run):
        if not run or Path(run).name!=run or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in run):
            raise ValueError('run must be a simple lowercase directory name')
        self.out=ROOT/'data/t13'/run
        self.out.mkdir(parents=True,exist_ok=False)
        self.client=Client('http://127.0.0.1:8093');self.entries=[];self.events=[]

    def save(self,name,value):
        (self.out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    def compose(self,*args):
        result=subprocess.run(COMPOSE+list(args),cwd=ROOT,capture_output=True,text=True,encoding='utf-8',check=True)
        self.events.append({'compose':list(args),'stdout':result.stdout,'stderr':result.stderr})
        return result.stdout

    def call(self,path,body=None,expected=200,name=None):
        status,value=self.client.request(path,body)
        if name:(self.out/(name+'.json')).write_bytes(self.client.raw)
        assert status==expected,(path,status,value)
        return value

    def ready(self):
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            try:
                _,value=self.client.request('/readyz',timeout=5)
                caps=value['processor']['capabilities']
                if value['storage']['coordinator']['state']=='running' and all(caps.get(k) for k in ('embedding','reranking','pdf')):
                    assert caps['generation'] is False,'drill must not start a GPU model'
                    return value
            except (OSError,KeyError):pass
            time.sleep(1)
        raise TimeoutError('CPU capabilities did not become ready')

    def payload(self,doc,source,media,partial=False):
        return {'job_id':doc+('-partial' if partial else '-strict'),'document_id':doc,'media_type':media,
            'allow_partial':partial,'source_base64':base64.b64encode(source).decode()}

    def wait(self,payload,failed=False):
        status,job=self.client.wait(payload['job_id'],seconds=600)
        self.save(payload['job_id'],job)
        assert status==200 and bool(job.get('last_failure'))==failed,job
        if not failed: assert job['stage']=='Committed',job
        return job

    def report(self,name,job,source,attempts=None):
        document=None
        if job['stage']=='Committed':
            document=document_summary(self.call('/v1/document',{'document_id':job['document_id']})['document'])
        entry=capture('job',json.dumps(job,ensure_ascii=False),context={'source':source,'media_type':'Pdf' if source.endswith('.pdf') else 'Txt',
            'admission_attempts':attempts or []},document=document,note='Fresh T13 CPU operational drill; no generation model was used.')
        self.save(name+'.capture',entry);self.entries.append(entry)

    def run(self):
        self.save('cpu-ready',self.ready())
        assert self.call('/v1/documents')['generation']==0,'requires a fresh dedicated database'
        assert not self.call('/v1/jobs')['jobs'],'requires no existing jobs'
        voyager=(ROOT/'evals/independent/fixtures/voyager1.txt').read_bytes()
        baseline=self.payload('voyager-t13',voyager,'Txt')
        self.call('/v1/ingest',baseline,202)
        self.wait(baseline)
        self.call('/v1/document',{'document_id':'voyager-t13'},name='baseline-before')
        baseline_hash=hashlib.sha256(self.client.raw).hexdigest()
        print('Baseline Voyager document committed.',flush=True)

        # Actual PDF conversion holds API admission while a second client retries.
        apollo=self.payload('apollo-t13',(ROOT/'evals/independent/fixtures/apollo11_pdf.pdf').read_bytes(),'Pdf')
        busy_client=Client(self.client.url);busy_client.busy_retries=5
        queued=self.payload('queued-t13',b'Queued admission evidence.','Txt')
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending=pool.submit(Client(self.client.url).request,'/v1/ingest',apollo)
            time.sleep(.3)
            status,reply=busy_client.request('/v1/ingest',queued)
            self.save('busy-admission',{'attempts':busy_client.admission_attempts,'final_status':status,'final_response':reply})
            assert busy_client.admission_attempts,'expected real overlapping admission'
            code,reply=pending.result(timeout=220)
            self.save('apollo-upload',reply);assert code==202,reply
        rejected=self.wait(apollo,failed=True)
        assert rejected['pdf_diagnostics']['status']=='partial'
        self.report('apollo-strict',rejected,'apollo11_pdf.pdf')
        if status==503:
            assert self.call('/v1/jobs')['jobs'] and not any(j['job_id']==queued['job_id'] for j in self.call('/v1/jobs')['jobs'])
            self.call('/v1/ingest',queued,202)
        queued_job=self.wait(queued)
        self.report('queued-admission',queued_job,'queued.txt',busy_client.admission_attempts)
        generation=self.call('/v1/documents')['generation']
        assert self.call('/v1/ingest',queued,202)['receipt']==queued_job['receipt']
        assert self.call('/v1/documents')['generation']==generation
        print('Busy admission attempts preserved; strict Apollo PDF rejected with page diagnostics.',flush=True)

        changed=dict(apollo,allow_partial=True)
        self.call('/v1/ingest',changed,400,name='immutable-partial-policy')
        for doc,filename in [('apollo-t13','apollo11_pdf.pdf'),('perseverance-t13','perseverance_pdf.pdf')]:
            source=(ROOT/'evals/independent/fixtures'/filename).read_bytes()
            if doc!='apollo-t13':
                strict=self.payload(doc,source,'Pdf');self.call('/v1/ingest',strict,202)
                job=self.wait(strict,failed=True);self.report(doc+'-strict',job,filename)
            partial=self.payload(doc,source,'Pdf',True)
            self.call('/v1/ingest',partial,202)
            job=self.wait(partial)
            assert job['pdf_diagnostics']['allow_partial'] and job['pdf_diagnostics']['warning_count']>0
            document=self.call('/v1/document',{'document_id':doc})['document']
            assert document['processing']['pdf']['warnings']
            self.report(doc+'-partial',job,filename)
            print(filename+': explicit partial-text ingestion committed with warnings.',flush=True)

        source='\n\n'.join(f'# Section {i}\n\nRecovery evidence number {i}. '+('This text tests interrupted CPU ingestion and durable source preservation. '*8) for i in range(250)).encode()
        pending=self.payload('recovery-t13',source,'Txt')
        self.call('/v1/ingest',pending,202)
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            state=self.call('/healthz')
            if state['active_job']==pending['job_id']:break
            time.sleep(.02)
        else:raise AssertionError('did not observe active ingestion before interruption')
        self.save('before-interruption',state)
        self.compose('kill','-s','SIGKILL','vectornext')
        self.compose('stop','processor')
        self.compose('up','-d','--no-deps','vectornext')
        # The restarted coordinator records a durable unavailable-processor failure.
        deadline=time.monotonic()+40
        while time.monotonic()<deadline:
            try:
                job=self.call('/v1/job',{'job_id':pending['job_id']})
                if job.get('last_failure'):break
            except OSError:pass
            time.sleep(.5)
        else:raise AssertionError('processor outage was not recorded')
        self.save('processor-outage',job)
        assert job['coordinator']['state']=='running'
        self.report('processor-outage',job,'recovery.txt')
        self.compose('up','-d','--no-deps','processor')
        self.ready()
        self.call('/v1/retry',{'job_id':pending['job_id']},202)
        recovered=self.wait(pending)
        self.report('recovered',recovered,'recovery.txt')
        generation=self.call('/v1/documents')['generation']
        assert self.call('/v1/ingest',pending,202)['receipt']==recovered['receipt']
        assert self.call('/v1/documents')['generation']==generation
        after=self.call('/v1/document',{'document_id':'voyager-t13'},name='baseline-after')
        before=json.loads((self.out/'baseline-before.json').read_bytes())
        assert after['document']==before['document'],'committed source changed across recovery'
        self.save('verified',{'completed':True,'project':'vectornext-t13','gpu_generations':0,
            'baseline_response_sha256':baseline_hash,'committed_document_unchanged':True,
            'generation':generation,'recovery_failure_count':recovered['failure_count'],
            'busy_rejections':len(busy_client.admission_attempts),
            'images':{s:self.compose('images','-q',s).strip() for s in ('vectornext','processor')}})
        print('Interrupted ingestion resumed after explicit retry; committed document unchanged and publication idempotent.',flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);args=p.parse_args()
    drill=Drill(args.run)
    try:drill.run()
    finally:
        drill.save('events',drill.events)
        (drill.out/'workflow.md').write_text(render_many(drill.entries),encoding='utf-8')
    print('Report: '+str(drill.out/'workflow.md'),flush=True)


if __name__=='__main__':main()
