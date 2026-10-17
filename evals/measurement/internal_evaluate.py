"""Execute the exposed internal pilot; preserves the independent runner's gate."""
import argparse
from copy import deepcopy
import itertools
import json
from pathlib import Path
import subprocess
import time
import uuid

from .capture_grounding import prose_coordinates, table_coordinates
from .capture_projection import project
from .families import PRIMARY, digest, encoded, load
from .internal_runtime import ROOT, SPLITS, PACKAGE_SHA, context, docker, get, verify_package, wire, save
from .oracle import save as raw_save, encoded as rpc_encoded
from .run_benchmark import OPTIONS, schedule
from .table_grounding import covers

API='http://127.0.0.1:8098'
PROCESSOR='http://127.0.0.1:8099'


def mounts_equal(actual,expected):
    # Docker does not guarantee the order of Mounts in separate inspect calls.
    return sorted(actual,key=lambda m:m['Destination'])==sorted(expected,key=lambda m:m['Destination'])


def verified(root):
    freeze=load(root/'execution-freeze.json')
    if freeze['classification']!='internal_exposed_pilot' or freeze['independent_review']:
        raise ValueError('Internal/exposure disclosure missing')
    if freeze['package_sha256']!=PACKAGE_SHA:
        raise ValueError('Wrong package freeze')
    package=Path(freeze['package']); verify_package(package)
    for name,expected in freeze['code_files'].items():
        if digest((ROOT/name).read_bytes())!=expected:
            raise ValueError('Frozen code changed: '+name)
    for name,expected in freeze['runtime_files'].items():
        if digest((root/name).read_bytes())!=expected:
            raise ValueError('Frozen runtime input changed: '+name)
    if subprocess.run(['git','merge-base','--is-ancestor',freeze['commit'],'HEAD'],cwd=ROOT).returncode:
        raise ValueError('Committed execution source is no longer in history')
    current=json.loads(docker('inspect',*[c['id'] for c in freeze['containers'].values()]))
    for observed,expected in zip(current,freeze['containers'].values()):
        if not observed['State']['Running'] or observed['Image']!=expected['image']:
            raise ValueError('Frozen container/image is no longer running')
        if not mounts_equal(observed['Mounts'],expected['mounts']):
            raise ValueError('Frozen container mounts changed')
    return freeze,package


def check_library(root):
    expected={b['document_id']:b['revision'] for b in load(root/'bindings.json') if b['state']=='committed'}
    library=get(API,'/v1/ui/library')
    if {d['document_id']:d['revision'] for d in library['documents']}!=expected:
        raise ValueError('Library revisions differ from freeze')


