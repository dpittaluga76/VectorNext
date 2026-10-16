"""24-request one-pass pilot, isolated storage, unchanged shared generator."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import zipfile
from deployment.client import Client

HERE = Path('experiments/t32')
ARMS = [('minilm-minilm','minilm','minilm'), ('nomic-ettin','nomic-v1.5','ettin-17m'),
        ('nomic-minilm','nomic-v1.5','minilm'), ('minilm-ettin','minilm','ettin-17m')]


def write(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate():
    for path, expected in json.loads((HERE/'input-freeze.json').read_bytes()).items():
        if digest(HERE/path) != expected: raise ValueError('frozen input changed: '+path)
    requests=json.loads((HERE/'requests.json').read_bytes())
    gold=json.loads((HERE/'gold.json').read_bytes())
    if len(requests)!=6 or list(requests)!=list(gold) or len(ARMS)!=4: raise ValueError('24-request bound')
    return requests


class Run:
    def __init__(self, name):
        if not name or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in name):
            raise ValueError('simple fresh run name required')
        self.project='vectornext-t32-'+name
        self.root=Path('data/t32')/name
        self.root.mkdir(exist_ok=False)
        self.env=os.environ.copy()
        self.client=Client('http://127.0.0.1:8101')
        self.normal=Client('http://127.0.0.1:8088')
        self.freeze=None

    def shell(self, *command):
        result=subprocess.run(command,env=self.env,capture_output=True,text=True,encoding='utf-8')
        with (self.root/'commands.log').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(command)+'\n'+result.stdout+result.stderr+'\n')
        if result.returncode: raise RuntimeError(result.stderr[-2000:])
        return result.stdout.strip()

    def compose(self,*args):
        return self.shell('docker','compose','-f','compose.t32.yaml','-p',self.project,*args)

    def call(self,path,body=None,expected=200,client=None):
        code,value=(client or self.client).request_once(path,body)
        if code!=expected: raise RuntimeError((path,code,value))
        return value

    def normal_state(self):
        return {name:self.call(path,client=self.normal) for name,path in
            [('documents','/v1/documents'),('library','/v1/ui/library'),('ready','/readyz')]}

    def snapshot(self):
        return {d['document_id']:self.call('/v1/document',{'document_id':d['document_id']})['document']
                for d in self.call('/v1/documents')['documents']}

    def verify(self):
        validate()
        if any(digest(p)!=h for p,h in self.freeze['files'].items()): raise ValueError('execution inputs changed')
        for tag,identity in self.freeze['images'].items():
            if self.shell('docker','image','inspect',tag,'--format','{{.Id}}')!=identity:
                raise ValueError('image changed during run')
        current=json.loads(self.shell('docker','inspect','vectornext-llm-1'))[0]
        if current['Id']!=self.freeze['generator']['Id']: raise ValueError('normal generator recreated')

    def select(self,embedding,reranker,cache,folder):
        self.env.update(T32_EMBEDDING=embedding,T32_RERANKER=reranker,T32_CACHE=cache)
        self.compose('stop','api','t32-processor')
        started=time.monotonic()
        self.compose('up','-d','--no-build','--pull','never','--force-recreate')
        deadline=time.monotonic()+240
        last=None
        while time.monotonic()<deadline:
            try:
                code,last=self.client.request_once('/readyz',timeout=10)
                if code==200: break
            except (OSError,ValueError) as error: last=str(error)
            time.sleep(1)
        else: raise RuntimeError(('startup failed',last))
        write(folder/'startup.json',{'seconds':time.monotonic()-started,'ready':last})
        (folder/'compose.json').write_text(self.compose('config','--format','json'),encoding='utf-8')

    def ingest(self,embedding):
        folder=self.root/embedding;folder.mkdir()
        self.select(embedding,'minilm','ingest/'+embedding,folder)
        if self.call('/v1/documents')['documents'] or self.call('/v1/jobs')['jobs']:
            raise ValueError('fresh storage required')
        rows=[]
        for source in json.loads((HERE/'sources.json').read_bytes())['sources']:
            path=HERE/source['file'];identifier=source['id'];started=time.monotonic()
            try:
                code,value=self.client.request_once('/v1/ingest',{'job_id':'t32-'+identifier,
                    'document_id':identifier,'policy':'structural','record_pointer':'',
                    'media_type':{'.txt':'Txt','.pdf':'Pdf','.json':'Json'}[path.suffix],
                    'source_base64':base64.b64encode(path.read_bytes()).decode()})
                (folder/(identifier+'.admission.json')).write_bytes(self.client.raw)
                if code==202: code,value=self.client.wait('t32-'+identifier)
                row={'document':identifier,'committed':code==200 and value.get('stage')=='Committed',
                    'http_status':code,'job':value}
            except Exception as error: row={'document':identifier,'committed':False,'error':str(error)}
            row['seconds']=time.monotonic()-started;rows.append(row)
            write(folder/'ingestion.json',rows)
            print('ingest',embedding,identifier,row['committed'],round(row['seconds'],2),flush=True)
        documents=self.snapshot();write(folder/'documents.json',documents)
        return documents

    def sample(self,stop,folder):
        ids=[self.compose('ps','-q',s) for s in ('api','t32-processor')]
        with (folder/'resources.jsonl').open('x',encoding='utf-8') as stream:
            while not stop.is_set():
                result=subprocess.run(['docker','stats','--no-stream','--format','{{json .}}',*ids],
                    capture_output=True,text=True,encoding='utf-8')
                stream.write(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),'exit':result.returncode,
                    'rows':[json.loads(x) for x in result.stdout.splitlines()]})+'\n');stream.flush()
                stop.wait(2)

    def execute(self):
        requests=validate()
        existing=self.shell('docker','volume','ls','--format','{{.Name}}').splitlines()
        if any(v.startswith(self.project+'_') for v in existing): raise ValueError('existing project volumes')
        before=self.normal_state();write(self.root/'normal-before.json',before)
        paths={p for directory in ('model_worker','deployment','experiments/t32') for p in Path(directory).rglob('*')
               if p.is_file() and '__pycache__' not in p.parts}
        paths|={Path(p) for p in ('compose.t32.yaml','docker/app-processor.Dockerfile','experiments/t02/encoders.py',
            'experiments/t02/fetch_models.py','experiments/t02/requirements.txt','experiments/t02/models.lock.json',
            'experiments/t02/models.26b.lock.json','experiments/t27/models.12b.lock.json','experiments/t31/models.bge.lock.json',
            'evals/evidence/score.py')}
        generator=json.loads(self.shell('docker','inspect','vectornext-llm-1'))[0]
        self.freeze={'created':datetime.now(timezone.utc).isoformat(),'requests':24,'arms':ARMS,
            'commit':self.shell('git','rev-parse','HEAD'),'project':self.project,
            'files':{p.as_posix():digest(p) for p in sorted(paths)},
            'images':{tag:self.shell('docker','image','inspect',tag,'--format','{{.Id}}') for tag in
                ('vectornext-app:t28-12b','vectornext-app-processor:t32')},
            'generator':{k:generator[k] for k in ('Id','Image','Config')},
            'normal_containers':json.loads(self.shell('docker','inspect','vectornext-vectornext-1','vectornext-processor-1'))}
        write(self.root/'execution-freeze.json',self.freeze)
        with zipfile.ZipFile(self.root/'source.zip','x',zipfile.ZIP_DEFLATED) as archive:
            for path in paths:archive.write(path,path.as_posix())
        try:
            documents={model:self.ingest(model) for model in ('minilm','nomic-v1.5')}
            for arm,embedding,reranker in ARMS:
                self.verify();folder=self.root/arm;folder.mkdir()
                self.select(embedding,reranker,'query/'+arm,folder)
                if self.snapshot()!=documents[embedding]:raise ValueError('shared snapshot changed')
                warmup=self.shell('docker','compose','-f','compose.t32.yaml','-p',self.project,
                    'exec','-T','t32-processor','python','-c',(HERE/'warmup.py').read_text(encoding='utf-8'))
                (folder/'warmup.json').write_text(warmup,encoding='utf-8')
                stop=threading.Event();sampler=threading.Thread(target=self.sample,args=(stop,folder));sampler.start()
                try:
                    for identifier,request in requests.items():
                        # Exclusive marker is written before dispatch. This runner never resumes/retries.
                        with (folder/(identifier+'.attempt.json')).open('x',encoding='utf-8') as stream:
                            json.dump({'utc':datetime.now(timezone.utc).isoformat()},stream)
                        started=time.monotonic();error=None
                        try:
                            code,_=self.client.request_once('/v1/ask',{'request':request,
                                'options':{'candidates':30,'rerank_limit':20,'primary_limit':5,'rerank':True,'evidence_strategy':'ranked'}})
                            raw=self.client.raw
                        except Exception as failure:code,raw,error=0,b'',str(failure)
                        seconds=time.monotonic()-started
                        (folder/(identifier+'.response.json')).write_bytes(raw)
                        write(folder/(identifier+'.row.json'),{'case':identifier,'http_status':code,
                            'seconds':seconds,'error':error,'response_sha256':hashlib.sha256(raw).hexdigest()})
                        print(arm,identifier,code,round(seconds,2),flush=True)
                finally:stop.set();sampler.join()
                if self.snapshot()!=documents[embedding]:raise ValueError('snapshot mutated by requests')
            self.verify()
            from .score import summarize
            summary=summarize(self.root);write(self.root/'summary.json',summary)
            print(json.dumps({a:v['correct'] for a,v in summary['arms'].items()}),flush=True)
        finally:
            (self.root/'services.log').write_text(self.compose('logs','--no-color'),encoding='utf-8')
            self.compose('stop','api','t32-processor')
            after=self.normal_state();write(self.root/'normal-after.json',after)
            if before['documents']!=after['documents'] or before['library']!=after['library']:
                raise ValueError('normal library changed during run')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True)
    Run(parser.parse_args().run).execute()
