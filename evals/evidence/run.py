"""Explicit isolated Docker experiment. No services, downloads or historical data."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from .validate import digest, validate
from .score import score_file


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True, encoding='utf-8').strip()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run', required=True, help='new simple lowercase run name')
    parser.add_argument('--image',default='vectornext-evidence:t23')
    args=parser.parse_args()
    assert args.run and all(c in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in args.run)
    counts=validate()
    root=Path.cwd()
    output=root/'data/t23'/args.run
    output.mkdir(exist_ok=False)
    public=output/'input'
    public.mkdir()
    source=Path('evals/evidence')
    for name in ('sources.json','requests.json'):
        shutil.copyfile(source/name,public/name)
    shutil.copytree(source/'fixtures',public/'fixtures')
    # Labels and scorer are absent from the inference mount. Hashes can include them.
    paths=set(Path('src').rglob('*.rs'))|set(Path('model_worker').glob('*.py'))
    paths|=set(source.glob('*.py'))
    paths|={Path(p) for p in ['Cargo.toml','Cargo.lock','examples/evidence_retrieval.rs',
        'docker/evidence-test.Dockerfile','experiments/t02/encoders.py','experiments/t02/fetch_models.py',
        'experiments/t02/models.lock.json','experiments/t02/models.26b.lock.json',
        'evals/evidence/input-freeze.json']}
    paths|={Path(p) for p in json.loads((source/'input-freeze.json').read_text())['files']}
    volumes={name:f'vectornext-t23-{args.run}-{name}' for name in ('data','ingest','baseline','expanded')}
    existing=set(docker('volume','ls','--format','{{.Name}}').splitlines())
    assert not existing.intersection(volumes.values()),'refusing to reuse existing experiment volumes'
    manifest={'created_utc':datetime.now(timezone.utc).isoformat(),'inputs':counts,
        'image':docker('image','inspect',args.image,'--format','{{.Id}}'),
        'processor_base':docker('image','inspect','vectornext-app-processor:t18','--format','{{.Id}}'),
        'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'files':{p.as_posix():digest(p) for p in sorted(paths)},'volumes':volumes,
        'runtime':{'network':'none','cpus':2,'memory':'4g','gpu':False,'arms':['baseline','expanded','expanded','baseline']}}
    (output/'execution-freeze.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
    for volume in volumes.values():docker('volume','create',volume)
    for sequence,arm in enumerate(['ingest','baseline','expanded','expanded','baseline']):
        validate()
        assert all(digest(p)==h for p,h in manifest['files'].items()),'execution inputs changed'
        filename=f'{sequence:02}-{arm}.jsonl'
        command=['docker','run','--rm','--network','none','--cpus','2','--memory','4g',
            '--cap-drop','ALL','--security-opt','no-new-privileges:true',
            '--mount',f'type=volume,source={volumes["data"]},target=/data',
            '--mount',f'type=volume,source={volumes[arm]},target=/cache',
            '--mount',f'type=bind,source={root/"models"},target=/models,readonly',
            '--mount',f'type=bind,source={public},target=/input,readonly',
            '--mount',f'type=bind,source={output},target=/reports',manifest['image'],
            arm,'/data/db','/input',f'/reports/{filename}','/opt/model-env/bin/python']
        print(f'{sequence}: {arm}',flush=True)
        with (output/f'{sequence:02}-{arm}.log').open('x',encoding='utf-8') as log:
            result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
        (output/f'{sequence:02}-process.json').write_text(json.dumps({'command':command,'exit_code':result.returncode}),encoding='utf-8')
        if result.returncode:raise RuntimeError(f'{arm} process failed; capture retained in {output}')
    gold=json.loads((source/'gold.json').read_text(encoding='utf-8'))
    summary=[score_file(output/f'{i:02}-{arm}.jsonl',gold) for i,arm in enumerate(manifest['runtime']['arms'],1)]
    (output/'scores.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps([{k:r[k] for k in ('capture','errors','stages','latency')} for r in summary],indent=2))


if __name__=='__main__':main()
