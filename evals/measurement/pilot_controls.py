"""Offline D7 pairing audit and closed-book matching; never calls a model."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from .audit_labels import verified_input
from .families import PRIMARY, encoded, load, save
from .typed_facts import floor, permitted_values

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def unique(rows, key):
    result = {r[key]: r for r in rows}
    if len(result) != len(rows):
        raise ValueError('Duplicate case identity')
    return result


def control_messages(question):
    """Only the original question enters the user turn; no gold-dependent inputs."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError('Nonempty original question required')
    return [{'role': 'system', 'content': (HERE / 'closed-book-v1.4.txt').read_text(encoding='utf-8')},
            {'role': 'user', 'content': question}]


def audit_pairing(audit, gold, ledger, tiers):
    if audit['opened_proposal_split'] != 'development':
        raise ValueError('Development-only input required')
    source = unique(audit['cases'], 'id')
    facts = unique(gold['cases'], 'case_id')
    families = unique(ledger['cases'], 'case_id')
    exclusions = unique(tiers['cases'], 'case_id')
    if set(source) != set(facts) or set(source) != set(families):
        raise ValueError('Source/gold/family rosters differ')
    rows = []
    for cid, s in source.items():
        g, f, r = facts[cid], families[cid], s['request']
        if r['split'] != 'development' or r['case_id'] != cid:
            raise ValueError('Source request identity/split mismatch')
        if s['n'] != g['number'] or g['number'] != f['number']:
            raise ValueError('Number identity mismatch')
        for k in ('document', 'format', 'question'):
            if r[k] != g[k]:
                raise ValueError('Request/gold mismatch')
        for k in ('document', 'document_sha256', 'format', 'tier', 'source_text_sha256'):
            if g[k] != f[k]:
                raise ValueError('Gold/family mismatch')
        if (s['document_sha256'] != g['document_sha256'] or
                sha(s['source_text'].encode('utf-8')) != g['source_text_sha256']):
            raise ValueError('Source bytes differ from reviewed hashes')
        rows.append({**f, 'question': r['question'],
                     'normalized_source_sha256': sha(floor(s['source_text']).encode('utf-8'))})

    def pairs(subset):
        pdf, txt = ([r for r in subset if r['format'] == fmt] for fmt in ('pdf', 'txt'))
        return {name: [[p['number'], t['number']] for p in pdf for t in txt if check(p, t)]
                for name, check in (
                    ('exact_paragraph', lambda p, t: p['source_text_sha256'] == t['source_text_sha256']),
                    ('normalized_paragraph', lambda p, t: p['normalized_source_sha256'] == t['normalized_source_sha256']),
                    ('same_question', lambda p, t: p['question'] == t['question']),
                    ('question_and_normalized_paragraph', lambda p, t: p['question'] == t['question'] and
                     p['normalized_source_sha256'] == t['normalized_source_sha256']))}

    primary = [r for r in rows if r['tier'] == PRIMARY]
    excluded = []
    for r in rows:
        if r['format'] != 'pdf' or r['tier'] == PRIMARY:
            continue
        d = exclusions[r['case_id']]
        if d['tier'] != r['tier'] or d['document_sha256'] != r['document_sha256']:
            raise ValueError('PDF exclusion mismatch')
        excluded.append({k: d[k] for k in ('number', 'case_id', 'document', 'question',
                                          'tier', 'primary_reason', 'finding', 'original_expected')})
    counts = lambda rs: dict(sorted(Counter(r['format'] for r in rs).items()))
    candidate = []
    for r in sorted(primary, key=lambda r: r['number']):
        candidate.append({'number': r['number'], 'case_id': r['case_id'],
                          'question_sha256': sha(r['question'].encode('utf-8')),
                          'messages_sha256': sha(encoded(control_messages(r['question']))),
                          'pending_decisions': r['pending_decisions']})
    return {'version': 'd7-pilot-audit-v1.4', 'approved_for_execution': False,
            'model_calls': 0, 'sealed_opened': False, 'development_n': len(rows),
            'primary_n': len(primary), 'development_by_format': counts(rows),
            'primary_by_format': counts(primary),
            'primary_by_source': dict(sorted(Counter(r['source'] for r in primary).items())),
            'primary_by_format_label': {fmt: dict(sorted(Counter(r['label'] for r in primary
                                       if r['format'] == fmt).items())) for fmt in ('txt', 'pdf', 'json')},
            'primary_clean_prose_n': sum(r['format'] in ('txt', 'pdf') for r in primary),
            'all_development_pairs': pairs(rows), 'primary_pairs': pairs(primary),
            'excluded_pdfs': excluded, 'candidate_control_roster': candidate}


