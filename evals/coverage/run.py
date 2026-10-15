"""Explicit six-block local comparison. No tuning, source generation, or volume deletion."""
import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time
from deployment.client import Client
from evals.run import Sampler, write
from .score import Scorer
from .freeze import BLOCKS, HERE, ROOT, digest, public_inputs, verify, validate

PROJECT='vectornext-t14'
COMPOSE=['docker','compose','-f','compose.app.yaml','-f','compose.coverage.yaml','-p',PROJECT]


class LocalSampler(Sampler):
    def container(self,service):
        code="import json,pathlib; p=pathlib.Path('/sys/fs/cgroup'); print(json.dumps({k:(p/k).read_text().strip() for k in ['memory.current','memory.peak','memory.stat']}))"
        r=subprocess.run(['docker','exec',PROJECT+'-'+service+'-1','python','-c',code],capture_output=True,text=True,timeout=10)
        if r.returncode: return {'error':r.stderr[-300:]}
        v=json.loads(r.stdout);stats=dict(line.split() for line in v['memory.stat'].splitlines())
        return {'current_bytes':int(v['memory.current']),'lifetime_peak_bytes':int(v['memory.peak']),
            'anonymous_bytes':int(stats['anon']),'file_bytes':int(stats['file'])}


def options(primary, strategy):
    if primary not in (2,5): raise ValueError('invalid T14 primary limit')
    return {'candidates':30,'rerank_limit':20,'primary_limit':primary,'rerank':True,'evidence_strategy':strategy}


def evidence_ids(case):
    return set(e for s in case['expected'].get('support_sets',[]) for e in s) | set(
        e for a in case['expected'].get('alternatives',[]) for e in a['support_set'])


