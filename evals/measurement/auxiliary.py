"""Component experiments are not end-to-end answer trials. Keep their denominators separate."""
from evals.evidence.score import catalog, score_case
from experiments.t26.planner_check import score as planner_score
from .metrics import exact_load, distribution, wilson
from experiments.t36.score import match_fields


def retrieval(reader):
    root = reader.root
    files = [(p, root/'evals/evidence/gold.json') for p in (root/'data/t23/final-v1').glob('0[1-9]-*.jsonl')]
    files += [(p, root/'evals/selection/gold.json') for p in (root/'data/t24/final-v1').glob('0[1-9]-*.jsonl')]
    for corpus, labels in [('nist','evidence'),('nasa','selection')]:
        files += [(p, root/f'evals/{labels}/gold.json') for p in (root/f'data/t31/comparison-v1/{corpus}').glob('*/0[1-9]-*.jsonl')]
    result = []
    for path, labels in sorted(files):
        gold = reader.read(labels)
        records = [exact_load(line) for line in reader.raw(path).splitlines() if line.strip()]
        finish = next((r for r in records if r.get('kind') == 'finish'), None)
        rows = {r['id']:r for r in records if 'id' in r}
        if len(rows) != sum('id' in r for r in records):
            raise ValueError('duplicate component case: ' + str(path))
        chunks = catalog(finish['documents']) if finish else {}
        cases = []
        for case in gold['cases']:
            try:
                scored = score_case(case, rows.get(case['id']), gold['facts'], chunks)
            except (KeyError, ValueError) as error:
                scored = {'id':case['id'],'error':True,'required':len(case['facts']),'unscorable_reason':str(error)}
            cases.append(scored)
        positives = [c for c in cases if c.get('required',0) > 0]
        complete = sum(c.get('primary',{}).get('complete') is True for c in positives)
        result.append({'capture':path.relative_to(root).as_posix(),'track':'retrieval_only',
                       'questions':len(cases),'cases':cases,'primary_complete':complete,
                       'positive_questions':len(positives),'wilson95':wilson(complete,len(positives)),
                       'latency_ms':distribution(r.get('elapsed_ms') for r in rows.values())})
    return result


def planning(reader):
    root = reader.root
    labels = []
    for path in ['experiments/t26/cases.json','experiments/t26/cases-v3.json','experiments/t26/regressions.json']:
        labels.extend(reader.read(root/path))
    folders = [root/'data/t26'/name for name in ('baseline-v1','candidate-v1','candidate-v3','regressions-v3')]
    folders += [root/f'data/{task}/application-v1/{name}' for task in ('t27','t28') for name in ('planner','regressions')]
    result = []
    for folder in folders:
        if not folder.exists(): continue
        cases = []
        for path in sorted(folder.glob('*-capture.json')):
            captured = reader.read(path)
            response = folder/(captured['id']+'-response.json')
            raw = reader.read(response) if response.exists() else None
            label = next((c for c in labels if c['id'] == captured['id'] and c['input'] == captured['input']), None)
            errors = planner_score(label,raw) if label and raw else None
            cases.append({'case':captured['id'],'capture':response.relative_to(root).as_posix(),
                          'correct':not errors if errors is not None else None,
                          'legacy_errors':captured.get('errors'),'errors':errors,
                          'seconds':captured.get('seconds'),
                          'unscorable_reason':None if errors is not None else 'missing matching frozen label/response'})
        correct = sum(c['correct'] is True for c in cases)
        result.append({'group':folder.relative_to(root).as_posix(),'track':'planner_only','cases':cases,
                       'correct':correct,'questions':len(cases),'wilson95':wilson(correct,len(cases))})
    return result


