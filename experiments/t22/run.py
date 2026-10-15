"""Explicit isolated paired runs; refuses existing output, never regenerates inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(output):
    root = Path.cwd()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    inputs = root / 'data/t20/20261015-fixed-v3'
    images = {variant: subprocess.check_output(['docker', 'image', 'inspect', '-f', '{{.Id}}', name], text=True).strip()
              for variant, name in [('baseline', 'vectornext-filter:t22-baseline-final'), ('indexed', 'vectornext-filter:t22-indexed')]}
    paths = sorted(Path('src').rglob('*.rs')) + [Path(p) for p in ['examples/filter_profile.rs', 'docs/t22-protocol.md', 'experiments/t22/run.py', 'docker/filter-profile.Dockerfile']]
    manifest = {'images': images, 'sources': {p.as_posix(): digest(p) for p in paths},
                'inputs': {str(p.relative_to(root)): digest(p) for p in [inputs/'manifest.json',inputs/'400/queries.json',inputs/'1600/queries.json']},
                'order': ['baseline', 'indexed', 'indexed', 'baseline'], 'cpus': 2, 'memory': '4g', 'passes': 3}
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2))
    for size in (400,1600):
        for block,variant in enumerate(manifest['order']):
            name=f'{size}-{block}-{variant}.json'
            command=['docker','run','--rm','--network','none','--cpus','2','--memory','4g',
                     '-v','vectornext-t22-data:/work','-v',f'{inputs}:/inputs:ro','-v',f'{output}:/reports',
                     images[variant],f'/work/{size}','/inputs',str(size),f'/reports/{name}','3']
            subprocess.run(command,check=True)
            assert all(digest(root/p)==h for p,h in manifest['sources'].items()), 'source changed during run'
            assert all(digest(root/p)==h for p,h in manifest['inputs'].items()), 'input changed during run'
    summarize(output)


def summarize(output):
    manifest=json.loads((output/'manifest.json').read_text())
    result={'images':manifest['images'],'response_checks':0,'groups':[],'builds':[],'capture_hashes':{}}
    references={}
    groups={}
    for size in (400,1600):
        for block,variant in enumerate(manifest['order']):
            path=output/f'{size}-{block}-{variant}.json'
            r=json.loads(path.read_text())
            assert r['size']==size and r['passes']==3 and len(r['measurements'])==528
            result['capture_hashes'][path.name]=digest(path)
            result['builds'].append({'size':size,'variant':variant,'block':block,'index_build_ms':r['index_build_ms'],'memory':r['memory']})
            seen=set()
            for m in r['measurements']:
                key=(size,m['trace'],m['case'],m['query'])
                observation=(m['pass'],m['trace'],m['case'],m['query'])
                assert observation not in seen
                seen.add(observation)
                assert 0<=m['pass']<3 and 0<=m['query']<8 and m['trace'] in (True,False)
                if key in references:
                    assert references[key]==m['response_sha256'],f'response mismatch {key}'
                else:
                    references[key]=m['response_sha256']
                result['response_checks']+=1
                group=(size,variant,m['trace'],m['case'],'warm' if m['pass'] else 'first')
                groups.setdefault(group,[]).append(m)
    for (size,variant,trace,case,phase),rows in sorted(groups.items()):
        values=sorted(m['elapsed_ms'] for m in rows)
        result['groups'].append({'size':size,'variant':variant,'trace':trace,'case':case,'phase':phase,'n':len(rows),
                                'p50_ms':statistics.median(values),'p95_ms':values[int(.95*(len(values)-1))],
                                'filter_p50_ms':statistics.median(m['stages']['search_filter_tokenize'] for m in rows)})
    assert result['response_checks']==4224
    with (output/'summary.json').open('x') as stream:json.dump(result,stream,indent=2)
    print('Complete: 4224 identical response checks; frozen captures retained.')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['run','summarize']);parser.add_argument('output',type=Path)
    args=parser.parse_args()
    if args.action=='run':run(args.output)
    else:summarize(args.output)