class Run:
    def __init__(self,name):
        if not name.replace('-','').isalnum(): raise ValueError('simple alphanumeric run name required')
        self.freeze=verify();validate();self.name=name
        self.dataset=json.loads((HERE/'dataset.json').read_text(encoding='utf-8'))
        self.requests=json.loads((HERE/'requests.json').read_text(encoding='utf-8'))
        self.cases=public_inputs(self.dataset,self.requests)
        self.root=ROOT/'data/t14'/name;self.root.mkdir(parents=True,exist_ok=True)
        self.env=os.environ | {'T14_DATABASE':'/storage/'+name,'T14_CACHE':'/cache/'+name+'/ingest'}
        self.client=Client('http://127.0.0.1:8094')

    def compose(self,*args):
        r=subprocess.run(COMPOSE+list(args),cwd=ROOT,env=self.env,capture_output=True,text=True,encoding='utf-8')
        if r.returncode: raise RuntimeError(r.stderr[-3000:])
        return r.stdout

    def call(self,path,body=None,expected=200):
        code,value=self.client.request(path,body)
        if code!=expected: raise RuntimeError((path,code,value))
        return value

    def ready(self):
        end=time.monotonic()+420
        while time.monotonic()<end:
            try:
                code,value=self.client.request('/readyz',timeout=5)
                if code==200: return value
            except OSError: pass
            time.sleep(1)
        raise TimeoutError('readiness exceeded 420 seconds')

    def snapshot(self):
        return {d['document_id']:self.call('/v1/document',{'document_id':d['document_id']})['document']
            for d in self.call('/v1/documents')['documents']}

    def metadata(self):
        ids=self.compose('ps','-q').split()
        containers=json.loads(subprocess.check_output(['docker','inspect',*ids],text=True))
        return {'utc':datetime.now(timezone.utc).isoformat(),'freeze_sha256':digest(HERE/'execution-freeze.json'),
            'database':self.env['T14_DATABASE'],'cache':self.env['T14_CACHE'],
            'images':{c['Config']['Labels']['com.docker.compose.service']:c['Image'] for c in containers},
            'model_locks':{p:digest(ROOT/p) for p in ['experiments/t02/models.lock.json','experiments/t02/models.26b.lock.json','processor/models.lock.json']},
            'running_image_scope':'T14 API and processor implement opt-in coverage; pinned T10 generator unchanged. Identical images required across all three strategies.',
            'cases':list(self.cases),'holdout_run':False}

    def ingest(self):
        target=self.root/'ingestion'
        target.mkdir(exist_ok=False)
        started=time.perf_counter_ns();rows=[]
        with LocalSampler() as sampler:
            self.compose('up','-d','--no-build','llm','processor','vectornext');ready=self.ready()
            startup=(time.perf_counter_ns()-started)/1e9
            if self.call('/v1/documents')['documents'] or self.call('/v1/jobs')['jobs']:
                raise ValueError('ingestion requires an unused database path; choose a fresh run name')
            write(target/'metadata.json',self.metadata())
            before=self.call('/v1/metrics')
            for doc in self.dataset['documents']:
                begin=time.perf_counter_ns();path=HERE/doc['path'];job_id=doc['id']+'-v1'
                try:
                    self.call('/v1/ingest',{'job_id':job_id,'document_id':doc['id'],
                        'media_type':{'text/plain':'Txt','application/pdf':'Pdf','application/json':'Json'}[doc['media_type']],
                        'policy':'structural','record_pointer':'/features' if doc['media_type']=='application/json' else '',
                        'source_base64':base64.b64encode(path.read_bytes()).decode()},expected=202)
                    _,job=self.client.wait(job_id,seconds=1200)
                    row={'document':doc['id'],'committed':job.get('stage')=='Committed','job':job}
                except Exception as error:
                    row={'document':doc['id'],'committed':False,'error':str(error)}
                row.update(seconds=(time.perf_counter_ns()-begin)/1e9,source_bytes=path.stat().st_size)
                rows.append(row);write(target/'progress.json',rows)
                print('ingest',doc['id'],row['committed'],round(row['seconds'],3),flush=True)
            docs=self.snapshot();write(self.root/'documents.json',docs);after=self.call('/v1/metrics')
        write(target/'complete.json',{'startup_seconds':startup,'readiness':ready,'rows':rows,
            'wall_seconds':(time.perf_counter_ns()-started)/1e9,'before':before,'after':after,'samples':sampler.samples,
            'chunks':sum(len(d['chunks']) for d in docs.values())})
        print('ingestion complete',len(docs),'/',len(self.dataset['documents']),flush=True)

    def queries(self):
        if not (self.root/'ingestion/complete.json').exists(): raise ValueError('complete ingestion capture required')
        # Refuse to overwrite or silently resume a partial block.
        if any((self.root/n).exists() for n,_,_ in BLOCKS): raise ValueError('comparison capture exists; preserve it')
        frozen_docs=json.loads((self.root/'documents.json').read_text(encoding='utf-8'))
        for block,strategy,primary in BLOCKS:
            verify();target=self.root/block;target.mkdir()
            self.env['T14_CACHE']='/cache/'+self.name+'/'+block.split('-')[0]
            started=time.perf_counter_ns();rows=[]
            with LocalSampler() as sampler:
                self.compose('up','-d','--no-build','--force-recreate','vectornext','processor');self.ready()
                startup=(time.perf_counter_ns()-started)/1e9
                docs=self.snapshot()
                if docs!=frozen_docs: raise ValueError('corpus changed between blocks')
                metadata=self.metadata()|{'options':options(primary,strategy)}
                initial=json.loads((self.root/'ingestion/metadata.json').read_text(encoding='utf-8'))
                if metadata['images']!=initial['images']: raise ValueError('runtime images changed between ingestion and comparison')
                write(target/'metadata.json',metadata)
                scorer=Scorer(self.dataset,docs)
                available=[e['id'] for e in self.dataset['evidence'] if e['document_id'] in docs]
                fidelity=scorer.parse_fidelity(available)
                for e in self.dataset['evidence']:
                    if e['id'] not in fidelity: fidelity[e['id']]={'unavailable_document':True}
                write(target/'parse-fidelity.json',fidelity)
                refs={e['id']:e['document_id'] for e in self.dataset['evidence']}
                for id,case in self.cases.items():
                    before=self.call('/v1/metrics');begin=time.perf_counter_ns()
                    try:
                        code,report=self.client.request('/v1/ask',{'request':self.requests[id],'options':options(primary,strategy)})
                        raw=self.client.raw;error=None
                    except Exception as exc:
                        code=0;report=None;raw=b'';error=str(exc)
                    wall=(time.perf_counter_ns()-begin)/1e9
                    filename=id+'.json'
                    if raw: (target/filename).write_bytes(raw)
                    missing=sorted({refs[e] for e in evidence_ids(case)}-docs.keys())
                    score=None;scoring_error=None
                    if code==200:
                        try: score=scorer.case(case,report)
                        except Exception as exc: scoring_error=str(exc)
                    row={'case':id,'http_status':code,'wall_seconds':wall,'report_file':filename if raw else None,
                        'report_sha256':digest(target/filename) if raw else None,
                        'before':before,'after':self.call('/v1/metrics'),'score':score,
                        'unavailable_source_documents':missing,'scoring_error':scoring_error,
                        'error':error or (report if code!=200 else None)}
                    rows.append(row);write(target/'progress.json',rows)
                    print(block,id,code,round(wall,3),score['answer_correct'] if score else error or report,flush=True)
            write(target/'complete.json',{'startup_seconds':startup,'cases':rows,'samples':sampler.samples})
        verify();print('all six blocks complete',flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True)
    p.add_argument('--phase',choices=['ingest','queries','all'],default='all');a=p.parse_args()
    run=Run(a.run)
    if a.phase in ('ingest','all'): run.ingest()
    if a.phase in ('queries','all'): run.queries()


if __name__=='__main__': main()

