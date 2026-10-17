"""Development-only family trace, aggregate custodian receipt and cluster statistics.

No inference, network, sealed reader, source edits or replacement acquisition.
The receipt validates an attestation; it cannot verify private screening itself.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
import re
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
PRIMARY = 'primary_direct_extraction'
FORMATS = ('txt', 'pdf', 'json')
LABELS = ('supported', 'negative')
TIERS = ('A', 'B', 'C', 'U')
DEFECTS = ('source_content_unavailable', 'question_incomplete',
           'premise_or_entity_ambiguous', 'unit_or_format_ambiguous',
           'scope_or_period_ambiguous', 'requires_derivation')
SEED = 't39-d6-reserve-20261017-v1'
POLICIES = ('families-v1.3.md', 'tiers-v1.1.md', 'typed-facts-v1.1.md',
            'answer-format-v1.1.txt', 'table-context-v1.2.md')


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    with path.open('xb') as stream:
        stream.write(encoded(value))


def load(path):
    # Duplicate JSON keys must not hide an extra receipt field or altered count.
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise ValueError('Duplicate JSON key')
            obj[key] = value
        return obj
    return json.loads(path.read_bytes(), object_pairs_hook=pairs)


def size_band(length):
    if type(length) is not int or length < 0:
        raise ValueError('Invalid supplied-text byte count')
    return 'small' if length <= 4096 else 'medium' if length <= 16384 else 'large'


def established(row):
    return row['confidence'] in ('A', 'B') and bool(row['family_key'])


def counts(rows):
    result = {fmt: {label: 0 for label in LABELS} for fmt in FORMATS}
    for row in rows:
        result[row['format']][row['label']] += 1
    return result


def clusters(rows):
    known = Counter(r['family_key'] for r in rows if established(r))
    return {'cases': len(rows), 'established_cases': sum(known.values()),
            'candidate_or_unknown_cases': sum(not established(r) for r in rows),
            'families': len(known), 'largest_cluster': max(known.values(), default=0),
            'size_distribution': dict(sorted(Counter(known.values()).items())),
            'memberships': dict(sorted(known.items()))}


def summary(rows):
    primary = [r for r in rows if r['tier'] == PRIMARY]
    return {'all_exposed_cases': len(rows), 'primary_cases': len(primary),
            'primary_by_format_label': counts(primary),
            'primary_confidence': dict(sorted(Counter(r['confidence'] for r in primary).items())),
            'exposed_confidence': dict(sorted(Counter(r['confidence'] for r in rows).items())),
            'primary_clusters': clusters(primary),
            'primary_clusters_by_format': {f: clusters([r for r in primary if r['format'] == f])
                                           for f in FORMATS},
            'cross_split_verified_cases': 0, 'custodian_status': 'pending',
            'collisions': None, 'replacements_drawn': 0}


def build_ledger(audit, gold, registry, source_metadata):
    if audit['opened_proposal_split'] != 'development':
        raise ValueError('Development audit required')
    cases = {c['n']: c for c in audit['cases']}
    if len(cases) != len(audit['cases']) or len({c['case_id'] for c in gold['cases']}) != len(cases):
        raise ValueError('Duplicate or mismatched development cases')
    table_traces = {}
    for trace in registry['tables']:
        if trace['tier'] not in TIERS or not trace['family_key'].startswith('company:'):
            raise ValueError('Invalid company trace')
        for n in trace['cases']:
            if n in table_traces:
                raise ValueError('Duplicate table trace')
            table_traces[n] = trace
    if set(table_traces) != {c['number'] for c in gold['cases'] if c['format'] == 'json'}:
        raise ValueError('Trace must cover every development table case')
    rows = []
    for g in sorted(gold['cases'], key=lambda c: c['number']):
        a = cases[g['number']]
        req = a['request']
        raw = a['source_text'].encode('utf-8')
        if (a['id'] != g['case_id'] or req['split'] != 'development' or
                a['label']['split'] != 'development' or
                req['document'] != g['document'] or req['format'] != g['format'] or
                a['document_sha256'] != g['document_sha256'] or
                digest(raw) != g['source_text_sha256']):
            raise ValueError('Source/gold binding changed')
        row = {k: g[k] for k in ('number', 'case_id', 'document', 'document_sha256',
                                'source_text_sha256', 'format', 'tier', 'pending_decisions')}
        row.update(source=req['source'], structure=req['structure'],
                   label='supported' if g['expected'] == 'supported' else 'negative',
                   original_label='supported' if g['original_expected'] == 'supported' else 'negative',
                   supplied_text_bytes=len(raw), size_band=size_band(len(raw)),
                   report_year=None, company_year_key=None, aliases=[],
                   cross_split_status='pending_custodian', lineage_status='custodian_check_required')
        if g['number'] in table_traces:
            t = table_traces[g['number']]
            row.update(family_key=t['family_key'], family_type='company',
                       confidence=t['tier'], source_identity=t['filer'],
                       report_year=t['report_year'], aliases=t['aliases'],
                       company_year_key=(t['family_key'] + ':FY' + t['report_year'])
                       if t['report_year'] else None)
            records = json.loads(raw)['records']
            matches = []
            for needle in t['needles']:
                refs = []
                for i, record in enumerate(records):
                    if 'cells' in record:
                        refs.extend(f'/records/{i}/cells/{j}' for j, v in enumerate(record['cells'])
                                    if needle in v)
                    elif needle in record.get('text', ''):
                        refs.append(f'/records/{i}/text')
                if not refs:
                    raise ValueError(f'Trace clue missing from development case {g["number"]}')
                matches.append({'clue': needle, 'source_pointers': refs})
            row['evidence'] = {'method': 'public_report_match' if t['tier'] == 'A'
                               else 'supplied_attribution' if t['tier'] == 'B' else 'public_search_lead',
                               'url': t['url'], 'locator': t['locator'], 'matches': matches,
                               'limitation': t['limitation'], 'checked_date': registry['date']}
        elif req['source'] == 'squad':
            if not req['family'].startswith('squad:'):
                raise ValueError('Missing upstream article family')
            title = req['family'].split(':', 1)[1]
            row.update(family_key='article:wikipedia:' + title, family_type='article', confidence='B',
                       source_identity=title, evidence={
                           'method': 'pinned_upstream_article_identity',
                           'upstream': source_metadata['squad-dev.json'],
                           'original_id': a['label']['original_id'],
                           'url': 'https://en.wikipedia.org/wiki/' + quote(title),
                           'limitation': 'Dataset article identity; no claim that current web text equals the frozen paragraph or that all cross-article reuse is resolved.'})
        elif req['source'] == 'qasper':
            paper = req['family'].removeprefix('qasper:')
            if not re.fullmatch(r'\d{4}\.\d{4,5}(v\d+)?', paper):
                raise ValueError('Missing upstream paper family')
            paper = re.sub(r'v\d+$', '', paper)
            row.update(family_key='paper:arxiv:' + paper, family_type='paper', confidence='B',
                       source_identity=paper, evidence={
                           'method': 'pinned_upstream_paper_identity',
                           'upstream': source_metadata['qasper-dev.json'],
                           'original_id': a['label']['original_id'],
                           'url': 'https://arxiv.org/abs/' + paper,
                           'limitation': 'Paper identity; unknown alternate-publication aliases require custodian review.'})
        else:
            raise ValueError('Unreviewed source kind')
        rows.append(row)
    return {'version': 't39-d6-family-ledger-v1.3', 'approved_for_execution': False,
            'sealed_content_opened': False, 'model_outputs_used': False,
            'base_manifest_sha256': audit['manifest_sha256'], 'cases': rows,
            'summary': summary(rows)}


def handoff(ledger):
    groups = defaultdict(list)
    for row in ledger['cases']:
        if row['family_key']:
            groups[row['family_key']].append(row)
    return {'version': 't39-d6-custodian-input-v1.3', 'custodian': 'Daniel Pittaluga / Architect',
            'ledger_sha256': digest(encoded(ledger)), 'policy_hashes': ledger['policy_hashes'],
            'sealed_candidate_count': 60,
            'exposure_cases': len(ledger['cases']),
            'unknown_exposure_cases': sum(not established(r) for r in ledger['cases']),
            'families': [
                {'key': key, 'type': rs[0]['family_type'],
                 'names_and_aliases': sorted({name for r in rs for name in
                                             [r['source_identity'], *r['aliases']]}),
                 'formats': sorted({r['format'] for r in rs}),
                 'confidence_counts': dict(sorted(Counter(r['confidence'] for r in rs).items())),
                 'exposed_cases': len(rs), 'primary_cases': sum(r['tier'] == PRIMARY for r in rs)}
                for key, rs in sorted(groups.items())]}


def exact_keys(obj, keys):
    if not isinstance(obj, dict) or set(obj) != set(keys):
        # Do not echo unapproved fields: they may contain sealed information.
        raise ValueError('Unexpected or missing fields in aggregate receipt')


def number(value):
    if type(value) is not int or value < 0:
        raise ValueError('Aggregate counts must be nonnegative integers')
    return value


def validate_receipt(receipt, packet):
    exact_keys(receipt, ('version', 'handoff_sha256', 'policy_hashes', 'custodian',
                         'candidate_count', 'candidate_by_format', 'confidence_counts',
                         'd3_counts', 'd4_records_checked', 'd5_tables_checked',
                         'primary_by_format_label', 'established_primary_family_count',
                         'colliding_development_families',
                         'unresolved_development_families', 'colliding_sealed_cases',
                         'colliding_sealed_families', 'source_only_screening',
                         'lineage_review_complete', 'private_audit_retained', 'model_outputs_used'))
    if (receipt['version'] != 't39-d6-custodian-receipt-v1.3' or
            receipt['handoff_sha256'] != digest(encoded(packet)) or
            receipt['policy_hashes'] != packet['policy_hashes'] or
            receipt['custodian'] != packet['custodian']):
        raise ValueError('Receipt identity/policy mismatch')
    for key in ('source_only_screening', 'lineage_review_complete', 'private_audit_retained'):
        if receipt[key] is not True:
            raise ValueError('Custodian check incomplete')
    if receipt['model_outputs_used'] is not False:
        raise ValueError('Source-only screening required')
    n = number(receipt['candidate_count'])
    if n != packet['sealed_candidate_count']:
        raise ValueError('Every sealed candidate must be accounted for')
    for field, keys in [('candidate_by_format', FORMATS), ('confidence_counts', TIERS),
                        ('d3_counts', ('primary', *DEFECTS))]:
        exact_keys(receipt[field], keys)
        if sum(number(v) for v in receipt[field].values()) != n:
            raise ValueError('Aggregate partition does not account for candidates')
    if (number(receipt['d4_records_checked']) != n or
            number(receipt['d5_tables_checked']) != receipt['candidate_by_format']['json']):
        raise ValueError('All candidates require D4 and all tables require D5 checks')
    exact_keys(receipt['primary_by_format_label'], FORMATS)
    total = 0
    for fmt in FORMATS:
        part = receipt['primary_by_format_label'][fmt]
        exact_keys(part, LABELS)
        size = sum(number(v) for v in part.values())
        if size > receipt['candidate_by_format'][fmt]:
            raise ValueError('Primary format count exceeds candidate count')
        total += size
    if total != receipt['d3_counts']['primary']:
        raise ValueError('Primary quotas do not match screened membership')
    if number(receipt['established_primary_family_count']) > total:
        raise ValueError('More primary families than primary cases')
    unknown_cases = receipt['confidence_counts']['C'] + receipt['confidence_counts']['U']
    if total > unknown_cases and receipt['established_primary_family_count'] == 0:
        raise ValueError('Established primary cases require a family')
    allowed = {f['key'] for f in packet['families']}
    for field in ('colliding_development_families', 'unresolved_development_families'):
        keys = receipt[field]
        if (not isinstance(keys, list) or any(type(k) is not str for k in keys) or
                len(keys) != len(set(keys)) or not set(keys) <= allowed):
            raise ValueError('Only unique development family keys may be disclosed')
    case_count = number(receipt['colliding_sealed_cases'])
    family_count = number(receipt['colliding_sealed_families'])
    traced = receipt['confidence_counts']['A'] + receipt['confidence_counts']['B']
    if not (0 <= family_count <= case_count <= traced):
        raise ValueError('Invalid collision counts')
    if bool(case_count) != bool(receipt['colliding_development_families']) or bool(case_count) != bool(family_count):
        raise ValueError('Collision keys/counts disagree')
    return receipt


def reconcile(ledger, packet, receipt):
    if packet != handoff(ledger):
        raise ValueError('Handoff no longer binds this ledger')
    validate_receipt(receipt, packet)
    collisions = set(receipt['colliding_development_families'])
    unresolved = set(receipt['unresolved_development_families'])
    primary = [r for r in ledger['cases'] if r['tier'] == PRIMARY]
    removed = [r for r in primary if r['family_key'] in collisions]
    unknown = [r for r in primary if r not in removed and
               (not established(r) or r['family_key'] in unresolved)]
    retained = [r for r in primary if r not in removed and r not in unknown]
    sealed_unknown = receipt['confidence_counts']['C'] + receipt['confidence_counts']['U']
    all_lost = removed + unknown
    combined = counts(retained)
    for fmt in FORMATS:
        for label in LABELS:
            combined[fmt][label] += receipt['primary_by_format_label'][fmt][label]
    total = sum(sum(part.values()) for part in combined.values())
    negative = sum(part['negative'] for part in combined.values())
    return {'version': 't39-d6-reconciliation-v1.3', 'approved_for_execution': False,
            'receipt_sha256': digest(encoded(receipt)),
            'collision_diagnostics': [{'case_id': r['case_id'], 'prior_tier': r['tier']}
                                      for r in ledger['cases'] if r['family_key'] in collisions],
            'primary_collision_losses': counts(removed),
            'primary_unknown_provenance_losses': counts(unknown),
            'primary_total_losses': counts(all_lost),
            'retained_primary': [r['case_id'] for r in retained],
            'retained_counts': counts(retained), 'clusters': clusters(retained),
            'sealed_unknown_cases': sealed_unknown,
            'cross_split_verified_cases': len(retained) if not sealed_unknown else 0,
            'claim': 'noncollision_against_established_sealed_portion_only' if sealed_unknown
                     else 'retained_development_families_noncolliding_by_custodian_attestation',
            'whole_benchmark_independence': not sealed_unknown and not unknown and
                 not packet['unknown_exposure_cases'] and not unresolved,
            'quota_targets': {'total_primary': [150, 300], 'negative_fraction': [.25, .30],
                              'sealed_fraction_min': .30, 'families_per_split_min': 20,
                              'cases_per_format_min': 20, 'table_cases_min': 20},
            'achieved_provisional_quotas': {
                'total_primary': total, 'negative_cases': negative,
                'negative_fraction': negative / total if total else None,
                'sealed_primary': receipt['d3_counts']['primary'],
                'sealed_fraction': receipt['d3_counts']['primary'] / total if total else None,
                'by_format_label': combined, 'development_families': clusters(retained)['families'],
                'established_sealed_primary_families': receipt['established_primary_family_count'],
                'unresolved_provenance_prevents_final_claim': bool(sealed_unknown or unknown or unresolved)},
            'replacements_drawn': 0,
            'remaining_gates': ['D7', 'pending_gold', 'runtime_and_scorer_integration', 'execution_freeze']}


def cluster_interval(rows, resamples=10000):
    """Case-weighted family bootstrap. Call separately for each arm/pass/outcome."""
    if type(resamples) is not int or resamples < 1000 or not rows:
        raise ValueError('Nonempty outcomes and >=1000 resamples required')
    if len({r['case_id'] for r in rows}) != len(rows):
        raise ValueError('Repeated cases are not independent observations')
    groups = defaultdict(list)
    for r in rows:
        if not established(r) or type(r['correct']) is not bool:
            raise ValueError('Established families and explicit binary outcomes required')
        groups[r['family_key']].append(int(r['correct']))
    point = sum(sum(v) for v in groups.values()) / len(rows)
    if len(groups) < 2:
        return {'n': len(rows), 'families': len(groups), 'estimate': point,
                'ci95': None, 'reason': 'fewer_than_two_families'}
    rng = random.Random(3906)
    keys = sorted(groups)
    samples = []
    for _ in range(resamples):
        sample = [v for key in rng.choices(keys, k=len(keys)) for v in groups[key]]
        samples.append(sum(sample) / len(sample))
    samples.sort()
    return {'n': len(rows), 'families': len(keys), 'estimate': point,
            'ci95': [samples[math.ceil(q * len(samples)) - 1] for q in (.025, .975)],
            'method': 'case_weighted_family_percentile_bootstrap', 'seed': 3906,
            'resamples': resamples}


def reserve_order(rows, stratum, excluded_families):
    """Pure ordering helper; does not acquire, inspect, or draw actual candidates."""
    if len({r['case_id'] for r in rows}) != len(rows) or len(stratum) != 6:
        raise ValueError('Unique reserve IDs and six-field strata required')
    eligible = []
    for r in rows:
        if (r['split'] != 'development_reserve' or not established(r) or
                r['family_key'] in excluded_families or r['noncollision_checked'] is not True or
                r['same_defect_screen_passed'] is not True or r['previously_inspected'] is not False):
            raise ValueError('Reserve contains ineligible/unverified material')
        actual = [r[k] for k in ('source', 'original_label', 'format', 'structure', 'question_type')]
        actual.append(size_band(r['supplied_text_bytes']))
        if actual == stratum:
            eligible.append(r)
    payload = json.dumps(stratum, ensure_ascii=False, separators=(',', ':'))
    return sorted((r['case_id'] for r in eligible),
                  key=lambda key: (digest((SEED + '\n' + payload + '\n' + key).encode('utf-8')), key))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    build = sub.add_parser('build')
    build.add_argument('--audit', type=Path, required=True)
    build.add_argument('--proposal', type=Path, required=True)
    build.add_argument('--output', type=Path, required=True)
    check = sub.add_parser('check-receipt')
    for name in ('ledger', 'handoff', 'receipt', 'output'):
        check.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'check-receipt':
        result = reconcile(load(args.ledger), load(args.handoff), load(args.receipt))
        save(args.output, result)
        print('Aggregate receipt validated; review gates remain open.')
        return
    from .audit_labels import verified_input
    audit, verified = verified_input(args.audit, args.proposal)
    requests = load(args.proposal / 'development/requests.json')
    if isinstance(requests, dict):
        requests = requests['requests']
    by_id = {r['case_id']: r for r in requests}
    if any(by_id.get(c['id']) != c['request'] for c in audit['cases']):
        raise ValueError('Audit request metadata differs from verified proposal')
    gold_path = ROOT / 'docs/reports/t39-d4-gold-candidate-v1.1.json'
    registry_path = ROOT / 'evals/measurement/table-families-v1.3.json'
    metadata = {s['file']: s for s in load(ROOT / 'evals/measurement/public-sources.json')['sources']}
    ledger = build_ledger(audit, load(gold_path), load(registry_path), metadata)
    ledger['inputs'] = {'source_audit_sha256': digest(args.audit.read_bytes()),
                        'gold_sha256': digest(gold_path.read_bytes()),
                        'table_registry_sha256': digest(registry_path.read_bytes()),
                        'builder_sha256': digest(Path(__file__).read_bytes()),
                        'verified_development_members': verified}
    ledger['policy_hashes'] = {p: digest((ROOT / 'evals/measurement' / p).read_bytes()) for p in POLICIES}
    args.output.mkdir(parents=True, exist_ok=False)
    save(args.output / 'family-ledger.json', ledger)
    save(args.output / 'custodian-input.json', handoff(ledger))
    print(json.dumps(ledger['summary']))


if __name__ == '__main__':
    main()
