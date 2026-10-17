"""Offline capture adapters. No model calls, source writes or execution-freeze bypass."""
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from evals.score import Scorer, exact
from evals.coverage.score import Scorer as CoverageScorer
from experiments.t32.score import score as literal_score
from experiments.t36.score import score as planner_score, match_fields, typed_equal
from experiments.t37.score import score as reviewed_planner_score
from .metrics import exact_load, outcome, unwrap, latency, aggregate, distribution
from .auxiliary import retrieval as retrieval_components, planning as planning_components, functional_smokes


class Reader:
    def __init__(self, root):
        self.root = root.resolve()
        self.hashes = {}

    def raw(self, path):
        path = path.resolve()
        name = path.relative_to(self.root).as_posix()
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if name in self.hashes and self.hashes[name] != digest:
            raise ValueError('input changed during measurement: ' + name)
        self.hashes[name] = digest
        return raw

    def read(self, path):
        return exact_load(self.raw(path))

    def verify(self):
        for name, digest in self.hashes.items():
            if hashlib.sha256((self.root/name).read_bytes()).hexdigest() != digest:
                raise ValueError('input changed: ' + name)


def expected_status(label):
    return label.get('expected', {}).get('status') or label.get('status') or label.get('outcome') or label.get('plan')


def normalize_record(reader, group, identifier, capture, metadata, label, score, job=None):
    row = {'group': group, 'case': identifier, 'capture': capture.relative_to(reader.root).as_posix(),
           'expected': expected_status(label), 'outcome': 'unscorable', 'legacy_score': metadata.get('score'),
           'values_correct': None, 'source_support_correct': None, 'rejected_gold_values': None,
           'validator_false_reject': 'not_adjudicated', 'latency': {'wall_ms': None, 'attempts': [], 'final': {'stages_ms': {}, 'calls': []}}}
    if not capture.exists():
        row['unscorable_reason'] = 'missing capture; remains in denominator'
        return row
    raw = reader.raw(capture)
    if metadata.get('report_sha256', metadata.get('response_sha256')) not in (None, hashlib.sha256(raw).hexdigest()):
        raise ValueError('recorded capture hash differs: ' + str(capture))
    if 'http_status' not in metadata and 'status' not in metadata:
        row['unscorable_reason'] = 'missing request outcome metadata; remains in denominator'
        return row
    try:
        code = metadata.get('http_status', metadata.get('status', 0))
        row['http_status'] = code
        if not raw and code == 0 and metadata.get('error'):
            row['outcome'] = 'system_error'
            row['system_error'] = 'recorded preflight/transport failure; no response'
            return row
        body = exact_load(raw)
        report = unwrap(body)
        row['latency'] = latency(body, metadata.get('wall_seconds', metadata.get('seconds')), job)
        rejected = (body.get('error') or {}).get('code') == 'answer_rejected'
        actual = report.get('answer', {}).get('status') if code == 200 else None
        message = (body.get('error') or {}).get('message','').removeprefix('invalid record: ')
        if code == 400 and (body.get('error') or {}).get('code') == 'invalid_request':
            if message.startswith('question needs clarification:'): actual = 'needs_clarification'
            if message.startswith(('aggregate question requires an unsupported corpus aggregation operation',
                                   'question does not support calculations across records')): actual = 'unsupported'
        scored = score(code, raw, report)
        row['rescored'] = scored
        row['values_correct'] = scored.get('all_fields_correct')
        fields = report.get('answer', {}).get('fields', {})
        gold = label.get('expected', {}).get('fields', label.get('values'))
        if code == 200 and actual == 'supported':
            if gold is not None:
                row['values_correct'] = exact({k:p['value'] for k,p in fields.items()}, gold)
            elif label.get('plan') == 'ready':
                names = match_fields((report.get('planning') or {}).get('plan', {}), label['fields'])
                row['values_correct'] = (names is not None and set(fields) == set(names) and all(
                    typed_equal(fields[n]['value'], e['value'], e['kind']) for n,e in zip(names,label['fields'])))
        row['source_support_correct'] = scored.get('source_support_correct', scored.get('citations_correct'))
        row['outcome'] = outcome(row['expected'], actual, scored['correct'], error=code != 200,
                                 rejected=rejected, request_decline=label.get('plan') in ('unsupported','needs_clarification'))
        if rejected:
            draft = report.get('unvalidated_draft')
            gold = label.get('expected', {}).get('fields', label.get('values'))
            if isinstance(draft, dict) and isinstance(draft.get('fields'), dict) and gold is not None:
                values = {k: p.get('value') for k, p in draft['fields'].items()}
                if not any(p.get('pointer') is not None and p.get('value') is None for p in draft['fields'].values()):
                    row['rejected_gold_values'] = exact(values, gold)
        if job:
            row['mode'] = job.get('mode')
            row['fallback_reason'] = job.get('fallback_reason')
    except (ValueError, KeyError, TypeError, AttributeError, StopIteration) as error:
        row['outcome'] = 'unscorable'
        row['unscorable_reason'] = type(error).__name__ + ': ' + str(error)
    return row


