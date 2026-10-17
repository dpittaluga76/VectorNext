"""Post-run diagnostic supplement; never changes frozen correctness or gates.

The frozen attribution treated every error as infrastructure and discarded prose
alignment gaps. This supplement preserves it and reports conservative unknowns.
All exposed-candidate outputs are aggregate-only.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

from evals.measurement.attribution import attribute
from evals.measurement.capture_grounding import prose_coordinates
from evals.measurement.families import PRIMARY, load
from evals.measurement.internal_attribution import inventory_for_keys
from evals.measurement.internal_runtime import context, save
from evals.measurement.metrics import distribution


def error_kind(destination, job):
    done = load(destination/'finished.json')
    if done['state'] == 'ingestion_failed':
        return 'ingestion_admission_failure'
    value = (job.get('result') or {}).get('error') or job.get('error')
    submission = destination/'submission.raw.json'
    if not job and submission.exists():
        value = load(submission).get('error')
    text = json.dumps(value)
    if 'frozen string-field instruction' in text:
        return 'benchmark_string_plan_contract'
    if 'unsupported corpus aggregation' in text:
        return 'pre_inference_aggregation_guard'
    if 'automatic planning does not support calculations' in text:
        return 'planner_unsupported_operation'
    return 'other_or_unobserved_error'


def gap_count(ctx, evidence):
    if ctx['descriptor']['format'] == 'json':
        return 0
    b, d = ctx['binding'], ctx['descriptor']
    return sum(len(prose_coordinates(ctx['text'], d['review_text_sha256'],
        d['original_sha256'], e, ctx['snapshot'], b['document_id'], b['revision'])['alignment_gaps'])
        for e in evidence)


def conservative_support(value, gaps):
    # An established complete proof stays true even if unrelated spans cannot
    # align. Incomplete alignment cannot establish that evidence is absent.
    return None if value is False and gaps else value


def oracle_reason(row):
    reason = row.get('reason') or ''
    known = {'planning_unavailable','gold_fields_not_applicable','stress_oracle_not_defined',
        'ingestion_failed','gold_evidence_not_reconstructable','identical_to_automatic_fields'}
    if reason in known:
        return reason
    if 'did not finish normally' in reason:
        return 'generation_did_not_finish_normally'
    if 'token' in reason.lower() and ('budget' in reason.lower() or 'exceed' in reason.lower()):
        return 'input_token_budget'
    return 'other_failure_private_detail_retained'


def revised_attribution(root, package, original):
    cases = {c['case_id']:c for c in load(package/'development/gold.json')['cases']}
    rows, amendments = [], []
    for old in original['cases']:
        row = dict(old); cid = row['case_id']; case = cases[cid]
        dest = root/'answers/development/v2/five'/cid
        job = load(dest/'job.json') if (dest/'job.json').exists() else {}
        if row['system_error']:
            row['error_category'] = error_kind(dest, job)
            # Known benchmark/request refusals are not infrastructure failures.
            row['system_error'] = row['error_category'] == 'other_or_unobserved_error'
        ctx = context(package, root, 'development', case['document'])
        if ctx['binding']['state'] == 'committed' and case['format'] != 'json':
            inventory = load(root/'ingestion'/ctx['binding']['document_id']/'evidence.json')
            view = job.get('result') or {}
            report = json.loads(view['raw_report']) if view.get('raw_report') else {}
            retrieval = report.get('retrieval')
            if isinstance(retrieval, dict) and 'results' in retrieval:
                evidence = inventory_for_keys(ctx, inventory, [r['key'] for r in retrieval['results']])
                if evidence is not None:
                    row['candidate_alignment_gaps'] = gap_count(ctx, evidence)
                    row['candidate_support'] = conservative_support(row.get('candidate_support'), row['candidate_alignment_gaps'])
            for attempt in job.get('attempts', []):
                for op in attempt.get('operations', []):
                    ref = (op.get('model_measurement') or {}).get('evaluation_capture', {}).get('rpc')
                    if op.get('operation') != 'answer' or not ref:
                        continue
                    req = root/'rpc/interactive'/ref/'request.json'
                    if req.exists():
                        row['selected_alignment_gaps'] = gap_count(ctx, load(req)['input']['evidence'])
                        row['selected_support'] = conservative_support(row.get('selected_support'), row['selected_alignment_gaps'])
        changes = [key for key in ('system_error','candidate_support','selected_support') if row.get(key) != old.get(key)]
        if changes:
            amendments.append({'case_id':cid, 'changed_diagnostics':changes})
        row.update(attribute(row)); rows.append(row)
    return {'flag_counts':dict(Counter(f for r in rows for f in r['flags'])),
        'unobserved_counts':dict(Counter(k for r in rows for k in r['unobserved'])),
        'amended_development_cases':amendments,
        'alignment_gap_cases':{stage:sum(r.get(stage+'_alignment_gaps',0)>0 for r in rows) for stage in ('candidate','selected')},
        'unknown_support_after_alignment':{stage:sum(r.get(stage+'_alignment_gaps',0)>0 and r.get(stage+'_support') is None for r in rows) for stage in ('candidate','selected')},
        'primary_scores_changed':False, 'independent_proof_review':False}


def arm_details(root, package, scores, split, arm):
    gold = {c['case_id']:c for c in load(package/split/'gold.json')['cases']}
    questions = {c['case_id']:c for c in load(package/split/'questions.json')}
    value = scores[split][arm]; counts = Counter(); role_counts = Counter()
    formats = {}; states = Counter(); solved_times = []; outcome_times = defaultdict(list)
    for row in value['cases']:
        cid = row['case_id']; case = gold[cid]; dest = root/'answers'/split/'v2'/arm/cid
        done = load(dest/'finished.json'); states[done['state']] += 1
        if case['tier'] != PRIMARY:
            continue
        job = load(dest/'job.json') if (dest/'job.json').exists() else {}
        if row['outcome'] == 'system_error': counts[error_kind(dest,job)] += 1
        if row.get('mapping_ok') is False: counts['unlisted_field_mapping'] += 1
        if row['review_queue']: counts['sensitivity_queue_cases_unreviewed'] += 1
        role_counts.update(r['diagnostic'] for r in row['roles'].values())
        outcome_times[row['outcome']].append(done.get('wall_ms'))
        if row['correct']: solved_times.append(done.get('wall_ms'))
        f = formats.setdefault(case['format'], {'n':0,'positive':0,'negative':0,'correct':0,'families':Counter()})
        f['n'] += 1; f['positive' if case['expected']=='supported' else 'negative'] += 1
        f['correct'] += row['correct'] is True; f['families'][questions[cid]['family']] += 1
    for f in formats.values():
        sizes = list(f.pop('families').values()); f.update(families=len(sizes),largest_cluster=max(sizes),cluster_sizes=dict(Counter(sizes)))
    return {'completion_states_all_tiers':dict(states),'primary_error_and_format_counts':dict(counts),
        'primary_role_diagnostics':dict(role_counts),'primary_by_format':formats,
        'strict_correct_latency_ms':distribution(solved_times),
        'primary_latency_by_outcome_ms':{k:distribution(v) for k,v in outcome_times.items()}}


def resource_details(root):
    switch = load(root/'controls/gemma/synthetic-warmup/started.json')['started_unix']
    groups = {'nuextract':[], 'gemma':[]}; ram = {m:defaultdict(list) for m in groups}
    for line in (root/'resources.jsonl').read_text(encoding='utf8').splitlines():
        r = json.loads(line); model = 'gemma' if r['unix'] >= switch else 'nuextract'
        if 'gpu' in r:
            parts = list(map(float,r['gpu'].split(','))); groups[model].append(parts)
        for line in r.get('containers','').splitlines():
            c = json.loads(line); m = re.match(r'([\d.]+)([KMG]iB)',c['MemUsage'])
            if m: ram[model][c['Name']].append(float(m[1])*{'KiB':1/1024,'MiB':1,'GiB':1024}[m[2]])
    return {model:{'samples':len(rows),'whole_gpu_peak_mib':max(r[0] for r in rows),
        'minimum_sampled_headroom_mib':min(r[1]-r[0] for r in rows),
        'gpu_used_mib':distribution(r[0] for r in rows),
        'container_ram_peak_mib':{k:max(v) for k,v in ram[model].items()},
        'windows_paging_measured':False} for model,rows in groups.items()}


def build(root, package):
    scores=load(root/'scores.json'); oracles=load(root/'oracle-scores.json')
    result={'version':'post_run_diagnostics_v1','primary_scoring_unchanged':True,
        'diagnostic_amendment':'Known request/format refusals are separated from infrastructure; unresolved prose alignment cannot prove missing evidence.',
        'arms':{split:{arm:arm_details(root,package,scores,split,arm) for arm in scores[split] if arm!='comparisons'} for split in ('development','exposed_candidates')},
        'attribution':revised_attribution(root,package,load(root/'attribution.json')),
        'resources':resource_details(root),'oracle_states':{}}
    for model,variants in oracles.items():
        result['oracle_states'][model]={}
        for variant,v in variants.items():
            primary=[r for r in v['cases'] if r['tier']==PRIMARY]
            result['oracle_states'][model][variant]={'all_tier_states':dict(Counter(r['state'] for r in v['cases'])),
                'all_tier_reasons':dict(Counter(oracle_reason(r) for r in v['cases'] if r['state']!='captured')),
                'primary_states':dict(Counter(r['state'] for r in primary)),
                'captured_primary_on_correct':sum(r['validator_on_correct'] for r in primary),
                'captured_primary_off_correct':sum(r['validator_off_correct'] for r in primary)}
    base={r['case_id']:r for r in scores['development']['five']['cases'] if r['tier']==PRIMARY}
    result['public_development_paired_changes']={arm:[{'case_id':r['case_id'],'baseline_correct':base[r['case_id']]['correct'],'candidate_correct':r['correct']} for r in scores['development'][arm]['cases'] if r['case_id'] in base and r['correct']!=base[r['case_id']]['correct']] for arm in ('two','facet')}
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('root','package','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();save(a.output,build(a.root,a.package))


if __name__=='__main__':main()
