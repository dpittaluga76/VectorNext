"""Read-only scoring of T11 captures; unavailable/failed cases stay in denominators."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
from evals.score import Scorer
from evals.summarize import distribution, resources
from evals.run import write
from .freeze import BLOCKS, HERE, digest, verify


STAGES=['dense','keyword','fused','results','reranked','reranked_top5','reranked_top5_with_source_labels','context']


def exact_outcome(row):
    s=row.get('score') or {}
    return bool(not row.get('unavailable_source_documents') and s.get('answer_correct') and s.get('template_correct') is not False)


def cited_outcome(row):
    s=row.get('score') or {}
    return exact_outcome(row) and s.get('expected_status')=='supported' and bool(s.get('proofs')) and all(p['gold_source_overlap'] for p in s['proofs'].values())


def complete_context(row):
    return bool(not row.get('unavailable_source_documents') and (row.get('score') or {}).get('stages',{}).get('context',{}).get('complete'))


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def planned_rows(cases,observed):
    by_id={r['case']:r for r in observed}
    if len(by_id)!=len(observed) or not by_id.keys()<=cases.keys(): raise ValueError('duplicate/unregistered captured case')
    return [by_id.get(id,{'case':id,'http_status':None,'score':None,'wall_seconds':None,'error':'not run'}) for id in cases]


def summarize_block(root,cases,dataset,docs):
    complete=root/'complete.json';progress=root/'progress.json'
    capture=json.loads(complete.read_text(encoding='utf-8')) if complete.exists() else {'cases':json.loads(progress.read_text(encoding='utf-8')) if progress.exists() else [],'samples':[]}
    rows=planned_rows(cases,capture['cases']);scorer=Scorer(dataset,docs)
    times={};usage=[];queues=[];backend=[];assessment=[];extraction=[];completed_calls=0
    details=[];evidence_items=[];evidence_documents=[]
    for row in rows:
        raw={}
        if row.get('report_file'):
            path=root/row['report_file']
            if digest(path)!=row['report_sha256']: raise ValueError('captured response bytes changed: '+str(path))
            raw=json.loads(path.read_text(encoding='utf-8'))
        if row['http_status']==200 and not row.get('scoring_error'):
            row['score']=scorer.case(cases[row['case']],raw)
            evidence_items.append(len(raw.get('evidence',[])))
            evidence_documents.append(len({e['key']['document_id'] for e in raw.get('evidence',[])}))
            for k,v in raw.get('timings_ms',{}).items():times.setdefault(k,[]).append(v)
            audit=raw.get('audit',{})
            for v,target in [(audit.get('assessment_audit',{}),assessment),(audit,extraction)]:
                if v.get('usage'):usage.append(v['usage'])
                if v.get('elapsed_seconds') is not None:target.append(v['elapsed_seconds'])
        for section,target in [('queue_seconds',queues),('backend_seconds',backend)]:
            a=row.get('before',{}).get('processor',{}).get('generation',{}).get('scheduler',{})
            b=row.get('after',{}).get('processor',{}).get('generation',{}).get('scheduler',{})
            if section in a and section in b:target.append(b[section]-a[section])
        if 'completed' in a and 'completed' in b:completed_calls+=b['completed']-a['completed']
        detail={k:v for k,v in row.items() if k not in ('before','after')}
        detail.update(answer=raw.get('answer'),formatted=raw.get('formatted'),timings_ms=raw.get('timings_ms'),
            assessment=raw.get('audit',{}).get('assessment'),
            retrieval_sha256=fingerprint(raw['retrieval']) if 'retrieval' in raw else None,
            ranking_sha256=fingerprint(raw['ranked']) if 'ranked' in raw else None,
            evidence=[{k:e[k] for k in ['id','key','text','sources','spans'] if k in e} for e in raw.get('evidence',[])])
        details.append(detail)
    good=[r for r in rows if r.get('score')]
    supported=[r for r in rows if cases[r['case']]['expected']['status']=='supported']
    result={'complete':complete.exists(),
        'metadata':json.loads((root/'metadata.json').read_text(encoding='utf-8')) if (root/'metadata.json').exists() else None,
        'planned':len(cases),'attempted':sum(r['http_status'] is not None for r in rows),
        'http_success':sum(r['http_status']==200 for r in rows),'exact_outcomes':sum(map(exact_outcome,rows)),
        'supported_exact':sum(map(exact_outcome,supported)),'supported_total':len(supported),
        'exact_with_gold_citation_overlap':sum(map(cited_outcome,supported)),
        'fields_correct':sum(r['score']['field_correct'] for r in good if not r.get('unavailable_source_documents')),
        'fields_total':sum(len(c['expected'].get('fields',{})) for c in cases.values()),
        'status_confusion':dict(Counter(cases[r['case']]['expected']['status']+' -> '+((r.get('score') or {}).get('actual_status') or 'error_or_not_run') for r in rows)),
        'template_correct':sum((r.get('score') or {}).get('template_correct') is True for r in rows),
        'template_total':sum('presentation' in c for c in cases.values()),
        'wall_seconds_all_attempts':distribution([r['wall_seconds'] for r in rows if r['wall_seconds'] is not None]),
        'prepared_prompt_tokens':distribution([r['score']['prompt_tokens'] for r in good if r['score']['prompt_tokens'] is not None]),
        'evidence_chars':distribution([r['score']['evidence_chars'] for r in good]),
        'evidence_items':distribution(evidence_items),'distinct_evidence_documents':distribution(evidence_documents),
        'generation_usage':{'scope':'HTTP 200 response audits only; validation-error requests also consume unreported tokens',
            'calls':len(usage),'scheduler_completed_operations_including_tokenization':completed_calls,
            'input_tokens':sum(u['prompt_tokens'] for u in usage),
            'output_tokens':sum(u['completion_tokens'] for u in usage),'cached_tokens':sum(u.get('prompt_tokens_details',{}).get('cached_tokens',0) for u in usage)},
        'timings_ms':{k:distribution(v) for k,v in times.items()},'assessment_seconds':distribution(assessment),
        'extraction_seconds':distribution(extraction),'gpu_queue_seconds':distribution(queues),
        'model_backend_seconds':distribution(backend),'stages':{},'tags':{},'cases':details,
        'memory':resources(capture['samples']),'process_startup_seconds':capture.get('startup_seconds')}
    for stage in STAGES:
        values=[(r.get('score') or {}).get('stages',{}).get(stage,{}) if not r.get('unavailable_source_documents') else {} for r in supported]
        ambiguous=[(r.get('score') or {}).get('stages',{}).get(stage,{}) for r in rows if cases[r['case']]['expected']['status']=='ambiguous']
        result['stages'][stage]={'supported_n':len(supported),'complete':sum(bool(v.get('complete')) for v in values),
            'mean_recall':statistics.mean(v.get('recall') or 0 for v in values),
            'ambiguity_n':len(ambiguous),'all_alternatives_complete':sum(bool(v.get('complete')) for v in ambiguous)}
    for tag in sorted({t for c in cases.values() for t in c['tags']}):
        subset=[r for r in rows if tag in cases[r['case']]['tags']]
        result['tags'][tag]={'n':len(subset),'exact_outcomes':sum(map(exact_outcome,subset)),
            'complete_context':sum(map(complete_context,subset))}
    return result


def paired(five,two):
    f={r['case']:r for r in five['cases']};t={r['case']:r for r in two['cases']}
    if f.keys()!=t.keys():raise ValueError('unpaired case IDs')
    common=[id for id in f if cited_outcome(f[id]) and cited_outcome(t[id])]
    result={'n':len(f),'five_only_exact':[id for id in f if exact_outcome(f[id]) and not exact_outcome(t[id])],
        'two_only_exact':[id for id in f if exact_outcome(t[id]) and not exact_outcome(f[id])],
        'two_lost_context':[id for id in f if complete_context(f[id]) and not complete_context(t[id])],
        'two_gained_context':[id for id in f if complete_context(t[id]) and not complete_context(f[id])],
        'matched_supported_cited_cases':common}
    comparable=[id for id in f if f[id].get('retrieval_sha256') and t[id].get('retrieval_sha256')]
    result['ranking_control']={'comparable_responses':len(comparable),
        'retrieval_mismatches':[id for id in comparable if f[id]['retrieval_sha256']!=t[id]['retrieval_sha256']],
        'reranking_mismatches':[id for id in comparable if f[id]['ranking_sha256']!=t[id]['ranking_sha256']]}
    for name,ids in [('all',list(f)),('matched_supported_cited',common)]:
        result[name+'_five_seconds']=distribution([f[id]['wall_seconds'] for id in ids if f[id]['wall_seconds'] is not None])
        result[name+'_two_seconds']=distribution([t[id]['wall_seconds'] for id in ids if t[id]['wall_seconds'] is not None])
        a=result[name+'_five_seconds']['median'];b=result[name+'_two_seconds']['median']
        result[name+'_median_reduction_percent']=100*(1-b/a) if a and b else None
        result[name+'_paired_seconds_saved']=distribution([f[id]['wall_seconds']-t[id]['wall_seconds'] for id in ids if f[id]['wall_seconds'] is not None and t[id]['wall_seconds'] is not None])
    return result


def summarize(root):
    verify();dataset=json.loads((HERE/'dataset.json').read_text(encoding='utf-8'))
    cases={c['id']:c for c in dataset['cases']}
    docs=json.loads((root/'documents.json').read_text(encoding='utf-8'))
    ingestion=json.loads((root/'ingestion/complete.json').read_text(encoding='utf-8'))
    result={'run':root.name,'freeze_sha256':digest(HERE/'freeze.json'),'unique_questions':len(cases),
        'scorer_sha256':digest(HERE.parent/'score.py'),'summary_script_sha256':digest(Path(__file__)),
        'scope':'Same 28 questions repeated, not 112 independent questions; Codex-authored and reviewed.',
        'source_review':'See the separate reviewed report; gold overlap is not automatic factual entailment.',
        'metadata':json.loads((root/'ingestion/metadata.json').read_text(encoding='utf-8')),
        'ingestion':{k:v for k,v in ingestion.items() if k not in ('before','after','samples','rows')},
        'ingestion_documents':[{'document':r['document'],'committed':r['committed'],'seconds':r['seconds'],
            'source_bytes':r['source_bytes'],'stage':r.get('job',{}).get('stage'),
            'failure':r.get('error') or r.get('job',{}).get('last_failure')} for r in ingestion['rows']],
        'ingestion_memory':resources(ingestion['samples']),'blocks':{},'paired':{}}
    for key,path in [('hardware','hardware.json'),('parse_fidelity','five-cold/parse-fidelity.json'),
        ('reviewed_ingestion_diagnostics','ingestion/source-review-diagnostics.json')]:
        if (root/path).exists():result[key]=json.loads((root/path).read_text(encoding='utf-8'))
    for name,_ in BLOCKS:result['blocks'][name]=summarize_block(root/name,cases,dataset,docs)
    for cache in ('cold','warm'):result['paired'][cache]=paired(result['blocks']['five-'+cache],result['blocks']['two-'+cache])
    all_complete=all(v['complete'] for v in result['blocks'].values())
    no_loss=all(not v['five_only_exact'] and not v['two_lost_context'] for v in result['paired'].values())
    all_correct=all(result['blocks']['two-'+c]['exact_outcomes']==len(cases) for c in ('cold','warm'))
    faster=all((v['all_median_reduction_percent'] or 0)>=20 for v in result['paired'].values())
    result['decision']={'all_blocks_complete':all_complete,'two_preserves_all_paired_outcomes_and_context':no_loss,
        'two_correct_on_all_cases_both_passes':all_correct,'median_reduction_at_least_20_percent_both_passes':faster,
        'two_passes_conservative_gate':all_complete and no_loss and all_correct and faster,
        'default_primary_limit':5,'automatic_default_change':False}
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--write',action='store_true');a=p.parse_args()
    value=summarize(a.root)
    if a.write:write(a.root/'summary.json',value)
    for name,block in value['blocks'].items():
        print(json.dumps({'block':name,'complete':block['complete'],'exact':str(block['exact_outcomes'])+'/'+str(block['planned']),
            'supported_context':str(block['stages']['context']['complete'])+'/'+str(block['supported_total']),
            'median_seconds':block['wall_seconds_all_attempts']['median']}))
    print(json.dumps(value['decision']))


if __name__=='__main__':main()
