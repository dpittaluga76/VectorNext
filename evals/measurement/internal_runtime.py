"""Private, isolated T39 runtime. No model calls during setup or ingestion."""
import argparse
import base64
import json
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request

from .families import digest, encoded, load
from .internal_successor import safe_file
from .oracle import save as raw_save

ROOT = Path(__file__).resolve().parents[2]
PACKAGE_SHA = '40edecc22f0a7212e8dd6f31aa9a1d3907f610b78e6b64e795b0947f859efb6e'
SPLITS = ('development', 'exposed_candidates')


def save(path, value):
    raw_save(path, encoded(value))


def docker(*args):
    return subprocess.check_output(['docker', *map(str,args)], text=True, encoding='utf8')


def wire(url, path, body=None, timeout=30):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(url.rstrip('/')+path, data=body,
        headers={'Content-Type':'application/json','X-VectorNext-Client':'1'})
    try:
        response = opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, response.read()


def get(url,path,body=None):
    status, raw = wire(url,path,None if body is None else encoded(body),900)
    if status != 200:
        raise RuntimeError(f'{path}: HTTP {status}: {raw[:300]!r}')
    return json.loads(raw)


def verify_package(package):
    raw = (package/'manifest.json').read_bytes()
    if digest(raw) != PACKAGE_SHA:
        raise ValueError('Wrong internal successor package')
    for name, expected in json.loads(raw)['files'].items():
        if digest(safe_file(package,name).read_bytes()) != expected:
            raise ValueError('Package member changed: '+name)


def setup(output):
    output.mkdir(parents=True,exist_ok=False)
    images = {k:json.loads(docker('image','inspect',tag))[0]['Id'] for k,tag in
              [('api','vectornext-app:t39'),('processor','vectornext-app-processor:t39'),
               ('llm','vectornext-app-llm:t39')]}
    # Explicit fresh names; never derive a benchmark volume from application mounts.
    name='vectornext-t39-internal'
    if docker('ps','-a','--filter',f'label=com.docker.compose.project={name}','-q').strip():
        raise ValueError('Existing evaluation containers: inspect before setup')
    for volume in ('data','cache'):
        if docker('volume','ls','-q','--filter',f'name=^{name}-{volume}$').strip():
            raise ValueError('Existing benchmark volume; new setup may not reuse it')
    base={'init':True,'read_only':True,'restart':'no','cap_drop':['ALL'],
          'security_opt':['no-new-privileges:true'],'labels':{'vectornext.measurement':'T39'},
          'networks':['local'],'tmpfs':['/tmp:exec,size=1073741824']}
    model_mount=f'{(ROOT/"models").as_posix()}:/models:ro'
    captures=output/'rpc'; captures.mkdir()
    services={
      'vectornext':{**base,'image':images['api'],'cpus':2,'mem_limit':'4g',
        'environment':{'VECTORNEXT_DATA':'/storage/db','VECTORNEXT_DEFAULT_ANSWER_MODE':'nuextract',
                       'VECTORNEXT_PROCESSOR_URL':'http://processor:8090'},
        'volumes':['data:/storage'],'networks':['local','ingress'],'ports':['127.0.0.1:8098:8088']},
      'processor':{**base,'image':images['processor'],'cpus':4,'mem_limit':'6g',
        'command':['python','-m','evals.measurement.evaluation_processor','--capture-root','/captures'],
        'volumes':[model_mount,'cache:/cache',f'{captures.as_posix()}:/captures',
                   *[f'{(ROOT/p).as_posix()}:/app/{p}:ro' for p in ('evals','model_worker','model_assets','deployment','experiments')]],
        'networks':['local','ingress'],'ports':['127.0.0.1:8099:8090']},
      'llm':{**base,'image':images['llm'],'cpus':8,'mem_limit':'32g','gpus':'all',
        'command':[],'volumes':[model_mount], 'networks':['local','ingress'],
        'ports':['127.0.0.1:8100:8080']}}
    config={'name':name,'services':services,'networks':{'local':{'internal':True},'ingress':{}},
            'volumes':{v:{'name':name+'-'+v} for v in ('data','cache')}}
    save(output/'compose.json',config)
    save(output/'setup.json',{'images':images,'normal_runtime':json.loads(docker('inspect',
        'vectornext-vectornext-1','vectornext-processor-1','vectornext-llm-1'))})
    docker('compose','-f',output/'compose.json','up','-d','vectornext','processor')