def rpc_attempt(destination,model,operation,value):
    """Direct RPC attempts are create-only: resume never replays uncertainty."""
    if (destination/'finished.json').exists():
        return load(destination/'finished.json')
    if destination.exists():
        save(destination/'finished.json',{'state':'interrupted_uncertain','no_retry':True})
        return load(destination/'finished.json')
    destination.mkdir(parents=True)
    raw_save(destination/'input.json',encoded(value))
    # Answer preparation and generation use the production interactive lane.
    # The supervisor requires the lease and every operation priority to agree.
    lease={'model':model,'token':str(uuid.uuid4()),'owner':'t39-'+uuid.uuid4().hex,'priority':'interactive'}
    save(destination/'started.json',{'model':model,'operation':operation,'started_unix':time.time(),
                                    'input_sha256':digest(encoded(value)),'lease':lease})
    calls=[];acquired=False;start=time.monotonic();state='failed';error=None
    def call(name,path,payload,timeout):
        body=rpc_encoded(payload)
        raw_save(destination/(name+'.request.json'),body)
        began=time.monotonic()
        try:
            status,raw=wire(PROCESSOR,path,body,timeout)
        except Exception as exc:
            calls.append({'operation':name,'state':'failed_or_uncertain',
                          'elapsed_ms':(time.monotonic()-began)*1000,'error':str(exc)})
            save(destination/(name+'.error.json'),calls[-1])
            raise
        raw_save(destination/(name+'.response.json'),raw)
        calls.append({'operation':name,'status':status,'elapsed_ms':(time.monotonic()-began)*1000})
        result=json.loads(raw)
        if status!=200 or 'error' in result:
            raise RuntimeError(f'{name}: HTTP {status}: {str(result)[:400]}')
        return result
    try:
        identity=call('acquire','/generation/acquire',lease,300)
        acquired=True
        if identity.get('model')!=model or identity.get('token')!=lease['token']:
            raise ValueError('Wrong lease/model identity')
        if operation=='answer':
            count=call('tokens','/rpc/interactive',{'op':'answer_tokens','input':value,'lease':lease},450)['result']
            if type(count) is not int or not 0<=count<=3328:
                raise ValueError('Oracle exceeds unchanged 3328-token budget')
        call(operation,'/rpc/interactive',{'op':operation,'input':value,'lease':lease},750)
        state='captured'
    except Exception as exc:
        error=f'{type(exc).__name__}: {exc}'
    finally:
        # Reconcile our token even if the acquire response was lost. The
        # supervisor owns backend reconciliation; this does not reset it.
        if (destination/'acquire.request.json').exists():
            try:call('release','/generation/release',{'token':lease['token']},300)
            except Exception as exc:
                state='failed_or_uncertain';error=(error or '')+'; release: '+str(exc)
        result={'state':state,'error':error,'calls':calls,'wall_ms':(time.monotonic()-start)*1000,'no_retry':True}
        save(destination/'finished.json',result)
    return result


def controls(root,model):
    _,package=verified(root)
    warm=root/'controls'/model/'synthetic-warmup'
    if rpc_attempt(warm,model,'closed_book',{'question':'What is the sum of one and one?'})['state']!='captured':
        raise RuntimeError('Synthetic warmup failed; measured controls not started')
    for split in SPLITS:
        for i,case in enumerate(load(package/split/'controls.json')):
            result=rpc_attempt(root/'controls'/model/split/case['case_id'],model,'closed_book',
                               {'question':case['question']})
            print(json.dumps({'phase':'controls','model':model,'split':split,'completed':i+1,
                              'state':result['state']}),flush=True)


def submit(root,case,split,arm,representation='v2'):
    freeze,package=verified(root)
    identity='t39-'+digest(encoded([digest((root/'execution-freeze.json').read_bytes()),
                                   split,case['case_id'],arm,representation]))[:56]
    dest=root/'answers'/split/representation/arm/case['case_id']
    if (dest/'finished.json').exists():return load(dest/'finished.json')
    dest.mkdir(parents=True,exist_ok=True)
    ctx=context(package,root,split,case['document'],representation)
    binding=ctx['binding']
    if binding['state']!='committed':
        result={'state':'ingestion_failed','included_in_denominator':True}
        save(dest/'finished.json',result);return result
    payload={'request_id':identity,'mode':'nuextract','kind':'ui','payload':{
        'question':case['question'],'history':[],'document_ids':[binding['document_id']],
        'prose':False,'options':OPTIONS[arm]}}
    resumed=(dest/'started.json').exists();start=time.monotonic()
    if not resumed:
        save(dest/'started.json',{'request':payload,'started_unix':time.time()})
        try:
            status,raw=wire(API,'/v1/answer-jobs',encoded(payload))
            raw_save(dest/'submission.raw.json',raw)
            if status!=202:
                result={'state':'submission_failed','status':status,'wall_ms':(time.monotonic()-start)*1000}
                save(dest/'finished.json',result);return result
        except (OSError,TimeoutError):pass
    while not (dest/'job.json').exists():
        status,raw=wire(API,'/v1/answer-jobs/'+identity)
        if status!=200:raise RuntimeError('Uncertain durable submission; no resubmission: '+identity)
        job=json.loads(raw)
        if job['request_id']!=identity or job['mode']!='nuextract':raise ValueError('Job identity mismatch')
        if job['terminal']:
            raw_save(dest/'job.json',raw);break
        if time.monotonic()-start>1800:raise TimeoutError('Observer expired; durable work retained')
        time.sleep(.5)
    job=load(dest/'job.json')
    result={'state':'captured','wall_ms':None if resumed else (time.monotonic()-start)*1000,
            'job_total_ms':job.get('total_ms'),'resumed':resumed,'included_in_denominator':True}
    try:
        save(dest/'projection.json',project((dest/'job.json').read_bytes(),case['question'],ctx))
    except Exception as exc:
        # Captured output is retained; a projection defect never becomes a success.
        save(dest/'projection-error.json',{'error':str(exc)})
    save(dest/'finished.json',result)
    # Archive is fsynced before freeing the isolated operational queue quota.
    status,raw=wire(API,'/v1/answer-jobs/'+identity+'/clear',encoded({}))
    raw_save(dest/'clear.raw.json',raw)
    if status!=200:raise RuntimeError('Terminal record was not cleared; inspect quota before continuing')
    return result