def functional_smokes(reader):
    """Retain the narrower original checks; never call these semantic-quality labels."""
    root=reader.root
    groups=[]
    folders=[root/'data/t26'/name for name in ('live-v1','live-v3')]
    folders += [root/f'data/{task}/application-v1/source' for task in ('t27','t28')]
    for folder in folders:
        if not folder.exists():continue
        labels=reader.read(folder/'cases.json')
        previous=reader.read(folder/'summary.json')
        requests=[(p,reader.read(p)) for p in sorted(folder.glob('*-request.json'))]
        cases=[]
        for identifier, documents, question, expected, history in labels:
            match=next(((p,m) for p,m in requests if m['path']=='/v1/ui/ask'
                        and m['request']['question']==question and m['request'].get('history',[])==history),None)
            row={'case':identifier,'correct':None,'semantic_support':'not_independently_labelled',
                 'legacy':next((c for c in previous['results'] if c['id']==identifier),None)}
            if match:
                path,meta=match;response=path.with_name(path.name.replace('-request','-response'))
                body=reader.read(response);code=meta['http_status']
                error=(body.get('error') or {}).get('message','')
                if isinstance(expected,str):
                    correct=(code==400 and (body.get('error') or {}).get('code')=='invalid_request'
                             and (expected in error or identifier=='aggregation' and 'unsupported corpus aggregation' in error))
                else:
                    correct=(code==200 and body.get('outcome')==('supported' if expected is not None else 'insufficient_evidence')
                             and sorted(f['value_text'] for f in body.get('fields',[]))==sorted(expected or []))
                    if code==200:
                        report=exact_load(body['raw_report'])
                        correct &= report.get('planning',{}).get('plan',{}).get('status')=='ready'
                        evidence={e['id'] for e in body.get('evidence',[])}
                        correct &= all(f['evidence_id'] in evidence for f in body.get('fields',[]))
                row.update(correct=bool(correct),capture=response.relative_to(root).as_posix(),seconds=meta.get('seconds'))
            cases.append(row)
        groups.append({'group':folder.relative_to(root).as_posix(),'track':'source_smoke_values_and_references',
                       'questions':len(cases),'correct':sum(c['correct'] is True for c in cases),'cases':cases})
    folder=root/'data/t28/application-v1/fresh'
    if folder.exists():
        labels=reader.read(root/'experiments/t28/cases.json');meta=reader.read(folder/'summary.json')
        for mode in ('fixed','source'):
            cases=[]
            for label in labels:
                path=folder/(label['id']+'-'+mode+'.json')
                raw=reader.read(path) if path.exists() else {}
                answer=(raw.get('result',{}) if mode=='fixed' else raw).get('answer',{})
                correct=answer.get('status')==label['status']
                if label['status']=='supported':
                    fields=answer.get('fields',{})
                    correct &= set(fields)==set(label['expected']) and all(
                        fields[k].get('pointer')==v['pointer'] for k,v in label['expected'].items())
                    if mode=='source' and correct:
                        def literal(v):
                            return 'null' if v is None else 'true' if v is True else 'false' if v is False else str(v)
                        correct &= all(literal(fields[k]['value'])==v['value_text'] for k,v in label['expected'].items())
                else:correct &= answer.get('fields')=={}
                if mode=='source':correct &= raw.get('validation',{}).get('mechanical_support')=='passed'
                cases.append({'case':label['id'],'capture':path.relative_to(root).as_posix(),'correct':bool(correct),
                              'legacy':next((r for r in meta['results'] if r['id']==label['id'] and r['mode']==mode),None)})
            groups.append({'group':folder.relative_to(root).as_posix()+'/'+mode,
                           'track':'extraction_status_and_pointer_only' if mode=='fixed' else 'source_smoke_values_and_pointers',
                           'questions':len(cases),'correct':sum(c['correct'] for c in cases),'cases':cases})
    folder=root/'data/t36/development-v1'
    if folder.exists():
        cases=[]
        for label in reader.read(root/'experiments/t36/development-requests.json'):
            path=folder/'planner'/(label['id']+'.response.json')
            captured=reader.read(path)
            body=exact_load(captured['raw'])
            names=match_fields(body.get('result',{}).get('plan',{}),label['expected'])
            cases.append({'case':label['id'],'capture':path.relative_to(root).as_posix(),
                          'correct':captured['http_status']==200 and names is not None})
        groups.append({'group':folder.relative_to(root).as_posix(),'track':'planner_development_observed',
                       'questions':len(cases),'correct':sum(c['correct'] for c in cases),'cases':cases})
    return groups
