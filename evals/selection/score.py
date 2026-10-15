"""T24 stage scoring plus controlled-shortlist and paired-repeat checks."""
import json
from pathlib import Path
from evals.evidence.score import score_file, distribution, key


def records(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()]


def score(path,gold):
    result=score_file(path,gold)
    queries=[r for r in records(path) if 'id' in r]
    for metric in ('facet_rerank_ms','selection_ms'):
        result['latency'][metric]=distribution([q[metric] for q in queries if metric in q])
    result['pair_evaluations']=sum(q.get('pair_evaluations',0) for q in queries)
    result['facet_calls']=sum(len(q.get('facet_audit',[])) for q in queries)
    for group in ('single','multi'):
        rows=[r for r in result['cases'] if r['group']==group]
        result[group]={'complete':sum(r['primary']['complete'] for r in rows),'questions':len(rows),'facts':sum(len(r['primary']['covered']) for r in rows),'required':sum(r['required'] for r in rows)}
    return result


def check_comparison(captures):
    reference={};previous={};counts={'shortlist_matches':0,'repeat_matches':0,'unavailable':[]}
    for name,rows in captures:
        for q in rows:
            if 'id' not in q:continue
            if q.get('status')!='ok':counts['unavailable'].append([name,q['id']]);continue
            selected=list(map(key,q['selected']));primary=list(map(key,q['primary']))
            assert len(selected)<=20 and len(set(selected))==len(selected)
            assert len(primary)<=5 and len(set(primary))==len(primary) and set(primary)<=set(selected)
            signature={s:q[s] for s in ('raw','selected','rerank')}
            if q['id'] in reference:
                assert reference[q['id']]==signature,('shortlist/general scores changed',name,q['id'])
                counts['shortlist_matches']+=1
            else:reference[q['id']]=signature
            repeat=(q['arm'],q['id'])
            signature={s:q[s] for s in ('raw','selected','primary','rerank','facet_audit','selection')}
            if repeat in previous:
                assert previous[repeat]==signature,('paired repeat changed',name,q['id'])
                counts['repeat_matches']+=1
            else:previous[repeat]=signature
    return counts