def strategies(root,split,arms,representation='v2'):
    _,package=verified(root);check_library(root)
    cases=load(package/split/'questions.json')
    if representation=='v1':
        names={d['document'] for d in load(package/split/'documents.json') if d['format']=='json'}
        cases=[c for c in cases if c['document'] in names]
    if split=='exposed_candidates' and arms!=['five']:
        decision=load(root/'selection.json')
        if arms!=['five',decision.get('candidate')]:raise ValueError('Unfrozen exposed candidate strategy')
    for i,(case,arm) in enumerate(schedule(cases,arms)):
        result=submit(root,case,split,arm,representation)
        print(json.dumps({'phase':'strategy','split':split,'representation':representation,
                          'arm':arm,'completed':i+1,'state':result['state']}),flush=True)


def observed(ctx,evidence):
    b,d=ctx['binding'],ctx['descriptor']
    if d['format']=='json':
        return table_coordinates(ctx['original'],ctx['annotation'],ctx['representation'],evidence,
                                 b['document_id'],b['revision'])['visible_coordinates']
    return prose_coordinates(ctx['text'],d['review_text_sha256'],d['original_sha256'],
        evidence,ctx['snapshot'],b['document_id'],b['revision'])['proofs']


def range_covered(required,refs):
    if 'pointer' in required:return False
    intervals=sorted((r['utf8_start'],r['utf8_end']) for r in refs
                     if r.get('document_sha256')==required['document_sha256'])
    end=required['utf8_start']
    for a,b in intervals:
        if a<=end:end=max(end,b)
    return end>=required['utf8_end']


def select_evidence(case,evidence,coordinates,proof):
    if case['tier']=='stress_adjudication':return None,'stress_oracle_not_defined'
    if case['expected']!='supported':return evidence,None
    if case['format']=='json':
        groups=[p['required'] for p in proof['proof_sets']]
        cover=lambda required,refs:all(any(covers(r,s) for s in refs) for r in required)
    else:
        groups=[sum((role['proof_sets'][0] for role in case['roles']),[])]
        cover=lambda required,refs:all(range_covered(r,refs) for r in required)
    if not groups:return None,'missing_gold_evidence_definition'
    required=groups[0]
    # Search source-order combinations exactly; bounded work fails explicitly.
    attempts=0
    for n in range(1,min(len(evidence),8)+1):
        for indices in itertools.combinations(range(len(evidence)),n):
            attempts+=1
            if attempts>100000:return None,'oracle_selection_search_bound'
            refs=[r for i in indices for r in coordinates[i]]
            selected=[evidence[i] for i in indices]
            value_present=True
            if case['format']=='json':
                value=proof['proof_sets'][0]['value']
                index=value.get('row',value.get('paragraph'))
                value_present=any(s['locator'].get('Json',{}).get('pointer')==f'/records/{index}'
                                  for e in selected for s in e['sources'])
            if value_present and cover(required,refs):return selected,None
    return None,'gold_evidence_not_reconstructable'


