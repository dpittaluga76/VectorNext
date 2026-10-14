"""Score offline Rust retrieval replays; no model calls and no holdout queries."""
import argparse
import json
from pathlib import Path
import statistics
from .score import Scorer


def summarize(root):
    dataset=json.loads((Path(__file__).parent/'dataset.json').read_text(encoding='utf-8'))
    dev={c['id']:c for c in dataset['cases'] if c['split']=='dev'}
    scorers={p:Scorer(dataset,json.loads((root/p/'baseline/documents.json').read_text(encoding='utf-8'))) for p in ['plain','structural','generated']}
    output=[]
    for run in json.loads((root/'replay.json').read_text(encoding='utf-8'))['runs']:
        sc=scorers[run['policy']]; rows=[]
        for row in run['cases']:
            case=dev[row['case']]; expected=case['expected']; sets=expected.get('support_sets',[])
            if expected['status']=='ambiguous': sets=[list({e for alt in expected['alternatives'] for e in alt['support_set']})]
            hits=row['retrieval']['results']
            rows.append({'case':case['id'],'status':expected['status'], 'stages':{
                'raw_results':sc.stage([sc.chunk_item(h['key']) for h in hits],sets),
                'top5_with_source_labels':sc.stage([sc.source_label_item(h['key']) for h in hits[:5]],sets)}})
        if {r['case'] for r in rows}!=set(dev): raise ValueError('replay must contain exactly the dev cases')
        result={k:v for k,v in run.items() if k!='cases'}; result['cases']=rows; result['stages']={}
        for stage in ['raw_results','top5_with_source_labels']:
            supported=[r['stages'][stage] for r in rows if r['status']=='supported']
            ambiguous=[r['stages'][stage] for r in rows if r['status']=='ambiguous']
            result['stages'][stage]={'supported_n':len(supported),'mean_recall':statistics.mean(r['recall'] for r in supported),
                'complete':sum(r['complete'] for r in supported),'ambiguity_n':len(ambiguous),'all_alternatives_complete':sum(r['complete'] for r in ambiguous)}
        output.append(result)
    return output


def main():
    p=argparse.ArgumentParser(); p.add_argument('root',type=Path); a=p.parse_args()
    result=summarize(a.root)
    (a.root/'replay-summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    for run in result:
        print(json.dumps({k:v for k,v in run.items() if k!='cases'}))


if __name__=='__main__': main()