def ingest(package,output,api='http://127.0.0.1:8098'):
    verify_package(package)
    directory=output/'ingestion'; directory.mkdir(exist_ok=True)
    entries=[]
    for split in SPLITS:
        for descriptor in load(package/split/'documents.json'):
            for representation in ('v2','v1'):
                if representation=='v1' and (split!='development' or descriptor['format']!='json'):
                    continue
                rep=descriptor['representations'][representation]
                key='/'.join((split,representation,descriptor['document']))
                identity='t39-'+digest(key.encode())[:40]
                destination=directory/identity; destination.mkdir(exist_ok=True)
                if (destination/'binding.json').exists():
                    entries.append(load(destination/'binding.json')); continue
                request={'job_id':identity,'document_id':identity,'expected_revision':None,
                    'media_type':{'txt':'Txt','json':'Json','pdf':'Pdf'}[descriptor['format']],
                    'policy':'structural','record_pointer':rep['record_pointer'] or '',
                    'allow_partial':False,'source_base64':base64.b64encode((package/rep['path']).read_bytes()).decode()}
                if not (destination/'started.json').exists():
                    save(destination/'started.json',{'key':key,'request_sha256':digest(encoded(request))})
                    try:
                        status,raw=wire(api,'/v1/ingest',encoded(request),900)
                        (destination/'submission.raw.json').write_bytes(raw)
                        save(destination/'submission-status.json',{'status':status})
                        if status!=202:
                            binding={'key':key,'state':'ingestion_failed','status':status,'document_id':identity}
                            save(destination/'binding.json',binding); entries.append(binding); continue
                    except (OSError,TimeoutError):
                        pass # Read/reconcile the stable ingestion identity only.
                start=time.monotonic()
                while True:
                    job=get(api,'/v1/job',{'job_id':identity})
                    if (job.get('stage')=='Committed' or job.get('last_failure') or
                            job.get('coordinator',{}).get('state') in ('failed','stopped')):
                        break
                    if time.monotonic()-start>1800:
                        raise TimeoutError('Uncertain ingestion retained; no retry')
                    time.sleep(.5)
                save(destination/'job.json',job)
                binding={'key':key,'state':'committed' if job['stage']=='Committed' else 'ingestion_failed',
                         'document_id':identity,'revision':job.get('revision')}
                if binding['state']=='committed':
                    snapshot=get(api,'/v1/document',{'document_id':identity})['document']
                    if snapshot['original']['sha256']!=rep['sha256'] or snapshot['revision']!=binding['revision']:
                        raise ValueError('Committed snapshot differs from source/binding')
                    save(destination/'snapshot.json',snapshot)
                save(destination/'binding.json',binding); entries.append(binding)
                print(json.dumps({'ingested':len(entries),'state':binding['state']}),flush=True)
    save(output/'bindings.json',entries)


def context(package,output,split,document,representation='v2'):
    descriptor=next(d for d in load(package/split/'documents.json') if d['document']==document)
    key='/'.join((split,representation,document))
    binding=next(b for b in load(output/'bindings.json') if b['key']==key)
    folder=output/'ingestion'/binding['document_id']
    result={'binding':binding,'descriptor':descriptor,'representation':representation,
            'text':(package/descriptor['review_text_path']).read_text(encoding='utf8'),
            'original':(package/descriptor['representations']['v1']['path']).read_bytes()}
    # v1 table representation is the original adapter, not the raw reviewed table.
    if descriptor['format']=='json':
        annotation=load(package/split/'annotations'/document)
        result['annotation']=annotation
    if binding['state']=='committed':
        result['snapshot']=load(folder/'snapshot.json')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation',choices=['setup','ingest','inventory']);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--package',type=Path);p.add_argument('--binary',type=Path)
    a=p.parse_args();a.output=a.output.resolve()
    if a.operation=='setup': setup(a.output)
    elif a.operation=='ingest': ingest(a.package.resolve(),a.output)
    else:
        count=0
        for snapshot in (a.output/'ingestion').glob('*/snapshot.json'):
            dest=snapshot.with_name('evidence.json')
            if not dest.exists():
                subprocess.run([str(a.binary),str(snapshot),str(dest)],check=True)
            count+=1
        print(json.dumps({'snapshots':count}))


if __name__=='__main__': main()
