"""Exact scoring of saved responses only; no inference and no gold mutation."""
import argparse
import json
from pathlib import Path
from experiments.t32.score import exact_load, score as explicit_score
from experiments.t32.summarize import mib
from evals.evidence.score import distribution
from .run import ARMS, HERE, SELECTED, write, digest


def case_score(code, raw, label, documents, browser=False):
    view=exact_load(raw) if raw else {}
    report_raw=view.get('raw_report','{}').encode() if browser else raw
    report=exact_load(report_raw) if report_raw else {}
    if browser:
        specs=report.get('request',{}).get('fields',{})
        fields=report.get('answer',{}).get('fields',{})
        names=list(fields)
        # Names are proposed by the planner; require exactly one field of the right
        # type/value, source support, a ready plan, and an exact matching UI projection.
        name=names[0] if len(names)==1 else '__missing__'
        gold={'status':label['status'],'values':{name:label['value']},'facts':label['facts']}
        result=explicit_score(code,report_raw,gold,documents)
        ui=view.get('fields',[])
        projected=(len(ui)==1 and ui[0].get('name')==name and ui[0].get('kind')==label['kind']
                   and ui[0].get('value_text')==str(fields.get(name,{}).get('value')))
        result['planning_status']=report.get('planning',{}).get('plan',{}).get('status')
        result['projection_exact']=projected
        result['correct'] &= (specs.get(name,{}).get('kind')==label['kind'] and projected
                              and result['planning_status']=='ready' and view.get('outcome')=='supported')
    else:
        result=explicit_score(code,raw,label,documents)
    result['audit']=report.get('audit')
    result['planning']=report.get('planning')
    return result


def pdf_exception(code,raw,docs):
    body=exact_load(raw) if raw else {};doc=docs.get('cedar-audit',{})
    answer=body.get('answer',{});proof=answer.get('fields',{}).get('interval_days',{})
    return (code==200 and answer.get('status')=='supported' and proof.get('value')==45
        and body.get('validation',{}).get('mechanical_support')=='passed'
        and doc.get('original',{}).get('sha256')=='d718f78196f0b4372e6b0e584f630e960194357c74af2f4d28bc00519d3427cd'
        and any(e['id']==proof.get('evidence_id') and e['key']['document_id']=='cedar-audit'
            and e['key']['revision']==doc.get('revision')
            and 'The final July 2031 interval for the Cedar type B manifold is 45 days.' in e['text']
            for e in body.get('evidence',[])))


def summarize(root):
    root=Path(root);docs=exact_load((root/'corpus/documents.json').read_bytes())
    all_gold=exact_load(Path('experiments/t32/gold.json').read_bytes())
    gold={key:all_gold[key] for key in SELECTED}
    browser=exact_load((HERE/'browser-gold.json').read_bytes())
    result={'run':root.as_posix(),'scheduled':24,'arms':{},'execution_freeze_sha256':digest(root/'execution-freeze.json'),
            'source_archive_sha256':digest(root/'source.zip'),'corpus_sha256':digest(root/'corpus/documents.json'),
            'ingestion':json.loads((root/'corpus/ingestion.json').read_bytes()),
            'review_reference':'docs/reports/t32-source-review.md'}
    for arm in ARMS:
        folder=root/arm;rows=[]
        for identifier,label in {**gold,**browser}.items():
            row=json.loads((folder/(identifier+'.row.json')).read_bytes())
            raw=(folder/(identifier+'.response.json')).read_bytes()
            if digest(folder/(identifier+'.response.json'))!=row['response_sha256']:raise ValueError('response changed')
            row['score']=case_score(row['http_status'],raw,label,docs,identifier in browser)
            # Reports keep audit JSON in its original raw capture to avoid Decimal
            # coercion or bloating a summary; keep useful stable diagnostics here.
            audit=row['score'].pop('audit') or {}
            row['generation']={k:audit.get(k) for k in ('model','usage','input_tokens','elapsed_seconds','assessment')}
            row['generation']['assessment_audit']={k:(audit.get('assessment_audit') or {}).get(k)
                for k in ('model','usage','input_tokens','elapsed_seconds')}
            plan=row['score'].pop('planning') or {}
            row['planning']={'plan':plan.get('plan'),'audit':{k:plan.get('audit',{}).get(k)
                for k in ('model','usage','input_tokens','elapsed_seconds')}}
            row['reviewed_correct']=row['score']['correct'] or (identifier=='pdf_correction' and pdf_exception(row['http_status'],raw,docs))
            rows.append(row)
        samples=[json.loads(line) for line in (folder/'resources.jsonl').read_text().splitlines()]
        gpu=[float(s['gpu']['output'].strip().split(',')[2]) for s in samples if not s['gpu']['exit'] and s['gpu']['output'].strip()]
        resources={}
        for service in ('api','processor','llm'):
            memory=[json.loads(line) for s in samples if not s['containers']['exit']
                    for line in s['containers']['output'].splitlines() if line.strip()]
            memory=[r for r in memory if r['Name'].endswith('-'+service+'-1')]
            resources[service]={'peak_ram_mib':max((mib(r['MemUsage']) for r in memory),default=None),'samples':len(memory)}
        result['arms'][arm]={'correct':sum(r['score']['correct'] for r in rows),
            'reviewed_correct':sum(r['reviewed_correct'] for r in rows),'total':6,
            'http_errors':sum(r['http_status'] not in (0,200) for r in rows),
            'preflight_blocked':sum(r['seconds'] is None for r in rows),
            'latency_seconds':distribution([r['seconds'] for r in rows if r['seconds'] is not None]),
            'peak_device_memory_mib':max(gpu,default=None),'resources':resources,'cases':rows}
        for key in ('startup','restart'):
            file=folder/(key+'.json')
            result['arms'][arm][key+'_seconds']=json.loads(file.read_bytes())['seconds'] if file.exists() else None
    baseline=result['arms']['12b']['cases']
    for arm in result['arms'].values():
        pairs=list(zip(baseline,arm['cases']))
        arm['gained']=[b['case'] for a,b in pairs if b['reviewed_correct'] and not a['reviewed_correct']]
        arm['lost']=[b['case'] for a,b in pairs if a['reviewed_correct'] and not b['reviewed_correct']]
        common=[(a,b) for a,b in pairs if a['reviewed_correct'] and b['reviewed_correct']]
        arm['common_success_seconds']={'baseline':distribution([a['seconds'] for a,b in common]),
                                      'candidate':distribution([b['seconds'] for a,b in common])}
    before=json.loads((root/'normal-before.json').read_bytes());after=json.loads((root/'normal-after.json').read_bytes())
    result['normal_unchanged']=all(before[k]==after[k] for k in ('documents','library','jobs'))
    result['normal_ready']=after['ready']['ready']
    return result


def serializable(value):
    from decimal import Decimal
    if isinstance(value,Decimal):return str(value)
    raise TypeError(type(value).__name__)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.write_text(json.dumps(summarize(Path('data/t34')/a.run),indent=2,default=serializable)+'\n',encoding='utf-8',newline='\n')
