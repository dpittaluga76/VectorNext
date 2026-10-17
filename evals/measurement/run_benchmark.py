"""Execute an independently approved, frozen development benchmark using durable jobs.

No setup, ingestion, model downloads, prompt tuning, or automatic resubmission.
The custodian must separately release a sealed execution freeze after selection.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request
from .oracle import encoded, save
from .review import checked_file, sha

OPTIONS={
    'five':{'candidates':30,'rerank_limit':20,'primary_limit':5,'rerank':True,'evidence_strategy':'ranked'},
    'two':{'candidates':30,'rerank_limit':20,'primary_limit':2,'rerank':True,'evidence_strategy':'ranked'},
    'facet':{'candidates':30,'rerank_limit':20,'primary_limit':5,'rerank':True,'evidence_strategy':'facet_coverage_v1'}}


def schedule(cases,arms):
    if not cases or set(arms)-set(OPTIONS) or len(arms)!=len(set(arms)) or 'five' not in arms:
        raise ValueError('invalid cases/strategy arms')
    if len({c['case_id'] for c in cases})!=len(cases): raise ValueError('duplicate case')
    for case in cases:
        shift=int(hashlib.sha256(case['family'].encode()).hexdigest(),16)%len(arms)
        for arm in arms[shift:]+arms[:shift]: yield case,arm


def request_id(freeze_hash,case_id,arm):
    return 't39-'+sha(encoded([freeze_hash,case_id,arm]))[:56]


def validate_freeze(root,freeze):
    if freeze.get('version')!=1 or freeze.get('model')!='nuextract': raise ValueError('unsupported execution freeze')
    if freeze.get('split') not in ('development','sealed'): raise ValueError('invalid split')
    if freeze['split']=='sealed' and not freeze.get('custodian_release_sha256'):
        raise ValueError('sealed execution needs separate custodian release')
    acceptance=checked_file(root,freeze['review_acceptance']).read_bytes()
    if sha(acceptance)!=freeze['review_acceptance_sha256']: raise ValueError('review acceptance changed')
    review=json.loads(acceptance)
    if review.get('status')!='independent_review_accepted': raise ValueError('independent approval required')
    manifest_raw=checked_file(root,freeze['package_manifest']).read_bytes()
    if sha(manifest_raw)!=review['manifest_sha256']: raise ValueError('execution package differs from approved review')
    manifest=json.loads(manifest_raw)
    for name in (freeze['requests'],freeze['protocol']):
        if manifest['files'].get(name)!=freeze.get('files',{}).get(name):
            raise ValueError('protocol/requests must belong to approved package')
    if freeze['requests'] not in freeze.get('files',{}): raise ValueError('public requests must be frozen')
    if not freeze.get('files') or freeze.get('protocol') not in freeze['files']:
        raise ValueError('protocol and inputs must be frozen')
    for name,expected in freeze['files'].items():
        if sha(checked_file(root,name).read_bytes())!=expected: raise ValueError('frozen file changed: '+name)
    if freeze.get('code_files',{}).get('evals/measurement/run_benchmark.py')!=sha(Path(__file__).read_bytes()):
        raise ValueError('runner identity differs')
    repo=Path(__file__).resolve().parents[2]
    for name,expected in freeze['code_files'].items():
        if sha(checked_file(repo,name).read_bytes())!=expected: raise ValueError('code identity differs: '+name)
    if not freeze.get('warmup_capture_sha256'): raise ValueError('separate synthetic warmup capture required')
    cases=json.loads(checked_file(root,freeze['requests']).read_text(encoding='utf-8'))
    if any(c['split']!=freeze['split'] for c in cases): raise ValueError('mixed splits')
    if freeze['split']=='development' and freeze['arms']!=['five','two','facet']:
        raise ValueError('development must include all predeclared arms')
    if freeze['split']=='sealed' and (len(freeze['arms'])!=2 or 'five' not in freeze['arms']):
        raise ValueError('sealed comparison must contain control plus one selected candidate')
    list(schedule(cases,freeze['arms']))
    return cases


def validate_runtime(freeze):
    containers=freeze['containers']
    if set(containers)!= {'api','processor','llm'}: raise ValueError('freeze all three runtime images')
    ids=[v['id'] for v in containers.values()]
    observed=json.loads(subprocess.check_output(['docker','inspect',*ids]))
    by_id={c['Id']:c for c in observed}
    for kind,expected in containers.items():
        c=by_id[expected['id']]
        if not c['State']['Running'] or c['Image']!=expected['image']:
            raise ValueError('runtime image/running state changed: '+kind)
        if (c['Config'].get('Labels') or {}).get('vectornext.measurement')!='T39':
            raise ValueError('requires explicitly labelled isolated T39 containers')
        if any(m.get('Name') in ('vectornext_data','vectornext_cache') for m in c['Mounts']):
            raise ValueError('normal application volumes must not be benchmarked')
    return observed


def run(root,freeze_path,api,output,*,transport=None,check_runtime=True):
    raw=freeze_path.read_bytes();freeze=json.loads(raw);freeze_hash=sha(raw)
    cases=validate_freeze(root,freeze)
    runtime=validate_runtime(freeze) if check_runtime else []
    if not output.exists():
        output.mkdir(parents=True)
        save(output/'freeze.json',raw);save(output/'runtime.json',encoded(runtime))
    elif (output/'freeze.json').read_bytes()!=raw: raise ValueError('resume freeze differs')
    if transport is None:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        def transport(path,body=None):
            req=urllib.request.Request(api.rstrip('/')+path,data=body,
                headers={'Content-Type':'application/json','X-VectorNext-Client':'1'})
            try: response=opener.open(req,timeout=30)
            except urllib.error.HTTPError as e: response=e
            with response: return response.status,response.read()
    def get(path):
        status,data=transport(path)
        if status!=200: raise RuntimeError(f'GET {path}: HTTP {status}')
        return json.loads(data)
    committed={b['document_id']:b['revision'] for b in freeze['bindings'].values() if b['state']=='committed'}
    def check_library():
        library=get('/v1/ui/library')
        actual={d['document_id']:d['revision'] for d in library['documents']}
        if actual!=committed or any(d['processing'] for d in library['documents']):
            raise ValueError('committed document set/revisions differ from ingestion freeze')
    check_library()
    for case,arm in schedule(cases,freeze['arms']):
        identity=request_id(freeze_hash,case['case_id'],arm)
        dest=output/identity
        if (dest/'finished.json').exists(): continue
        check_library()
        binding=freeze['bindings'][case['document']]
        if binding['state']!='committed':
            dest.mkdir(exist_ok=True)
            save(dest/'finished.json',encoded({'case_id':case['case_id'],'arm':arm,'state':'ingestion_failed',
                'binding':binding,'included_in_denominator':True}))
            continue
        payload={'request_id':identity,'mode':'nuextract','kind':'ui','payload':{
            'question':case['question'],'history':case.get('history',[]),'document_ids':[binding['document_id']],
            'prose':False,'options':OPTIONS[arm]}}
        start=time.monotonic();resumed=(dest/'started.json').exists()
        if (dest/'job.json').exists():
            job=json.loads((dest/'job.json').read_bytes())
            if not job.get('terminal') or job.get('request_id')!=identity or job.get('mode')!='nuextract':
                raise ValueError('saved completion has wrong state/identity/mode')
            save(dest/'finished.json',encoded({'case_id':case['case_id'],'arm':arm,'state':'captured',
                'wall_ms':None,'job_total_ms':job.get('total_ms'),'observer_resumed':True,
                'included_in_denominator':True}))
            continue
        if not resumed:
            dest.mkdir(exist_ok=True)
            save(dest/'started.json',encoded({'case_id':case['case_id'],'arm':arm,'request_id':identity,
                'request':payload,'started_unix':time.time()}))
            try:
                status,reply=transport('/v1/answer-jobs',encoded(payload))
                save(dest/'submission.json',reply)
                if status!=202:
                    save(dest/'finished.json',encoded({'case_id':case['case_id'],'arm':arm,'state':'submission_failed',
                        'status':status,'wall_ms':(time.monotonic()-start)*1000,'included_in_denominator':True}))
                    continue
            except (OSError,TimeoutError):
                # Only read/reconcile. Do not send the question again, even if
                # the original request never reached the server.
                pass
        path='/v1/answer-jobs/'+identity
        while True:
            status,reply=transport(path)
            if status!=200:
                raise RuntimeError(f'uncertain {identity}: HTTP {status}; preserved started record, no resubmission')
            job=json.loads(reply)
            if job.get('request_id')!=identity or job.get('mode')!='nuextract':
                raise ValueError('reconciled job has wrong request identity/model mode')
            if job['terminal']:
                save(dest/'job.json',reply)
                save(dest/'finished.json',encoded({'case_id':case['case_id'],'arm':arm,'state':'captured',
                    'wall_ms':None if resumed else (time.monotonic()-start)*1000,
                    'job_total_ms':job.get('total_ms'),'observer_resumed':resumed,'included_in_denominator':True}))
                break
            if time.monotonic()-start>1800:
                raise TimeoutError('observer deadline; durable job retained, resume by polling only')
            time.sleep(.5)
    return {'planned_requests':len(cases)*len(freeze['arms']),'freeze_sha256':freeze_hash,'output':str(output)}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--package',type=Path,required=True);p.add_argument('--freeze',type=Path,required=True)
    p.add_argument('--api',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(run(a.package,a.freeze,a.api,a.output),indent=2))


if __name__=='__main__': main()
