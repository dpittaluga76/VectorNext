"""Source-coordinate failure attribution; absence of a capture stays unknown."""
import argparse
from collections import Counter
import json
from pathlib import Path

from .attribution import attribute
from .capture_projection import exact_json
from .families import load
from .internal_evaluate import observed, range_covered
from .internal_oracle_results import projection
from .internal_runtime import context, save
from .table_grounding import covers, score_case


def coverage(case,evidence,ctx,proof):
    if case['expected']!='supported' or case['tier']=='stress_adjudication':return None
    refs=[r for e in evidence for r in observed(ctx,e)]
    if case['format']=='json':
        return any(all(any(covers(r,s) for s in refs) for r in p['required']) for p in proof['proof_sets'])
    return all(any(all(range_covered(p,refs) for p in group) for group in role['proof_sets']) for role in case['roles'])


def inventory_for_keys(ctx,inventory,keys):
    indexed={e['key']['chunk_id']:e for e in inventory}
    chunks={c['id']:c for c in ctx['snapshot']['chunks']}
    result=[]
    for key in keys:
        e=indexed.get(key['chunk_id'])
        if e is None:
            chunk=chunks.get(key['chunk_id']);record=(chunk or {}).get('attributes',{}).get('record')
            if record:
                e=next((e for e in inventory if e['record']==record['value'] and e['sources']==record['sources']),None)
        if e is None:return None
        result.append(e)
    return result


def summarize(root,package,scores,oracles):
    gold=load(package/'development/gold.json')['cases']
    proofs={p['case_id']:p for p in load(package/'development/table-proofs.json')['cases']}
    baseline={r['case_id']:r for r in scores['development']['five']['cases']}
    oracle={variant:{r['case_id']:r for r in oracles['nuextract'][variant]['cases']}
            for variant in ('automatic_fields','gold_fields')}
    rows=[]
    for case in gold:
        cid=case['case_id'];ctx=context(package,root,'development',case['document']);b=ctx['binding']
        row={'case_id':cid,'expected':case['expected'],'ingested':b['state']=='committed',
             'baseline_correct':baseline[cid]['correct'],'plan_correct':None,
             'oracle_evidence_correct':oracle['automatic_fields'][cid]['validator_on_correct']
                 if oracle['automatic_fields'][cid]['state']=='captured' else None,
             'oracle_fields_correct':oracle['gold_fields'][cid]['validator_on_correct']
                 if oracle['gold_fields'][cid]['state']=='captured' else None}
        dest=root/'answers/development/v2/five'/cid;job=load(dest/'job.json') if (dest/'job.json').exists() else {}
        view=job.get('result') or {};report=json.loads(view['raw_report']) if view.get('raw_report') else {}
        row['system_error']=baseline[cid]['outcome']=='system_error'
        if b['state']=='committed':
            inventory=load(root/'ingestion'/b['document_id']/'evidence.json')
            retrieval=report.get('retrieval')
            if isinstance(retrieval,dict) and 'results' in retrieval:
                candidates=inventory_for_keys(ctx,inventory,[r['key'] for r in retrieval['results']])
                if candidates is not None:row['candidate_support']=coverage(case,candidates,ctx,proofs.get(cid,{}))
            for attempt in job.get('attempts',[]):
                for operation in attempt.get('operations',[]):
                    if operation.get('operation')!='answer':continue
                    reference=(operation.get('model_measurement') or {}).get('evaluation_capture',{}).get('rpc')
                    if not reference:continue
                    folder=root/'rpc/interactive'/reference
                    if not (folder/'request.json').exists():continue
                    inp=load(folder/'request.json')['input']
                    row['selected_support']=coverage(case,inp['evidence'],ctx,proofs.get(cid,{}))
                    response=load(folder/'response.json').get('result',{})
                    row['assessment']=response.get('audit',{}).get('assessment',{}).get('status')
                    comparison=root/'comparisons'/reference/'comparison.json'
                    if comparison.exists():
                        value=exact_json(comparison.read_bytes())
                        if value['materialization']=='completed':
                            off=projection(value['validator_off']['answer'],inp['evidence'],ctx)
                            score=score_case(case,off,proofs.get(cid,{}))
                            row['candidate_correct']=score['correct'];row['validator']=value['validator_on']['state']
                            # Mechanical/coordinate checks do not supply independent semantic review.
                            row['proof_review']=None
        rows.append({**row,**attribute(row)})
    return {'cases':rows,'flag_counts':dict(Counter(flag for r in rows for flag in r['flags'])),
            'unobserved_counts':dict(Counter(key for r in rows for key in r['unobserved'])),
            'independent_proof_review':False,'unique_root_cause_claimed':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('root','package','scores','oracles','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();save(a.output,summarize(a.root,a.package,load(a.scores),load(a.oracles)))


if __name__=='__main__':main()
