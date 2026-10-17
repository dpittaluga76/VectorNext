"""Offline score/report adapter for the exposed T39 internal execution."""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path
import random

from .capture_projection import exact_json, project
from .families import PRIMARY, digest, encoded, load
from .gate import paired
from .internal_runtime import SPLITS, context, save
from .metrics import distribution, latency, wilson
from .pilot_controls import score_views
from .table_grounding import report
from .typed_facts import floor


def cluster_interval(rows):
    groups=defaultdict(list)
    for row in rows:groups[row['family']].append(row['correct'])
    if not groups:return None
    rng=random.Random(3905);keys=sorted(groups);samples=[]
    for _ in range(10000):
        values=[x for key in rng.choices(keys,k=len(keys)) for x in groups[key]]
        samples.append(sum(values)/len(values))
    samples.sort()
    return {'families':len(groups),'cluster_sizes':dict(Counter(map(len,groups.values()))),
            'seed':3905,'resamples':10000,'interval':[samples[249],samples[9749]]}


def original_correct(case,capture):
    status=capture.get('status','error')
    if status!='supported':return status==case['original_expected']
    if case['original_expected']!='supported':return False
    fields=capture.get('fields',[])
    alternatives=case['original_alternatives']
    # Exact listed span matching only, never containment or numeric coercion.
    return len(fields)==1 and fields[0].get('type')=='string' and floor(fields[0]['value_text']) in set(map(floor,alternatives))


def arm_result(root,package,split,arm,representation='v2'):
    gold=load(package/split/'gold.json');proofs=load(package/split/'table-proofs.json')
    questions={q['case_id']:q for q in load(package/split/'questions.json')}
    captures={};timings={};jobs={};issues=[];reused=[]
    for case in gold['cases']:
        cid=case['case_id'];rep=representation
        if representation=='v1' and case['format']!='json':rep='v2';reused.append(cid)
        dest=root/'answers'/split/rep/arm/cid
        if (dest/'projection.json').exists():captures[cid]=load(dest/'projection.json')
        elif (dest/'job.json').exists():
            try:captures[cid]=project((dest/'job.json').read_bytes(),case['question'],context(package,root,split,case['document'],rep))
            except Exception as exc:issues.append({'case_id':cid,'error':str(exc)})
        if (dest/'finished.json').exists():
            done=load(dest/'finished.json');timings[cid]=done.get('wall_ms')
        if (dest/'job.json').exists():jobs[cid]=load(dest/'job.json')
    result=report(gold,captures,proofs)
    byid={row['case_id']:row for row in result['cases']}
    primary=[c for c in gold['cases'] if c['tier']==PRIMARY]
    score=sum(byid[c['case_id']]['correct'] is True for c in primary)
    rows=[{'case_id':c['case_id'],'family':questions[c['case_id']]['family'],
           'correct':byid[c['case_id']]['correct'] is True} for c in primary]
    stages=defaultdict(list);calls=defaultdict(list);token_counts=defaultdict(list)
    for cid,job in jobs.items():
        measured=latency(job.get('result') or {},job=job)
        for attempt in measured['attempts']:
            for name in ('queue_ms','activation_ms','work_ms'):
                if attempt.get(name) is not None:stages[name].append(attempt[name])
            for name,val in attempt['stages_ms'].items():stages[name].append(val)
            for call in attempt['calls']:
                calls[call['stage']].append(call.get('elapsed_ms'))
                token_counts[call['stage']].append(call.get('input_tokens'))
    controls={}
    for model in ('nuextract','gemma'):
        raw={}
        for c in primary:
            p=root/'controls'/model/split/c['case_id']/'closed_book.response.json'
            value=load(p).get('result',{}).get('control') if p.exists() else None
            raw[c['case_id']]=None if value is None else encoded(value)
        controls[model]=score_views(primary,raw,{c['case_id']:byid[c['case_id']]['correct'] is True for c in primary})
    result.update(arm=arm,split=split,representation=representation,projection_issues=issues,
        original_label_view={'n':len(gold['cases']),'correct':sum(original_correct(c,captures.get(c['case_id'],{})) for c in gold['cases']),
            'definition':'original listed strings/status; minimal floor; not historical dataset-native metric'},
        primary={'n':len(primary),'correct':score,'wilson95':wilson(score,len(primary)),
                 'cluster':cluster_interval(rows)},
        latency=distribution(timings.values()),stages={k:distribution(v) for k,v in stages.items()},
        model_calls={k:distribution(v) for k,v in calls.items()},
        input_tokens={k:distribution(v) for k,v in token_counts.items()},
        controls=controls,reused_non_table_captures=reused,
        paired_rows=[{'case_id':c['case_id'],'family':questions[c['case_id']]['family'],'split':split,
                     'correct':byid[c['case_id']]['correct'] is True,
                     'harmful':byid[c['case_id']]['outcome']=='answered_wrong',
                     'wall_ms':timings.get(c['case_id'])} for c in primary])
    return result


def comparisons(results):
    baseline=results['five'];rows=[]
    for row in baseline['paired_rows']:
        cid=row['case_id'];arms={}
        for arm,result in results.items():
            r=next(r for r in result['paired_rows'] if r['case_id']==cid)
            arms[arm]={k:r[k] for k in ('correct','harmful','wall_ms')}
        rows.append({k:row[k] for k in ('case_id','family','split')}|{'arms':arms})
    return {arm:paired(rows,arm) for arm in ('two','facet') if arm in results}


def select(root,package):
    results={arm:arm_result(root,package,'development',arm) for arm in ('five','two','facet')}
    gates=comparisons(results);eligible=[]
    for arm,gate in gates.items():
        checks={k:v for k,v in gate['checks'].items() if k not in ('sealed','prospectively_adequate')}
        if all(checks.values()):eligible.append(arm)
    def order(arm):
        rows=results[arm]['paired_rows'];paired_times=[r['wall_ms'] for r in rows if r['correct'] and
            next(b for b in results['five']['paired_rows'] if b['case_id']==r['case_id'])['correct']]
        return (-sum(r['correct'] for r in rows),sum(r['harmful'] for r in rows),
                distribution(paired_times)['median'] or float('inf'),arm!='two')
    candidate=min(eligible,key=order) if eligible else None
    value={'candidate':candidate,'gates':gates,'defaults_unchanged':True,
           'classification':'internal_development_selection_not_promotion',
           'input_freeze_sha256':digest((root/'execution-freeze.json').read_bytes())}
    save(root/'selection.json',value)
    return value


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=['score','select'])
    p.add_argument('--root',type=Path,required=True);p.add_argument('--package',type=Path,required=True)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.operation=='select':result=select(a.root,a.package)
    else:
        result={}
        for split in SPLITS:
            arms=['five','two','facet'] if split=='development' else ['five']
            if split=='exposed_candidates' and (a.root/'selection.json').exists():
                candidate=load(a.root/'selection.json')['candidate']
                if candidate:arms.append(candidate)
            result[split]={arm:arm_result(a.root,a.package,split,arm) for arm in arms}
            result[split]['comparisons']=comparisons({k:v for k,v in result[split].items() if k in arms})
        result['development_v1']=arm_result(a.root,a.package,'development','five','v1')
        save(a.output,result)
    print(json.dumps({'operation':a.operation,'candidate':result.get('candidate'),'saved':str(a.output)}))


if __name__=='__main__':main()
