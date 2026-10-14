"""Explicit local T10 runner. Only dev requests; isolated data; never deletes volumes."""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import threading
import time
from deployment.client import Client
from .requests import public_request
from .score import Scorer

ROOT=Path(__file__).resolve().parents[1]
COMPOSE=['docker','compose','-f','compose.app.yaml','-f','compose.eval.yaml','-p','vectornext-t10']


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value): path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


class Sampler:
    def __init__(self): self.stop=threading.Event(); self.samples=[]; self.thread=None
    def container(self,service):
        code="import json,pathlib; p=pathlib.Path('/sys/fs/cgroup'); print(json.dumps({k:(p/k).read_text().strip() for k in ['memory.current','memory.peak','memory.stat']}))"
        result=subprocess.run(['docker','exec','vectornext-t10-'+service+'-1','python','-c',code],capture_output=True,text=True,timeout=10)
        if result.returncode: return {'error':result.stderr[-300:]}
        v=json.loads(result.stdout); stats=dict(line.split() for line in v['memory.stat'].splitlines())
        return {'current_bytes':int(v['memory.current']),'lifetime_peak_bytes':int(v['memory.peak']),
            'anonymous_bytes':int(stats['anon']),'file_bytes':int(stats['file'])}
    def loop(self):
        with ThreadPoolExecutor(3) as pool:
            while not self.stop.is_set():
                sample={'monotonic_ns':time.perf_counter_ns()}
                futures={s:pool.submit(self.container,s) for s in ['vectornext','processor','llm']}
                try:
                    raw=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True,timeout=5)
                    sample['gpu_mib'],sample['gpu_utilization_percent']=[int(x.strip()) for x in raw.split(',')]
                except Exception as e: sample['gpu_error']=str(e)
                for s,f in futures.items():
                    try: sample[s]=f.result()
                    except Exception as e: sample[s]={'error':str(e)}
                self.samples.append(sample)
                self.stop.wait(1)
    def __enter__(self):
        self.thread=threading.Thread(target=self.loop,daemon=True); self.thread.start(); return self
    def __exit__(self,*_): self.stop.set(); self.thread.join(15)


