"""Offline exact Rust materialization/validation and oracle scoring bridge."""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess

from .capture_grounding import cell_coordinate, prose_coordinates, table_coordinates
from .capture_projection import exact_json
from .families import PRIMARY, encoded, load
from .internal_runtime import context, save
from .table_grounding import score_case


def projection(answer,evidence,ctx):
    fields=[];lookup={e['id']:e for e in evidence};b=ctx['binding'];d=ctx['descriptor']
    for name,f in answer['fields'].items():
        e=lookup[f['evidence_id']];value=f['value']
        field={'name':name,'type':'string' if isinstance(value,str) else 'non_string',
               'value_text':value if isinstance(value,str) else str(value),'proofs':[]}
        if d['format']=='json':
            observed=table_coordinates(ctx['original'],ctx['annotation'],ctx['representation'],e,b['document_id'],b['revision'])
            field['evidence_coordinates']=observed['visible_coordinates']
            try:field['value_coordinate']=cell_coordinate(ctx['original'],ctx['annotation'],observed['record_index'],f['pointer'])
            except (ValueError,TypeError):field['value_coordinate']=None
        else:
            field['proofs']=prose_coordinates(ctx['text'],d['review_text_sha256'],d['original_sha256'],
                e,ctx['snapshot'],b['document_id'],b['revision'])['proofs']
        fields.append(field)
    return {'status':answer['status'],'fields':fields,'diagnostic_only':True}


def compare_directory(destination,input_raw,candidate_raw,binary):
    destination.mkdir(parents=True,exist_ok=True)
    for name,raw in [('input.json',input_raw),('candidate.json',candidate_raw)]:
        path=destination/name
        if path.exists():
            if path.read_bytes()!=raw:raise ValueError('Comparison input changed')
        else:path.write_bytes(raw)
    if (destination/'comparison.json').exists() or (destination/'error.json').exists():return
    result=subprocess.run([str(binary),str(destination/'input.json'),str(destination/'candidate.json'),
                           str(destination/'comparison.json')],capture_output=True,text=True)
    if result.returncode:save(destination/'error.json',{'exit':result.returncode,'stderr':result.stderr})


def prepare(root,binary):
    # Invoked in an offline Docker process with the already frozen Rust helper.
    for request in (root/'rpc/interactive').rglob('request.json'):
        value=load(request)
        if value.get('op')!='answer':continue
        reply=request.with_name('response.json')
        if not reply.exists() or 'answer' not in load(reply).get('result',{}):continue
        relative=request.parent.relative_to(root/'rpc/interactive')
        compare_directory(root/'comparisons'/relative,encoded(value['input']),reply.read_bytes(),binary)
    for request in (root/'oracles').rglob('answer.request.json'):
        reply=request.with_name('answer.response.json')
        if reply.exists() and 'answer' in load(reply).get('result',{}):
            compare_directory(request.parent/'validation',encoded(load(request)['input']),reply.read_bytes(),binary)


def summarize(root,package):
    gold=load(package/'development/gold.json')['cases']
    proofs={p['case_id']:p for p in load(package/'development/table-proofs.json')['cases']}
    result={}
    for model in ('nuextract','gemma'):
        result[model]={}
        for variant in ('automatic_fields','gold_fields'):
            rows=[]
            for case in gold:
                dest=root/'oracles'/model/case['case_id']/variant
                done=load(dest/'finished.json') if (dest/'finished.json').exists() else {'state':'missing'}
                row={'case_id':case['case_id'],'tier':case['tier'],'state':done['state'],
                     'reason':done.get('reason') or done.get('error'),'validator_on_correct':False,
                     'validator_off_correct':False,'rejected_gold_matching':False}
                compare=dest/'validation/comparison.json'
                if compare.exists():
                    material=exact_json(compare.read_bytes())
                    row['materialization']=material['materialization']
                    if material['materialization']=='completed':
                        inp=load(dest/'input.json');ctx=context(package,root,'development',case['document'])
                        for name in ('validator_on','validator_off'):
                            answer=material[name].get('answer')
                            if answer is None:
                                capture={'status':'rejected','fields':[]}
                            else:capture=projection(answer,inp['evidence'],ctx)
                            scored=score_case(case,capture,proofs.get(case['case_id'],{}))
                            row[name+'_correct']=scored['correct']
                            row[name+'_grounding']=scored['evidence_correct']
                            row[name+'_outcome']=scored['outcome']
                        row['rejected_gold_matching']=(material['validator_on']['state']=='rejected' and
                                                       row['validator_off_correct'] is True)
                rows.append(row)
            primary=[r for r in rows if r['tier']==PRIMARY]
            result[model][variant]={'planned':len(rows),'states':dict(Counter(r['state'] for r in rows)),
                'primary_n':len(primary),
                'validator_on_correct':sum(r['validator_on_correct'] is True for r in primary),
                'validator_off_correct':sum(r['validator_off_correct'] is True for r in primary),
                'gold_matching_rejections_unadjudicated':sum(r['rejected_gold_matching'] for r in rows),
                'cases':rows}
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=['prepare','score'])
    p.add_argument('--root',type=Path,required=True);p.add_argument('--package',type=Path)
    p.add_argument('--binary',type=Path);p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.operation=='prepare':prepare(a.root,a.binary)
    else:save(a.output,summarize(a.root,a.package))


if __name__=='__main__':main()
