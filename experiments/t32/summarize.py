"""Reporting-only aggregation of retained captures; never invokes inference."""
import argparse
import hashlib
import json
from pathlib import Path
from evals.evidence.score import distribution
from .run import ARMS, write


def mib(text):
    text=text.split(' / ')[0]
    for suffix,multiplier in [('GiB',1024),('MiB',1),('KiB',1/1024),('B',1/1024**2)]:
        if text.endswith(suffix):return float(text[:-len(suffix)])*multiplier
    raise ValueError('unknown Docker memory unit: '+text)


def summarize(root):
    root=Path(root);result=json.loads((root/'summary.json').read_bytes())
    result['run']=root.as_posix()
    freeze=json.loads((root/'execution-freeze.json').read_bytes())
    result['identity']={'images':freeze['images'],'generator_image':freeze['generator']['Image'],
        'generator_entrypoint':freeze['generator']['Config']['Entrypoint'],
        'generator_environment':[v for v in freeze['generator']['Config']['Env'] if v.startswith('VECTORNEXT_')],
        'commit':freeze['commit'],'input_sha256':hashlib.sha256(Path('experiments/t32/input-freeze.json').read_bytes()).hexdigest(),
        'freeze_sha256':hashlib.sha256((root/'execution-freeze.json').read_bytes()).hexdigest(),
        'archive_sha256':hashlib.sha256((root/'source.zip').read_bytes()).hexdigest()}
    result['ingestion']={}
    for embedding in ('minilm','nomic-v1.5'):
        rows=json.loads((root/embedding/'ingestion.json').read_bytes())
        docs=json.loads((root/embedding/'documents.json').read_bytes())
        result['ingestion'][embedding]={'admitted':len(docs),'attempted':len(rows),
            'seconds':sum(r['seconds'] for r in rows),'chunks':sum(len(d['chunks']) for d in docs.values()),
            'chunks_per_document':{name:len(d['chunks']) for name,d in docs.items()},
            'startup_seconds':json.loads((root/embedding/'startup.json').read_bytes())['seconds'],
            'snapshot_sha256':hashlib.sha256((root/embedding/'documents.json').read_bytes()).hexdigest()}
    baseline=result['arms']['minilm-minilm']['cases']
    for name,embedding,reranker in ARMS:
        arm=result['arms'][name];folder=root/name
        # Reporting exception only: retain the frozen score and gold verbatim.
        correction=json.loads((folder/'pdf_correction.response.json').read_bytes())
        captured=next(r for r in arm['cases'] if r['case']=='pdf_correction')
        answer=correction.get('answer',{});proof=answer.get('fields',{}).get('interval_days',{})
        docs=json.loads((root/embedding/'documents.json').read_bytes())
        doc=docs.get('cedar-audit',{})
        valid_alternative=(captured['http_status']==200 and answer.get('status')=='supported'
            and proof.get('value')==45 and correction.get('validation',{}).get('mechanical_support')=='passed'
            and doc.get('original',{}).get('sha256')=='d718f78196f0b4372e6b0e584f630e960194357c74af2f4d28bc00519d3427cd'
            and any(e['id']==proof.get('evidence_id') and e['key']['document_id']=='cedar-audit'
                    and e['key']['revision']==doc.get('revision')
                    and 'The final July 2031 interval for the Cedar type B manifold is 45 days.' in e['text']
                    for e in correction.get('evidence',[])))
        arm['reviewed_correct']=arm['correct']+int(valid_alternative and not captured['score']['correct'])
        arm['reviewed_support_exception']={'case':'pdf_correction','applies':valid_alternative,
            'review':'docs/reports/t32-source-review.md'}
        samples=[json.loads(line) for line in (folder/'resources.jsonl').read_text().splitlines()]
        if any(s['exit'] for s in samples):raise ValueError('resource sampling failure')
        arm['resources']={}
        for service in ('api','t32-processor'):
            rows=[r for s in samples for r in s['rows'] if r['Name'].endswith('-'+service+'-1')]
            arm['resources'][service]={'samples':len(rows),'peak_memory_mib':max(mib(r['MemUsage']) for r in rows),
                'peak_cpu_percent':max(float(r['CPUPerc'].rstrip('%')) for r in rows)}
        pairs=[(a,b) for a,b in zip(baseline,arm['cases']) if a['score']['correct'] and b['score']['correct']]
        arm['jointly_correct_seconds']={'baseline':distribution([a['seconds'] for a,b in pairs]),
                                      'candidate':distribution([b['seconds'] for a,b in pairs])}
        arm['http_errors']=sum(r['http_status']!=200 for r in arm['cases'])
        arm['startup_seconds']=json.loads((folder/'startup.json').read_bytes())['seconds']
        for row in arm['cases']:
            body=json.loads((folder/(row['case']+'.response.json')).read_bytes())
            if row['http_status']==200:
                row['embedding_space_id']=body['embedding_space_id']
                row['reranker']=body['reranker']
                audit=body.get('audit',{})
                row['generation']={key:audit.get(key) for key in ('usage','input_tokens','elapsed_seconds')}
                row['generation']['assessment']={key:(audit.get('assessment_audit') or {}).get(key)
                    for key in ('usage','input_tokens','elapsed_seconds')}
                row['max_pair_tokens']=max((r['pair_tokens'] for r in body['ranked']),default=0)
    before=json.loads((root/'normal-before.json').read_bytes());after=json.loads((root/'normal-after.json').read_bytes())
    result['normal_library_unchanged']=before['documents']==after['documents'] and before['library']==after['library']
    result['normal_ready_after']=after['ready']['ready']
    if (root/'pair-tokens.json').exists():
        result['post_run_tokenizer_probe']=json.loads((root/'pair-tokens.json').read_bytes())
    result['decision']='Retain MiniLM defaults; no production activation or migration.'
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();write(a.output,summarize(Path('data/t32')/a.run))