def frozen_suites(reader):
    root = reader.root
    roots = [('t10', root/'data/t10/20261014', 'dev'),
             ('t11', root/'data/t11/20261014-independent-fixed', 't11'),
             ('t14', root/'data/t14/20261014-coverage', 't14')]
    for task, run in [('t27','paired-v1'),('t28','replay-v1'),('t29','replay-v1'),('t30','replay-v1')]:
        roots.extend((task, root/f'data/{task}/{run}/{suite}', suite) for suite in ('t11','t14'))
    rows = []
    for task, folder, suite in roots:
        if not folder.exists():
            continue
        dataset = reader.read(root/({'dev':'evals/dataset.json','t11':'evals/independent/dataset.json','t14':'evals/coverage/dataset.json'}[suite]))
        # Never evaluate, expose or tune on the original holdout.
        cases = [c for c in dataset['cases'] if suite != 'dev' or c['split'] == 'dev']
        manifests = folder.rglob('queries.json' if suite == 'dev' else 'complete.json')
        for manifest in sorted(manifests):
            data = reader.read(manifest)
            if not isinstance(data, dict) or not isinstance(data.get('cases'), list):
                continue
            parent = manifest.parent
            documents = reader.read((parent if suite == 'dev' else folder)/'documents.json')
            scorer = (CoverageScorer if suite == 't14' else Scorer)(dataset, documents)
            indexed = {(r['case'], r.get('cache')): r for r in data['cases']}
            if len(indexed) != len(data['cases']):
                raise ValueError('duplicate measured requests: ' + str(manifest))
            for cache in (['cold-cache','warm-cache'] if suite == 'dev' else [None]):
                group = parent.relative_to(root).as_posix() + ('/'+cache if cache else '')
                for case in cases:
                    meta = indexed.get((case['id'],cache), {})
                    path = parent/meta.get('report_file', (cache+'-' if cache else '')+case['id']+'.json')
                    def score(code, raw, report, case=case):
                        if code != 200:
                            return {'correct': False}
                        result = scorer.case(case, report)
                        proof = bool(result['proofs']) and all(p['gold_source_overlap'] for p in result['proofs'].values())
                        result['source_support_correct'] = proof if case['expected']['status'] == 'supported' else None
                        result['correct'] = (result['answer_correct'] and report.get('validation', {}).get('mechanical_support') == 'passed'
                                             and (case['expected']['status'] != 'supported' or proof))
                        return result
                    rows.append(normalize_record(reader, group, case['id'], path, meta, case, score))
    return rows


def browser_literal_score(code, raw, report, label, docs):
    """T33–35's single-field browser contract, without importing archived runners."""
    view = exact_load(raw)
    fields = report.get('answer', {}).get('fields', {})
    name = next(iter(fields)) if len(fields) == 1 else '__missing__'
    expected = dict(label, values={name: label['value']})
    result = literal_score(code, view.get('raw_report','{}').encode(), expected, docs)
    spec = report.get('request', {}).get('fields', {}).get(name, {})
    ui = view.get('fields', [])
    result['correct'] &= (len(ui) == 1 and ui[0].get('name') == name and ui[0].get('kind') == label['kind']
                          and ui[0].get('value_text') == str(fields.get(name,{}).get('value'))
                          and spec.get('kind') == label['kind'] and report.get('planning',{}).get('plan',{}).get('status') == 'ready'
                          and view.get('outcome') == 'supported')
    return result


