"""Offline, paired CPU embedding-space comparison; no historical runner mutation."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
import zipfile

from evals.evidence.validate import validate as validate_nist, digest
from evals.selection.validate import validate as validate_nasa
from evals.evidence.score import score_file

PROFILES = ['minilm', 'bge-small-en-v1.5']


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True, encoding='utf-8').strip()


def write(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--image', default='vectornext-embedding:t31')
    args = parser.parse_args()
    if not args.run or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in args.run):
        raise ValueError('fresh simple run name required')
    root = Path.cwd(); output = root/'data/t31'/args.run
    output.mkdir(exist_ok=False)
    counts = {'nist': validate_nist(), 'nasa': validate_nasa()}
    suites = {'nist': Path('evals/evidence'), 'nasa': Path('evals/selection')}
    paths = set(Path('src').rglob('*.rs')) | set(Path('model_worker').glob('*.py')) | set(Path('model_worker').glob('*.json'))
    paths |= {p for p in Path('experiments/t31').rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    paths |= {Path(p) for p in ['Cargo.toml','Cargo.lock','examples/evidence_retrieval.rs',
        'experiments/t02/encoders.py','experiments/t02/fetch_models.py','experiments/t02/models.lock.json',
        'experiments/t02/models.26b.lock.json','experiments/t27/models.12b.lock.json']}
    for suite, source in suites.items():
        public = output/suite/'input'; public.mkdir(parents=True)
        for name in ('sources.json','requests.json'): shutil.copyfile(source/name, public/name)
        shutil.copytree(source/'fixtures', public/'fixtures')
        paths |= {p for p in source.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    volumes = {suite: {model: {kind: f'vectornext-t31-{args.run}-{suite}-{model}-{kind}'
        for kind in ('data','ingest','query')} for model in PROFILES} for suite in suites}
    names = {v for models in volumes.values() for kinds in models.values() for v in kinds.values()}
    if names.intersection(docker('volume','ls','--format','{{.Name}}').splitlines()):
        raise ValueError('existing volumes; preserve previous attempt')
    manifest = {'created':datetime.now(timezone.utc).isoformat(), 'inputs':counts,
        'image':docker('image','inspect',args.image,'--format','{{.Id}}'),
        'processor_base':docker('image','inspect','vectornext-app-processor:t30','--format','{{.Id}}'),
        'commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'files':{p.as_posix():digest(p) for p in sorted(paths)}, 'volumes':volumes,
        'requests':192, 'network':'none', 'cpus':2, 'memory':'4g', 'gpu':False,
        'target_tokens':180, 'retrieval':'baseline 30/20/5; no expansion/facets/generation', 'holdout_run':False}
    write(output/'execution-freeze.json',manifest)
    with zipfile.ZipFile(output/'source.zip','x',zipfile.ZIP_DEFLATED) as archive:
        for path in paths: archive.write(path,path.as_posix())
    for volume in sorted(names): docker('volume','create',volume)
    scores, ingestion = {}, {}
    def execute(suite, model, phase, sequence):
        if any(digest(p)!=h for p,h in manifest['files'].items()): raise ValueError('execution inputs changed')
        validate_nist(); validate_nasa()
        folder=output/suite/model; folder.mkdir(exist_ok=True)
        filename=f'{sequence:02}-{phase}.jsonl'; public=output/suite/'input'; vv=volumes[suite][model]
        mode='ingest' if phase=='ingest' else 'baseline'
        command=['docker','run','--rm','--network','none','--cpus','2','--memory','4g',
            '--cap-drop','ALL','--security-opt','no-new-privileges:true',
            '-e',f'VECTORNEXT_EMBEDDING_PROFILE={model}',
            '--mount',f'type=volume,source={vv["data"]},target=/data',
            '--mount',f'type=volume,source={vv["ingest" if phase=="ingest" else "query"]},target=/cache',
            '--mount',f'type=bind,source={root/"models"},target=/models,readonly',
            '--mount',f'type=bind,source={public},target=/input,readonly',
            '--mount',f'type=bind,source={folder},target=/reports',manifest['image'],
            mode,'/data/db','/input',f'/reports/{filename}','/opt/model-env/bin/python']
        print(suite,model,phase,flush=True)
        started=time.monotonic()
        with (folder/f'{sequence:02}-{phase}.log').open('x',encoding='utf-8') as log:
            result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
        write(folder/f'{sequence:02}-{phase}.process.json',{'command':command,'exit_code':result.returncode,'wall_seconds':time.monotonic()-started})
        if result.returncode: raise RuntimeError('process failed; preserve attempt: '+str(folder/filename))
        rows=[json.loads(line) for line in (folder/filename).read_text(encoding='utf-8').splitlines()]
        finish=next(r for r in rows if r.get('kind')=='finish')
        if phase=='ingest':
            ingestion[suite+'/'+model]={'documents':len(finish['documents']),
                'chunks':sum(len(d['chunks']) for d in finish['documents']),
                'elapsed_ms':sum(r.get('elapsed_ms',0) for r in rows if r.get('kind')=='ingestion'),
                'records':[r for r in rows if r.get('kind')=='ingestion'],
                'profile':next(r for r in rows if r.get('kind')=='startup')}
        else:
            scores[suite+'/'+model+'/'+phase]=score_file(folder/filename,json.loads((suites[suite]/'gold.json').read_bytes()))
    for suite_index,suite in enumerate(suites):
        order=PROFILES if suite_index==0 else list(reversed(PROFILES))
        for model in order: execute(suite,model,'ingest',0)
        for model in order: execute(suite,model,'cold',1)
        for model in reversed(order): execute(suite,model,'warm',2)
    if any(digest(p)!=h for p,h in manifest['files'].items()): raise ValueError('execution identity changed')
    changes=[]
    for suite in suites:
        for phase in ('cold','warm'):
            a=scores[suite+'/minilm/'+phase]; b=scores[suite+'/bge-small-en-v1.5/'+phase]
            pairs=list(zip(a['cases'],b['cases']))
            if any(x['id']!=y['id'] for x,y in pairs): raise ValueError('case identity mismatch')
            changes.append({'suite':suite,'pass':phase,
                'lost_complete':[x['id'] for x,y in pairs if x['primary']['complete'] and not y['primary']['complete']],
                'gained_complete':[x['id'] for x,y in pairs if not x['primary']['complete'] and y['primary']['complete']]})
    write(output/'summary.json',{'requests':sum(s['requests'] for s in scores.values()),'scores':scores,
        'ingestion':ingestion,'changes':changes,'no_final_coverage_loss':not any(x['lost_complete'] for x in changes),
        'production':'MiniLM unchanged; no migration/activation', 'finished':datetime.now(timezone.utc).isoformat()})
    print(json.dumps({'requests':192,'changes':changes}),flush=True)


if __name__ == '__main__': main()
