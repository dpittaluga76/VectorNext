"""Summarize captured development runs without calling models or altering raw data."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
from collections import Counter
from .score import Scorer


def distribution(values):
    return {'n':len(values),'median':statistics.median(values) if values else None,
        'min':min(values) if values else None,'max':max(values) if values else None}


def resources(samples):
    services=['vectornext','processor','llm']
    result={'samples':len(samples),'sampling_gap_seconds':distribution([(b['monotonic_ns']-a['monotonic_ns'])/1e9 for a,b in zip(samples,samples[1:])]),
        'device_mib_max':max((s['gpu_mib'] for s in samples if 'gpu_mib' in s),default=None),
        'device_samples':sum('gpu_mib' in s for s in samples),
        'max_sum_container_current_bytes':max((sum(s[v]['current_bytes'] for v in services) for s in samples if all('current_bytes' in s.get(v,{}) for v in services)),default=None)}
    for service in services:
        result[service]={name:max((s[service][name] for s in samples if name in s.get(service,{})),default=None) for name in ['current_bytes','anonymous_bytes','file_bytes','lifetime_peak_bytes']}
        result[service]['samples']=sum('current_bytes' in s.get(service,{}) for s in samples)
    return result


def summarize(root):
    complete=root/'queries.json'; progress=root/'queries-progress.json'
    if not complete.exists() and not progress.exists(): return None
    data=json.loads((complete if complete.exists() else progress).read_text(encoding='utf-8'))
    cases=data['cases'] if complete.exists() else data
    dataset=json.loads((Path(__file__).parent/'dataset.json').read_text(encoding='utf-8'))
    dev={c['id']:c for c in dataset['cases'] if c['split']=='dev'}
    labels={id:c['expected'] for id,c in dev.items()}
    if (root/'documents.json').exists():
        scorer=Scorer(dataset,json.loads((root/'documents.json').read_text(encoding='utf-8')))
        for row in cases:
            if row['http_status']==200: row['score']=scorer.case(dev[row['case']],json.loads((root/row['report_file']).read_text(encoding='utf-8')))
    result={'complete':complete.exists(),'scorer_sha256':hashlib.sha256((Path(__file__).parent/'score.py').read_bytes()).hexdigest(),'passes':{}}
    for cache in sorted({r['cache'] for r in cases}):
        rows=[r for r in cases if r['cache']==cache]; good=[r for r in rows if r['score'] is not None]
        report={'n':len(rows),'http_success':len(good),'exact_answers':sum(r['score']['answer_correct'] for r in good),
            'fields_correct':sum(r['score']['field_correct'] for r in good),'fields_total':sum(len(labels[r['case']].get('fields',{})) for r in rows),
            'status_confusion':dict(Counter(labels[r['case']]['status']+' -> '+(r['score']['actual_status'] if r['score'] else 'http_error') for r in rows)),
            'template_correct':sum(r['score']['template_correct'] is True for r in good),
            'template_total':sum(r['case']=='q_pele_exact' for r in rows),
            'wall_seconds':distribution([r['wall_seconds'] for r in rows]),'stages':{},'timings_ms':{},
            'prompt_tokens':distribution([r['score']['prompt_tokens'] for r in good if r['score']['prompt_tokens'] is not None]),
            'evidence_chars':distribution([r['score']['evidence_chars'] for r in good]),
            'repeated_source_span_bytes':sum(r['score']['repeated_source_span_bytes'] for r in good)}
        for stage in ['dense','keyword','fused','results','reranked','reranked_top5','reranked_top5_with_source_labels','context']:
            missing={'recall':0,'complete':False,'first_complete_rank':None}
            supported=[r['score']['stages'][stage] if r['score'] else missing for r in rows if labels[r['case']]['status']=='supported']
            ambiguous=[r['score']['stages'][stage] if r['score'] else missing for r in rows if labels[r['case']]['status']=='ambiguous']
            report['stages'][stage]={'supported_n':len(supported),'mean_recall':statistics.mean(v['recall'] for v in supported) if supported else None,
                'complete':sum(v['complete'] for v in supported),'first_complete_rank':distribution([v['first_complete_rank'] for v in supported if v['first_complete_rank'] is not None]),
                'ambiguity_n':len(ambiguous),'all_alternatives_complete':sum(v['complete'] for v in ambiguous)}
        times={}; queues=[]; backend=[]; usage=[]; assessment=[]; extraction=[]
        for r in good:
            raw=json.loads((root/r['report_file']).read_text(encoding='utf-8'))
            for k,v in raw['timings_ms'].items(): times.setdefault(k,[]).append(v)
            audit=raw.get('audit',{})
            for name,target in [('assessment_audit',assessment),(None,extraction)]:
                value=audit.get(name,{}) if name else audit
                if value.get('usage'): usage.append(value['usage'])
                if 'elapsed_seconds' in value: target.append(value['elapsed_seconds'])
            before=r['before']['processor']['generation'].get('scheduler',{})
            after=r['after']['processor']['generation'].get('scheduler',{})
            if before and after:
                queues.append(after['queue_seconds']-before['queue_seconds'])
                backend.append(after['backend_seconds']-before['backend_seconds'])
        report['timings_ms']={k:distribution(v) for k,v in times.items()}
        report['gpu_queue_seconds']=distribution(queues)
        report['model_service_backend_seconds']=distribution(backend)
        report['generation_usage']={'calls':len(usage),'input_tokens':sum(u['prompt_tokens'] for u in usage),'output_tokens':sum(u['completion_tokens'] for u in usage)}
        report['assessment_seconds']=distribution(assessment)
        report['extraction_seconds']=distribution(extraction)
        result['passes'][cache]=report
    if complete.exists():
        result['memory']=resources(data['samples'])
    return result


def main():
    p=argparse.ArgumentParser(); p.add_argument('root',type=Path); p.add_argument('--write',action='store_true'); a=p.parse_args()
    result={}
    for policy in ['plain','structural','generated']:
        if not (a.root/policy).exists(): continue
        for variant in sorted((a.root/policy).iterdir()):
            if variant.is_dir():
                value=summarize(variant)
                if value is not None: result[policy+'/'+variant.name]=value
    if a.write: (a.root/'summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    for name,r in result.items():
        for cache,v in r['passes'].items():
            print(json.dumps({'run':name,'pass':cache,'complete':r['complete'],'answers':str(v['exact_answers'])+'/'+str(v['n']),
                'wall_median':v['wall_seconds']['median'],'context_recall':v['stages']['context']['mean_recall'],
                'top5_recall':v['stages']['reranked_top5']['mean_recall'],'tokens_median':v['prompt_tokens']['median']}))


if __name__=='__main__': main()