def pilots(reader):
    root = reader.root
    rows = []
    for task in range(32,38):
        folder = root/f'data/t{task}'/('pilot-v3' if task == 33 else 'pilot-v1')
        if not folder.exists():
            continue
        labels = reader.read(root/f'experiments/t{36 if task >= 36 else 32}/gold.json')
        if task in (34,35):
            # Frozen SELECTED in each retained source.zip, not inferred from successes.
            labels = {key: labels[key] for key in ('pressure_revision','long_exact_record','unknown_count','pdf_correction')}
        browser = reader.read(root/f'experiments/t{task}/browser-gold.json') if task in (33,34,35) else {}
        labels = {**labels, **browser}
        for arm in sorted(folder.iterdir()):
            suffix = '.outcome.json' if task == 37 else '.row.json'
            if not arm.is_dir() or not any(arm.glob('*'+suffix)) or arm.name == 'corpus':
                continue
            docs_path = folder/(('minilm' if arm.name.startswith('minilm') else 'nomic-v1.5') if task == 32 else 'corpus')/'documents.json'
            if task == 37:
                captured = [reader.read(p)['document'] for p in (folder/'corpus').glob('*.document.json')]
                docs = {d['document_id']:d for d in captured}
            else:
                docs = reader.read(docs_path)
            if not docs or any(d.get('document_id') != name or 'chunks' not in d for name,d in docs.items()):
                raise ValueError('invalid document catalog for ' + str(arm))
            for identifier, label in labels.items():
                path = arm/(identifier+'.response.json')
                meta_path = arm/(identifier+suffix)
                meta = reader.read(meta_path) if meta_path.exists() else {}
                def score(code, raw, report, identifier=identifier, label=label):
                    if task >= 36:
                        result = planner_score(code, raw, label, docs)
                        if task == 37:
                            reviewed = reviewed_planner_score(identifier, code, raw, label, docs)
                            result['reviewed_correct'] = reviewed['correct']
                            result['review_exception'] = reviewed['correction']
                        return result
                    if identifier in browser:
                        return browser_literal_score(code, raw, report, label, docs)
                    if code != 200:
                        # Rejection diagnostics can contain evidence previews rather
                        # than the full records required by the legacy stage scorer.
                        return {'correct': False}
                    result = literal_score(code, raw, label, docs)
                    result['source_support_correct'] = result['citations']['complete']
                    return result
                job_path = arm/(identifier+'.job.json')
                rows.append(normalize_record(reader, arm.relative_to(root).as_posix(), identifier, path, meta, label,
                                              score, reader.read(job_path) if job_path.exists() else None))
    return rows