class Run:
    def __init__(self,args):
        self.args=args; self.client=Client('http://127.0.0.1:8089')
        self.root=ROOT/'data/t10'/args.run/args.policy/args.variant
        self.root.mkdir(parents=True,exist_ok=True)
        self.dataset=json.loads((ROOT/'evals/dataset.json').read_text(encoding='utf-8'))
        self.cases=[c for c in self.dataset['cases'] if c['split']=='dev']
        if args.case:
            if not set(args.case)<={c['id'] for c in self.cases}: raise ValueError('only registered dev case IDs are allowed')
            self.cases=[c for c in self.cases if c['id'] in args.case]
        self.env=os.environ | {'T10_DATABASE':args.database_root.rstrip('/')+'/'+args.policy,'T10_CACHE':'/cache/'+args.run+'/'+args.policy+'/'+(args.variant if args.phase=='queries' else 'ingest'),
            'T10_GENERATED_WEIGHT':str(args.generated_weight),'T10_STRUCTURAL_WEIGHT':str(args.structural_weight)}
        self.options={'candidates':args.candidates,'rerank_limit':args.rerank_limit,'primary_limit':args.primary_limit,'rerank':not args.no_rerank}
        for doc in self.dataset['documents']:
            if digest(ROOT/'evals'/doc['path'])!=doc['sha256']: raise ValueError('source fixture changed')
    def compose(self,*args):
        result=subprocess.run(COMPOSE+list(args),cwd=ROOT,env=self.env,capture_output=True,text=True,encoding='utf-8')
        if result.returncode: raise RuntimeError(result.stderr[-3000:])
        return result.stdout
    def ready(self):
        until=time.monotonic()+360
        while time.monotonic()<until:
            try:
                code,value=self.client.request('/readyz',timeout=5)
                if code==200: return value
            except OSError: pass
            time.sleep(1)
        raise TimeoutError('services did not become ready')
    def call(self,path,body=None,expected=200):
        code,value=self.client.request(path,body)
        if code!=expected: raise RuntimeError((path,code,value))
        return value
    def metadata(self):
        ids=self.compose('ps','-q').split()
        containers=json.loads(subprocess.check_output(['docker','inspect',*ids],text=True))
        return {'dataset_sha256':digest(ROOT/'evals/dataset.json'),'protocol_sha256':digest(ROOT/'docs/evaluation.md'),
            'policy':self.args.policy,'variant':self.args.variant,'options':self.options,'generated_weight':self.args.generated_weight,'structural_weight':self.args.structural_weight,
            'database':self.env['T10_DATABASE'],'cache':self.env['T10_CACHE'],
            'cases':[c['id'] for c in self.cases],'split':'dev','holdout_run':False,
            'public_requests':{c['id']:public_request(c) for c in self.cases},
            'git_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'git_status':subprocess.check_output(['git','status','--porcelain'],text=True),
            'images':{c['Config']['Labels']['com.docker.compose.service']:c['Image'] for c in containers},
            'model_locks':{p:digest(ROOT/p) for p in ['experiments/t02/models.lock.json','experiments/t02/models.26b.lock.json','processor/models.lock.json'] if (ROOT/p).exists()},
            'source_hash_scope':'working tree at capture; running images may predate pending edits; archive build manifests separately',
            'working_tree_sources':{str(p.relative_to(ROOT)).replace('\\','/'):digest(p) for directory,pattern in [('src','*.rs'),('model_worker','*.py'),('deployment','*.py'),('evals','*.py')] for p in (ROOT/directory).rglob(pattern)},
            'timer':time.get_clock_info('perf_counter')._asdict() if hasattr(time.get_clock_info('perf_counter'),'_asdict') else vars(time.get_clock_info('perf_counter'))}
    def snapshot(self):
        docs=self.call('/v1/documents'); result={}
        for d in docs['documents']: result[d['document_id']]=self.call('/v1/document',{'document_id':d['document_id']})['document']
        write(self.root/'documents.json',result)
        return result
    def wait(self,id):
        until=time.monotonic()+900
        while time.monotonic()<until:
            job=self.call('/v1/job',{'job_id':id})
            if job['last_failure']: raise RuntimeError(job)
            if job['stage']=='Committed': return job
            time.sleep(.1)
        raise TimeoutError('ingestion exceeded runner deadline')
    def startup(self):
        self.compose('stop','llm')
        with Sampler() as sampler:
            time.sleep(2)
            begin=time.perf_counter_ns(); self.compose('up','-d','llm'); status=self.ready()
            result={'startup_seconds':(time.perf_counter_ns()-begin)/1e9,'readiness':status}
        result['samples']=sampler.samples; write(self.root/'startup.json',result)
        print('startup',result['startup_seconds'],flush=True)
    def ingest(self):
        if any((self.root/name).exists() for name in ['ingestion.json','ingestion-progress.json']): raise ValueError('ingestion capture already exists; preserve it and use another isolated database')
        results=[]; begin=time.perf_counter_ns()
        with Sampler() as sampler:
            self.compose('up','-d','--force-recreate','vectornext','processor')
            status=self.ready(); ready=(time.perf_counter_ns()-begin)/1e9
            if self.call('/v1/documents')['documents']: raise ValueError('ingestion requires an empty policy database')
            write(self.root/'metadata.json',self.metadata())
            before=self.call('/v1/metrics')
            for doc in self.dataset['documents']:
                start=time.perf_counter_ns()
                self.call('/v1/ingest',{'job_id':doc['id']+'-v1','document_id':doc['id'],
                    'media_type':{'text/plain':'Txt','application/json':'Json','application/pdf':'Pdf'}[doc['media_type']],
                    'policy':self.args.policy,'record_pointer':'/matches' if doc['id']=='matches_json' else '',
                    'source_base64':base64.b64encode((ROOT/'evals'/doc['path']).read_bytes()).decode()},expected=202)
                job=self.wait(doc['id']+'-v1')
                results.append({'document':doc['id'],'source_bytes':(ROOT/'evals'/doc['path']).stat().st_size,'seconds':(time.perf_counter_ns()-start)/1e9,'job':job})
                write(self.root/'ingestion-progress.json',results)
                print(self.args.policy,'ingested',doc['id'],round(results[-1]['seconds'],3),flush=True)
            after=self.call('/v1/metrics'); docs=self.snapshot()
        write(self.root/'ingestion.json',{'process_startup_seconds':ready,'wall_seconds':(time.perf_counter_ns()-begin)/1e9,
            'documents':results,'before':before,'after':after,'samples':sampler.samples,'chunks':sum(len(d['chunks']) for d in docs.values())})
    def queries(self):
        if any((self.root/name).exists() for name in ['queries.json','queries-progress.json']): raise ValueError('query capture already exists; choose a new variant')
        results=[]; start=time.perf_counter_ns()
        with Sampler() as sampler:
            self.compose('up','-d','--force-recreate','vectornext','processor')
            self.ready(); startup=(time.perf_counter_ns()-start)/1e9
            docs=self.snapshot(); scorer=Scorer(self.dataset,docs)
            write(self.root/'query-metadata.json',self.metadata())
            ids=set()
            for c in self.cases:
                for s in c['expected'].get('support_sets',[]): ids.update(s)
                for a in c['expected'].get('alternatives',[]): ids.update(a['support_set'])
            write(self.root/'parse-fidelity.json',scorer.parse_fidelity(ids))
            for temperature in ('cold-cache','warm-cache'):
                for case in self.cases:
                    before=self.call('/v1/metrics'); begin=time.perf_counter_ns()
                    code,report=self.client.request('/v1/ask',{'request':public_request(case),'options':self.options})
                    wall=(time.perf_counter_ns()-begin)/1e9
                    filename=temperature+'-'+case['id']+'.json'; (self.root/filename).write_bytes(self.client.raw)
                    after=self.call('/v1/metrics')
                    result={'case':case['id'],'cache':temperature,'http_status':code,'wall_seconds':wall,
                        'before':before,'after':after,'report_file':filename,
                        'score':scorer.case(case,report) if code==200 else None,'error':report if code!=200 else None}
                    results.append(result); write(self.root/'queries-progress.json',results)
                    print(self.args.policy,self.args.variant,temperature,case['id'],code,round(wall,3),result['score']['answer_correct'] if code==200 else report,flush=True)
        write(self.root/'queries.json',{'process_startup_seconds':startup,'samples':sampler.samples,'cases':results})


def main():
    p=argparse.ArgumentParser(); p.add_argument('--phase',choices=['startup','ingest','queries'],required=True)
    p.add_argument('--policy',choices=['plain','structural','generated'],required=True)
    p.add_argument('--run',default='20261014'); p.add_argument('--variant',default='baseline')
    p.add_argument('--database-root',default='/storage')
    p.add_argument('--candidates',type=int,default=30); p.add_argument('--rerank-limit',type=int,default=20)
    p.add_argument('--primary-limit',type=int,default=5); p.add_argument('--no-rerank',action='store_true')
    p.add_argument('--generated-weight',type=float,default=1); p.add_argument('--case',action='append')
    p.add_argument('--structural-weight',type=float,default=1)
    a=p.parse_args()
    if not all(x.replace('-','').isalnum() for x in [a.run,a.variant]): p.error('simple alphanumeric run/variant names required')
    parts=PurePosixPath(a.database_root).parts
    if parts[:2]!=('/','storage') or '..' in parts: p.error('database root must stay under /storage')
    run=Run(a); getattr(run,a.phase)()


if __name__=='__main__': main()
