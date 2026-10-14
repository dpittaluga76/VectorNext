"""Freeze/verify T11 inputs explicitly. Validation never fetches or authors labels."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
BLOCKS=[('five-cold',5),('two-cold',2),('two-warm',2),('five-warm',5)]


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def public_inputs(dataset,requests):
    cases={c['id']:c for c in dataset['cases']}
    if len(cases)!=len(dataset['cases']) or cases.keys()!=requests.keys():
        raise ValueError('request/case IDs must be unique and identical')
    for id,c in cases.items():
        r=requests[id]
        if c['split']!='comparison': raise ValueError('only comparison cases are permitted')
        if set(r)-{'question','fields','history','template'}: raise ValueError('private request attributes')
        if r['question']!=c['question']: raise ValueError('question mismatch')
        if any(set(f)-{'kind','nullable'} for f in r['fields'].values()): raise ValueError('field contains a value or source')
        if r.get('history',[])!=[{'role':h['role'],'text':h['content']} for h in c.get('history',[])]: raise ValueError('history mismatch')
        if r.get('template')!=c.get('presentation',{}).get('template'): raise ValueError('template mismatch')
    return cases


def paths():
    fixed=['docs/t11-protocol.md','docs/t11-protocol-amendment-01.md','compose.app.yaml','compose.independent.yaml',
        'evals/score.py','evals/run.py','evals/validate.py','evals/dataset.json',
        'Cargo.toml','Cargo.lock','tests/ingestion.rs','docker/app.Dockerfile','experiments/t02/models.lock.json',
        'experiments/t02/models.26b.lock.json','processor/models.lock.json']
    files=[ROOT/p for p in fixed]
    files += [HERE/p for p in ['dataset.json','dataset.schema.json','requests.json','sources.json']]
    files += list((HERE/'fixtures').glob('*'))
    # Freeze execution and model code, not post-run summaries/review or presentation docs.
    files += [HERE/p for p in ['freeze.py','run.py','acquire.py','build_dataset.py']]
    for directory,pattern in [('src','*.rs'),('model_worker','*.py'),('processor','*.py'),('deployment','*.py')]:
        files += list((ROOT/directory).rglob(pattern))
    return sorted(set(files))


def verify(root=ROOT,manifest=None):
    manifest=manifest or json.loads((root/'evals/independent/freeze.json').read_text(encoding='utf-8'))
    for p,h in manifest['files'].items():
        if digest(root/p)!=h: raise ValueError('frozen input changed: '+p)
    return manifest


def main():
    p=argparse.ArgumentParser();p.add_argument('--create',action='store_true');a=p.parse_args()
    target=HERE/'freeze.json'
    if a.create:
        if target.exists(): raise ValueError('freeze already exists; preserve the original comparison')
        from evals.validate import validate_dataset
        validate_dataset(HERE/'dataset.json',HERE/'dataset.schema.json')
        public_inputs(json.loads((HERE/'dataset.json').read_text(encoding='utf-8')),json.loads((HERE/'requests.json').read_text(encoding='utf-8')))
        value={'version':1,'frozen_utc':datetime.now(timezone.utc).isoformat(),
            'blocks':[{'name':n,'primary_limit':k} for n,k in BLOCKS],
            'options':{'candidates':30,'rerank_limit':20,'rerank':True},
            'files':{p.relative_to(ROOT).as_posix():digest(p) for p in paths()}}
        target.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    print('Verified',len(verify()['files']),'frozen inputs')


if __name__=='__main__': main()
