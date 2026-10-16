"""Explicit bounded evaluation. Standard library; no model download or automatic activation."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import threading
import time
import urllib.error
import urllib.request
import zipfile
from .score import score, exact_load

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'experiments/t36'
IMAGES = ['vectornext-app:t37-hybrid', 'vectornext-app-processor:t37-hybrid', 'vectornext-app-llm:t37-hybrid']
URL = 'http://127.0.0.1:8097'
MODES = ['hybrid', 'nuextract', 'gemma']
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def now(): return datetime.now(timezone.utc).isoformat()
def digest(raw): return hashlib.sha256(raw).hexdigest()
def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, default=str) + '\n', encoding='utf-8')


def command(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True, encoding='utf-8', errors='replace').strip()


def call(path, body=None, timeout=30):
    data = None if body is None else json.dumps(body, separators=(',', ':')).encode()
    req = urllib.request.Request(URL + path, data=data, headers={'Content-Type':'application/json','X-VectorNext-Client':'1'})
    try: response = OPENER.open(req, timeout=timeout)
    except urllib.error.HTTPError as error: response = error
    with response:
        raw = response.read()
        return response.status, raw, json.loads(raw)


def source_files():
    paths = []
    for directory in ['src', 'model_worker', 'model_assets', 'processor', 'deployment', 'frontend/src', 'frontend/public', 'docker', 'experiments/t37', 'experiments/t36']:
        for p in (ROOT / directory).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.log'):
                paths.append(p)
    for name in ['Cargo.toml','Cargo.lock','.dockerignore','compose.app.yaml','compose.t37.yaml','docs/t37-protocol.md','frontend/package.json','frontend/package-lock.json']:
        paths.append(ROOT / name)
    return sorted(set(paths))


def freeze(root):
    if root.exists(): raise SystemExit('Run directory exists; preserve it and choose a fresh name')
    root.mkdir(parents=True)
    files = {p.relative_to(ROOT).as_posix():digest(p.read_bytes()) for p in source_files()}
    with zipfile.ZipFile(root / 'source.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
        for name in files: archive.write(ROOT / name, name)
    manifest = {'created':now(),'protocol':'docs/t37-protocol.md','git_head':command('git','rev-parse','HEAD'),
                'files':files,'source_zip_sha256':digest((root/'source.zip').read_bytes()),
                'images':{image:command('docker','image','inspect',image,'--format','{{.Id}}') for image in IMAGES},
                'compose':json.loads(command('docker','compose','-f','compose.t37.yaml','config','--format','json')),
                'gpu':command('nvidia-smi','--query-gpu=name,memory.total,driver_version','--format=csv,noheader'),
                'modes':MODES,'requests':24,'retry_failed_measurements':False}
    write(root/'execution-freeze.json',manifest)
    print('Frozen', len(files), 'files and three images:', root, flush=True)


def verify(root):
    manifest = json.loads((root/'execution-freeze.json').read_bytes())
    for name, expected in manifest['files'].items():
        if digest((ROOT/name).read_bytes()) != expected: raise SystemExit('Frozen source changed: '+name)
    for image, expected in manifest['images'].items():
        if command('docker','image','inspect',image,'--format','{{.Id}}') != expected: raise SystemExit('Frozen image changed: '+image)
    return manifest


def ingest(root):
    verify(root)
    directory = root/'corpus'
    if directory.exists(): raise SystemExit('Corpus attempt exists; do not rerun ingestion into success')
    directory.mkdir()
    code, raw, library = call('/v1/ui/library')
    if code != 200 or library['documents'] or library['jobs']: raise SystemExit('Isolated empty storage required')
    for source in json.loads((FIXTURES/'sources.json').read_bytes())['sources']:
        identity = source['id']; path = FIXTURES/source['file']
        payload = {'job_id':'t37-'+identity,'document_id':identity,'media_type':{'.txt':'Txt','.json':'Json','.pdf':'Pdf'}[path.suffix],
                   'policy':'structural','source_base64':base64.b64encode(path.read_bytes()).decode()}
        started = time.monotonic()
        try:
            code, raw, job = call('/v1/ingest',payload,timeout=240)
            (directory/(identity+'.submit.json')).write_bytes(raw)
            while code in (200,202) and not job.get('last_failure') and job.get('stage') != 'Committed':
                if time.monotonic()-started > 900: raise TimeoutError('ingestion wait exceeded')
                time.sleep(.5); code, raw, job = call('/v1/job',{'job_id':'t37-'+identity})
            (directory/(identity+'.job.json')).write_bytes(raw)
            code, raw, doc = call('/v1/document',{'document_id':identity})
            (directory/(identity+'.document.json')).write_bytes(raw)
            write(directory/(identity+'.outcome.json'),{'status':code,'seconds':time.monotonic()-started})
            print('Ingest',identity,job.get('stage'),job.get('last_failure'),flush=True)
        except Exception as error:
            write(directory/(identity+'.failure.json'),{'error':str(error),'seconds':time.monotonic()-started})
            print('Ingest failure retained:',identity,str(error),flush=True)
    (directory/'library.json').write_bytes(call('/v1/ui/library')[1])


def memory():
    if os.name != 'nt': return None
    import ctypes
    class Status(ctypes.Structure):
        _fields_ = [('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(s,ctypes.c_ulonglong) for s in ('physical','available','page','free_page','virtual','free_virtual','extended')]
    state = Status(); state.length = ctypes.sizeof(state)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state))
    return {'physical_bytes':state.physical,'available_bytes':state.available,'load_percent':state.load}


def sample(root, stop):
    with (root/'resources.jsonl').open('a',encoding='utf-8') as stream:
        while not stop.is_set():
            row = {'at':now(),'ram':memory()}
            try: row['gpu'] = subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,memory.total,utilization.gpu','--format=csv,noheader,nounits'],text=True,timeout=5).strip()
            except Exception as error: row['error'] = str(error)
            stream.write(json.dumps(row)+'\n');stream.flush();stop.wait(3)


def run(root):
    verify(root)
    requests = json.loads((FIXTURES/'requests.json').read_bytes())
    stop = threading.Event(); sampler = threading.Thread(target=sample,args=(root,stop));sampler.start()
    try:
        for mode in MODES:
            directory = root/mode; directory.mkdir(exist_ok=True)
            pending = {}
            for identifier,payload in requests.items():
                marker = directory/(identifier+'.submission.json')
                if marker.exists():
                    # A restart can poll admitted jobs; it never repeats a measured POST.
                    saved = json.loads(marker.read_bytes())
                    if not (directory/(identifier+'.outcome.json')).exists(): pending[identifier]=saved
                    continue
                saved = {'request_id':f't37-{root.name}-{mode}-{identifier}'.replace('_','-'),'mode':mode,'kind':'ui','payload':payload}
                record = {'submission':saved,'started_epoch':time.time(),'started':now()}
                write(marker,record)  # preserve intention before sending even on interruption
                try:
                    code,raw,job = call('/v1/answer-jobs',saved)
                    (directory/(identifier+'.ack.json')).write_bytes(raw)
                    if code == 202: pending[identifier]=record
                    else:
                        (directory/(identifier+'.response.json')).write_bytes(raw)
                        write(directory/(identifier+'.outcome.json'),{'status':code,'seconds':time.time()-record['started_epoch'],'admitted':False})
                except Exception as error:
                    write(directory/(identifier+'.submission-error.json'),{'error':str(error)})
                    pending[identifier]=record
            while pending:
                for identifier,record in list(pending.items()):
                    elapsed = time.time()-record['started_epoch']
                    try:
                        code,raw,job = call('/v1/answer-jobs/'+record['submission']['request_id'])
                        if code == 404:
                            (directory/(identifier+'.response.json')).write_bytes(raw)
                            write(directory/(identifier+'.outcome.json'),{'status':code,'seconds':elapsed,'admitted':False,'uncertain':True})
                            del pending[identifier];continue
                        if code != 200: continue
                        statefile=directory/(identifier+'.states.jsonl')
                        if record.get('last_state') != job['state']:
                            with statefile.open('a',encoding='utf-8') as stream: stream.write(json.dumps({'at':now(),'elapsed':elapsed,'state':job['state'],'fallback':job.get('fallback_reason')})+'\n')
                            record['last_state']=job['state']
                            print(mode,identifier,job['state'],round(elapsed,1),'s',flush=True)
                        if job['terminal']:
                            (directory/(identifier+'.job.json')).write_bytes(raw)
                            final=job.get('response_text',json.dumps({'error':{'code':'job_'+job['state'],'message':job.get('error')}}))
                            (directory/(identifier+'.response.json')).write_text(final,encoding='utf-8')
                            write(directory/(identifier+'.outcome.json'),{'status':job.get('status_code',503),'seconds':elapsed,'admitted':True,'state':job['state']})
                            del pending[identifier]
                    except Exception as error:
                        with (directory/'poll-errors.jsonl').open('a',encoding='utf-8') as stream: stream.write(json.dumps({'at':now(),'case':identifier,'error':str(error)})+'\n')
                    if elapsed > 2400: raise TimeoutError('Job still pending after operational deadline; preserved for reconciliation')
                time.sleep(.5)
            (directory/'readiness.json').write_bytes(call('/readyz')[1])
    finally: stop.set();sampler.join()
    report(root)


def distribution(values):
    if not values: return None
    values=sorted(values)
    return {'n':len(values),'median':statistics.median(values),'p95':values[min(len(values)-1, __import__('math').ceil(len(values)*.95)-1)],'min':values[0],'max':values[-1]}


def generation_times(value, seen=None):
    if seen is None: seen=set()
    if isinstance(value,dict):
        if isinstance(value.get('inference_seconds'),(float,int)):
            identity=(value.get('request_sha256'),value.get('inference_seconds'))
            if identity not in seen:
                seen.add(identity);yield value['inference_seconds']
        for key,item in value.items():
            if key in ('response_text','raw_report') and isinstance(item,str):
                try: yield from generation_times(json.loads(item),seen)
                except ValueError: pass
            elif key != 'answer_job': yield from generation_times(item,seen)
    elif isinstance(value,list):
        for item in value: yield from generation_times(item,seen)


def report(root):
    gold=exact_load((FIXTURES/'gold.json').read_bytes());documents={}
    for p in (root/'corpus').glob('*.document.json'):
        body=exact_load(p.read_bytes())
        if 'document' in body: documents[body['document']['document_id']]=body['document']
    results={'run':root.name,'protocol':'docs/t37-protocol.md','source_sha256':digest((root/'execution-freeze.json').read_bytes()),'modes':{}}
    for mode in MODES:
        rows=[]
        for identifier,label in gold.items():
            directory=root/mode; outcome=json.loads((directory/(identifier+'.outcome.json')).read_bytes())
            raw=(directory/(identifier+'.response.json')).read_bytes()
            path=directory/(identifier+'.job.json');job=json.loads(path.read_bytes()) if path.exists() else {}
            attempts=job.get('attempts',[])
            observed=list(generation_times(attempts))
            rows.append({'case':identifier,**outcome,'score':score(identifier,outcome['status'],raw,label,documents),
                         'attempts':len(attempts),'models':[a['model'] for a in attempts], 'fallback_reason':job.get('fallback_reason'),
                         'queue_seconds':sum(a['queue_ms'] for a in attempts)/1000,'activation_seconds':sum(a['activation_ms'] for a in attempts)/1000,
                         'work_seconds':sum(a['work_ms'] for a in attempts)/1000,'observed_generation_seconds':sum(observed) if observed else None})
        results['modes'][mode]={'correct':sum(r['score']['correct'] for r in rows),'denominator':8,
            'original_scorer_correct':sum(r['score']['original_score_correct'] for r in rows),'fallbacks':sum(r['attempts']==2 for r in rows),
            'timings':{key:distribution([r[key] for r in rows if r[key] is not None]) for key in ('seconds','queue_seconds','activation_seconds','work_seconds','observed_generation_seconds')},'cases':rows}
    write(root/'summary.json',results)
    print(json.dumps({m:{k:v for k,v in a.items() if k!='cases'} for m,a in results['modes'].items()},indent=2),flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['freeze','ingest','run','report','verify']);p.add_argument('--run',required=True)
    a=p.parse_args()
    if not a.run.replace('-','').isalnum(): raise SystemExit('Use a short alphanumeric/hyphen run name')
    globals()[a.action](ROOT/'data/t37'/a.run)