def prepare_oracles(root,package):
    """Run before inference; never reads outputs, just frozen source/proof data."""
    proofs={p['case_id']:p for p in load(package/'development/table-proofs.json')['cases']}
    destination=root/'oracle-inputs';destination.mkdir()
    for case in load(package/'development/gold.json')['cases']:
        ctx=context(package,root,'development',case['document'])
        b=ctx['binding'];entry={'case_id':case['case_id'],'question':case['question'],'history':[]}
        if b['state']!='committed':entry.update(state='unavailable',reason='ingestion_failed')
        else:
            folder=root/'ingestion'/b['document_id'];evidence=load(folder/'evidence.json')
            coordinates=[observed(ctx,e) for e in evidence]
            selected,reason=select_evidence(case,evidence,coordinates,proofs.get(case['case_id'],{}))
            if selected is None:entry.update(state='unavailable',reason=reason)
            else:
                entry.update(state='ready',evidence=selected,constrain_pointers=case['format']=='json')
                if case['expected']=='supported':
                    names=next((m for m in case['allowed_field_mappings'] if len(m)==len(case['roles'])),None)
                    if names is None:raise ValueError('No complete neutral oracle field mapping')
                    entry['gold_fields']={}
                    for name,role_id in names.items():
                        role=next(r for r in case['roles'] if r['id']==role_id)
                        if case['format']=='json':
                            loc=proofs[case['case_id']]['proof_sets'][0]['value']
                            location=('original table row '+str(loc['row'])+', column '+str(loc['col'])
                                      if 'row' in loc else 'original paragraph '+str(loc['paragraph']))
                        else:
                            location='; '.join('reviewed-text UTF-8 bytes '+str(p['utf8_start'])+'..'+str(p['utf8_end'])
                                               for p in role['proof_sets'][0])
                        description='Requested fact '+role_id+'. Source location: '+location+'.'
                        if len(description.encode('utf8'))>256:raise ValueError('Oracle location definition exceeds normal field bound')
                        entry['gold_fields'][name]={'kind':'string','nullable':False,
                                                   'description':description,'pointer':None}
                else:entry['gold_fields']=None
        save(destination/(case['case_id']+'.json'),entry)


def automatic_fields(root,case):
    path=root/'answers/development/v2/five'/case['case_id']/'job.json'
    if not path.exists():return None
    job=load(path);view=job.get('result') or {}
    if view.get('raw_report'):
        report=json.loads(view['raw_report'])
        if report.get('request',{}).get('fields'):return report['request']['fields']
    # Failed downstream requests may still have a captured plan in their audit.
    for attempt in job.get('attempts',[]):
        for operation in attempt.get('operations',[]):
            if operation.get('operation')!='plan_fields' or not operation.get('response_text'):continue
            plan=json.loads(operation['response_text']).get('plan',{})
            if plan.get('status')=='ready':
                return {f['name']:{k:f.get(k) for k in ('kind','nullable','description','pointer')}
                        for f in plan['fields']}
    return None


def oracles(root,model):
    _,package=verified(root)
    if rpc_attempt(root/'oracles'/model/'synthetic-warmup',model,'closed_book',
                   {'question':'What is the sum of one and one?'})['state']!='captured':
        raise RuntimeError('Oracle model warmup failed')
    for i,case in enumerate(load(package/'development/gold.json')['cases']):
        entry=load(root/'oracle-inputs'/(case['case_id']+'.json'))
        base=root/'oracles'/model/case['case_id']
        fields=automatic_fields(root,case)
        for variant,definition in [('automatic_fields',fields),('gold_fields',entry.get('gold_fields'))]:
            dest=base/variant
            if (dest/'finished.json').exists():continue
            reason=entry.get('reason')
            if definition is None:reason=reason or ('planning_unavailable' if variant=='automatic_fields' else 'gold_fields_not_applicable')
            if variant=='gold_fields' and definition is not None and definition==fields:reason='identical_to_automatic_fields'
            if reason:
                dest.mkdir(parents=True,exist_ok=True);save(dest/'finished.json',{'state':'unavailable','reason':reason})
                continue
            value={k:entry[k] for k in ('question','history','evidence','constrain_pointers')}
            value['fields']=definition
            rpc_attempt(dest,model,'answer',value)
        print(json.dumps({'phase':'oracle','model':model,'completed':i+1}),flush=True)