def parse_control(raw):
    def strict(items):
        obj = {}
        for key, val in items:
            if key in obj:
                raise ValueError('Duplicate response field')
            obj[key] = val
        return obj
    response = json.loads(raw, object_pairs_hook=strict)
    if not isinstance(response, dict) or set(response) != {'status', 'answer'}:
        raise ValueError('Unexpected control response fields')
    if not ((response['status'] == 'answer' and isinstance(response['answer'], str)) or
            (response['status'] == 'abstain' and response['answer'] is None)):
        raise ValueError('Invalid control status/value type')
    return response


def score_control(case, raw):
    """Use source-relative gold only as a positive string-match diagnostic."""
    result = {'case_id': case['case_id'], 'state': 'unknown',
              'closed_book_gold_match': None, 'reason': None}
    if case['tier'] != PRIMARY:
        raise ValueError('Primary case required')
    if case['pending_decisions']:
        return {**result, 'reason': 'unresolved_gold'}
    if raw is None:
        return {**result, 'reason': 'missing_or_failed_control'}
    try:
        response = parse_control(raw)
    except (ValueError, TypeError, UnicodeError):
        return {**result, 'reason': 'malformed_control'}
    if case['expected'] == 'supported':
        if len(case['roles']) != 1:
            return {**result, 'reason': 'unsupported_role_contract'}
        match = (response['status'] == 'answer' and
                 floor(response['answer']) in permitted_values(case['roles'][0]))
        return {**result, 'state': 'positive_' + ('matched' if match else
                ('abstained' if response['status'] == 'abstain' else 'nonmatched')),
                'closed_book_gold_match': match}
    if case['expected'] not in ('insufficient_evidence', 'ambiguous'):
        return {**result, 'reason': 'unsupported_label'}
    return {**result, 'state': 'negative_' + ('answered' if response['status'] == 'answer' else 'abstained')}


def score_views(cases, control_raw, rag_correct):
    """Pre-scored D5 correctness only; missing RAG outcomes remain failures.

    Capture/model/freeze verification belongs to the final runner, not this helper.
    Family intervals/composition must be attached there before publication.
    """
    roster = unique(cases, 'case_id')
    if set(control_raw) - set(roster) or set(rag_correct) - set(roster):
        raise ValueError('Unexpected capture identity')
    if any(type(v) is not bool and v is not None for v in rag_correct.values()):
        raise ValueError('Boolean or unresolved RAG correctness required')
    scored = [score_control(c, control_raw.get(c['case_id'])) for c in cases]
    unknown = sum(s['state'] == 'unknown' for s in scored)
    gold_pending = any(c['pending_decisions'] for c in cases) or any(v is None for v in rag_correct.values())

    def view(ids):
        return {'n': len(ids), 'correct': sum(rag_correct.get(i) is True for i in ids),
                'positive_n': sum(roster[i]['expected'] == 'supported' for i in ids),
                'negative_n': sum(roster[i]['expected'] != 'supported' for i in ids)}

    included = [s['case_id'] for s in scored if s['closed_book_gold_match'] is not True]
    return {'all_primary': None if gold_pending else view(list(roster)),
            'adjusted_primary': None if gold_pending or unknown else view(included),
            'unknown_controls': unknown, 'unresolved_gold': gold_pending,
            'missing_rag_failures': len(set(roster) - set(rag_correct)),
            'states': dict(sorted(Counter(s['state'] for s in scored).items())), 'cases': scored}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--proposal', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    audit, members = verified_input(args.audit, args.proposal)
    paths = {'gold': ROOT / 'docs/reports/t39-d4-gold-candidate-v1.1.json',
             'ledger': ROOT / 'docs/reports/t39-d6-family-ledger-v1.3.json',
             'tiers': ROOT / 'docs/reports/t39-d3-tiers-v1.1.json'}
    result = audit_pairing(audit, **{k: load(p) for k, p in paths.items()})
    paths.update(audit=args.audit, prompt=HERE / 'closed-book-v1.4.txt',
                 schema=HERE / 'closed-book-v1.4.schema.json', code=Path(__file__),
                 policy=HERE / 'pilot-scope-v1.4.md')
    result['input_sha256'] = {k: sha(p.read_bytes()) for k, p in paths.items()}
    result['verified_development_members'] = members
    result['proposal_manifest_sha256'] = audit['manifest_sha256']
    save(args.output, result)
    print(json.dumps({k: result[k] for k in ('primary_n', 'primary_by_format',
                      'all_development_pairs', 'verified_development_members')}))


if __name__ == '__main__':
    main()