def stage_table(rows):
    stages = defaultdict(list)
    attempts = 0
    for row in rows:
        measured = row['latency']
        stages['request_wall_ms'].append(measured['wall_ms'])
        source = measured['attempts'] or [measured['final']]
        attempts += len(source)
        for attempt in source:
            stages['unattributed_core_ms'].append(attempt.get('unattributed_core_ms'))
            for name in ('queue_ms','activation_ms','work_ms'):
                stages[name].append(attempt.get(name))
            for name, value in attempt['stages_ms'].items():
                stages[name].append(value)
            for call in attempt['calls']:
                stages[call['stage']+'_call_ms'].append(call.get('elapsed_ms'))
                stages[call['stage']+'_inference_ms'].append(call['stages_ms'].get('inference'))
                for tokens in ('input_tokens','output_tokens'):
                    stages[call['stage']+'_'+tokens].append(call.get(tokens))
    return {'attempts_or_legacy_requests': attempts, 'observations': {k: distribution(v) for k,v in sorted(stages.items())}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--output', type=Path, required=True, help='new report directory; existing output is refused')
    parser.add_argument('--compact', action='store_true', help='publish aggregate timings and case outcomes; full per-request timings remain reproducible from hashed captures')
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('output already exists; use a fresh directory')
    reader = Reader(args.root)
    rows = frozen_suites(reader) + pilots(reader)
    auxiliary = {'retrieval': retrieval_components(reader), 'planning': planning_components(reader),
                 'functional': functional_smokes(reader)}
    groups = defaultdict(list)
    for row in rows:
        groups[row['group']].append(row)
    summary = {name: {**aggregate(records), 'latency': stage_table(records)} for name, records in sorted(groups.items())}
    # These are capture families, not an assumption that every file is a scored question.
    # Explicitly inventory unsupported auxiliary formats without parsing private stores.
    excluded = ['data/t02–t09: pre-evaluation smoke/worker captures',
                'data/t23,t24,t31 retrieval and t26/t27/t28 planner trials: separately rescored component tracks, never added to answer denominators',
                'data/t26,t27,t28 source/worker smokes and t36 development planner cases: separately rescored narrower functional checks; no independent semantic-quality labels',
                'operational/normal-library captures and original holdout: deliberately excluded']
    reader.verify()
    report = {'version': 'measurement-v1', 'questions_are_clustered': True,
              'interval_note': 'Wilson intervals use distinct questions within each arm/pass; not independent across groups. These observed regression sets do not establish population quality.',
              'outcome_note': 'Strict frozen labels/proofs; reviewed exceptions remain separate. A matching rejected draft is not adjudicated validator error.',
              'latency_note': 'Inclusive stages and child calls overlap. Do not sum stage medians. Missing observations remain null; failures remain in request denominators.',
              'coverage_gaps_and_exclusions': excluded, 'requests': len(rows), 'groups': summary, 'records': rows, 'components': auxiliary,
              'inputs_sha256': dict(sorted(reader.hashes.items()))}
    report['implementation_sha256'] = {p.relative_to(reader.root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                       for p in sorted((reader.root/'evals/measurement').glob('*.py'))}
    if args.compact:
        report['records'] = [{k:v for k,v in row.items() if k not in ('rescored','legacy_score','latency')} | {
            'strict_correct': (row.get('rescored') or {}).get('correct'),
            'frozen_answer_correct': (row.get('rescored') or {}).get('answer_correct'),
            'reviewed_correct': (row.get('rescored') or {}).get('reviewed_correct'),
            'review_exception': (row.get('rescored') or {}).get('review_exception'),
            'legacy_answer_correct': (row.get('legacy_score') or {}).get('answer_correct'),
            'wall_ms': row['latency']['wall_ms'],
        } for row in rows]
        report['compact'] = True
    args.output.mkdir(parents=True)
    (args.output/'measurement.json').write_text(json.dumps(report, indent=2, default=str)+'\n', encoding='utf-8')
    lines = ['# Historical outcome matrix', '', report['interval_note'], '', report['outcome_note'], '',
             '| Arm/pass | N | Answer correct | Answer wrong | Abstain correct | Abstain missed | Other | Correct 95% interval | Median / p95 seconds |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |']
    for name, group in summary.items():
        counts = group['outcomes']; ci = group['correct_wilson95']; duration = group['wall_ms']
        timing = 'unknown' if duration['median'] is None else f"{duration['median']/1000:.2f} / {duration['p95']/1000:.2f}"
        values = [counts[k] for k in ('answered_correct','answered_wrong','abstained_correct','abstained_missed')]
        lines.append('| '+name+' | '+str(group['questions'])+' | '+' | '.join(map(str,values))+f" | {group['questions']-sum(values)} | {ci[0]:.1%}–{ci[1]:.1%} | {timing} |")
    lines += ['', 'Coverage gaps / exclusions:', ''] + ['- '+s for s in excluded]
    (args.output/'measurement.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps({'requests':len(rows),'groups':len(groups),'hashed_inputs':len(reader.hashes),
                      'unscorable':sum(r['outcome']=='unscorable' for r in rows), 'output':str(args.output)}))


if __name__ == '__main__':
    main()