def freeze(root,package):
    verify_package(package)
    code_paths=[]
    for folder in ('src','examples','model_worker','model_assets','deployment','processor','evals/measurement'):
        code_paths.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and
                          '__pycache__' not in p.parts and p.suffix in ('.rs','.py','.json','.md','.txt'))
    code_paths.extend(ROOT/p for p in ('Cargo.toml','Cargo.lock'))
    images=load(root/'setup.json')['images'];containers={}
    for kind,service in [('api','vectornext'),('processor','processor'),('llm','llm')]:
        c=json.loads(docker('inspect',f'vectornext-t39-internal-{service}-1'))[0]
        if c['Image']!=images[kind] or not c['State']['Running']:raise ValueError('Runtime differs from setup')
        if c['Config']['Labels'].get('vectornext.measurement')!='T39':raise ValueError('Not isolated runtime')
        for m in c['Mounts']:
            if m['Type']=='volume' and not m['Name'].startswith('vectornext-t39-internal-'):
                raise ValueError('Non-evaluation volume mounted')
        containers[kind]={'id':c['Id'],'image':c['Image'],'mounts':c['Mounts'],'command':c['Config']['Cmd'],
                          'entrypoint':c['Config']['Entrypoint'],'env':c['Config']['Env']}
    # Source must be committed; reports and private outputs may remain untracked.
    tracked=subprocess.check_output(['git','diff','HEAD','--name-only'],cwd=ROOT,text=True).splitlines()
    names={p.relative_to(ROOT).as_posix() for p in code_paths}
    if names.intersection(tracked):raise ValueError('Commit evaluation source before execution freeze')
    committed=set(subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines())
    if names-committed:raise ValueError('Uncommitted evaluation source files')
    members=[root/'bindings.json',root/'compose.json',*[p for p in (root/'ingestion').rglob('*.json')],
             *[p for p in (root/'oracle-inputs').rglob('*.json')],*[p for p in (root/'tools').iterdir() if p.is_file()]]
    value={'version':'internal-execution-v1.8','classification':'internal_exposed_pilot',
           'independent_review':False,'blind_holdout':False,'default_model':'nuextract','default_strategy':'five',
           'package':str(package.resolve()),'package_sha256':PACKAGE_SHA,
           'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
           'code_files':{p.relative_to(ROOT).as_posix():digest(p.read_bytes()) for p in sorted(code_paths)},
           'runtime_files':{p.relative_to(root).as_posix():digest(p.read_bytes()) for p in sorted(members)},
           'containers':containers,'processor_health':get(PROCESSOR,'/health'),
           'created_unix':time.time(),'no_retries':True}
    save(root/'execution-freeze.json',value)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation',choices=['prepare-oracles','freeze','controls','strategies','oracles'])
    p.add_argument('--root',type=Path,required=True);p.add_argument('--package',type=Path)
    p.add_argument('--model',choices=['nuextract','gemma'],default='nuextract')
    p.add_argument('--split',choices=SPLITS,default='development')
    p.add_argument('--arms',nargs='+',choices=list(OPTIONS),default=['five','two','facet'])
    p.add_argument('--representation',choices=['v1','v2'],default='v2')
    a=p.parse_args();a.root=a.root.resolve()
    if a.operation=='prepare-oracles':prepare_oracles(a.root,a.package.resolve())
    elif a.operation=='freeze':freeze(a.root,a.package.resolve())
    elif a.operation=='controls':controls(a.root,a.model)
    elif a.operation=='strategies':strategies(a.root,a.split,a.arms,a.representation)
    elif a.operation=='oracles':oracles(a.root,a.model)


if __name__=='__main__':main()
