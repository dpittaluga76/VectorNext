"""Predeclared planner and exact source-backed answer checks; no inference."""
from decimal import Decimal
from itertools import permutations
import json
import re


def exact_load(raw):
    return json.loads(raw, parse_float=Decimal)


def normalize(value):
    return ' '.join(value.split()).casefold()


def match_fields(plan, expected):
    """A bijection: extras, omissions, incorrect types/nullability all fail."""
    fields = plan.get('fields', [])
    if plan.get('status') != 'ready' or len(fields) != len(expected):
        return None
    names = [f.get('name') for f in fields]
    if any(not isinstance(n, str) for n in names) or len(set(names)) != len(names):
        return None
    for ordered in permutations(fields):
        if all(f.get('kind') == e['kind'] and f.get('nullable') is e.get('nullable', False)
               and re.search(e['meaning'], f['name'] + ' ' + f.get('description', ''), re.I)
               for f, e in zip(ordered, expected)):
            return [f['name'] for f in ordered]
    return None


def typed_equal(value, expected, kind):
    if kind == 'integer':
        return type(value) is int and value == expected
    if kind == 'number':
        return type(value) in (int, Decimal) and value == expected
    if kind == 'string':
        return type(value) is str and value == expected
    if kind == 'boolean':
        return type(value) is bool and value is expected
    return False


def value_text(value):
    if value is None: return 'null'
    if type(value) is bool: return 'true' if value else 'false'
    return str(value)


def score(code, raw, label, documents):
    result = {'correct': False, 'planning_correct': False, 'answer_correct': False,
              'projection_exact': False, 'citations_correct': False, 'error': None,
              'planning': None, 'audit': None, 'values_text': {}, 'timings_ms': {}}
    try:
        view = exact_load(raw) if raw else {}
        result['error'] = (view.get('error') or {}).get('message')
        if label['plan'] != 'ready':
            # Rust's existing Error::Invalid Display adds this fixed envelope prefix.
            message = result['error'].removeprefix('invalid record: ') if isinstance(result['error'], str) else ''
            correct = (code == 400 and isinstance(result['error'], str)
                       and (view.get('error') or {}).get('code') == 'invalid_request'
                       and message.startswith(label['error_contains']))
            result.update(correct=correct, planning_correct=correct,
                          decline_observed=label['plan'] if correct else None)
            return result
        if code != 200: return result
        report = exact_load(view['raw_report'])
        planning = report.get('planning') or {}
        result.update(planning=planning, audit=report.get('audit'),
                      timings_ms=report.get('timings_ms', {}),
                      prompt_tokens=report.get('prompt_tokens'))
        plan = planning.get('plan') or {}
        names = match_fields(plan, label['fields'])
        specs = report.get('request', {}).get('fields', {})
        plan_fields = plan.get('fields', [])
        result['planning_correct'] = names is not None and set(specs) == set(names) and all(
            all(specs[f['name']].get(k) == f.get(k) for k in ('kind', 'nullable', 'description'))
            for f in plan_fields)
        result['matched_names'] = names
        answer = report.get('answer') or {}
        fields = answer.get('fields', {})
        result['values_text'] = {n: value_text(p['value']) for n, p in fields.items()}
        result['status'] = answer.get('status')
        valid = report.get('validation', {}).get('mechanical_support') == 'passed'
        outcome = answer.get('status') == view.get('outcome') == label['outcome']
        if label['outcome'] == 'insufficient_evidence':
            result['projection_exact'] = view.get('fields') == []
            result['answer_correct'] = outcome and valid and fields == {}
            result['correct'] = result['planning_correct'] and result['answer_correct'] and result['projection_exact']
            return result
        if names is None: return result
        exact = set(fields) == set(names) and all(typed_equal(fields[n]['value'], e['value'], e['kind'])
                                                for n, e in zip(names, label['fields']))
        evidence = {e['id']: e for e in report.get('evidence', [])}
        def cited(proof, expected):
            e = evidence.get(proof.get('evidence_id'), {})
            key = e.get('key', {})
            doc = documents.get(key.get('document_id'), {})
            if not doc or key.get('revision') != doc.get('revision'): return False
            chunk = next((c for c in doc['chunks'] if c['id'] == key.get('chunk_id')), None)
            if not chunk or not e.get('text') or normalize(e['text']) not in normalize(chunk['evidence']): return False
            return all(f['document'] == key['document_id'] and normalize(f['text']) in normalize(e['text'])
                       for f in expected['facts'])
        citations = set(fields) == set(names) and all(cited(fields[n], e) for n, e in zip(names, label['fields']))
        ui = view.get('fields', [])
        projected = (len(ui) == len(names) and {f.get('name') for f in ui} == set(names)
                     and all(f.get('kind') == specs.get(f['name'], {}).get('kind')
                             and f.get('value_text') == result['values_text'].get(f['name']) for f in ui))
        result.update(answer_correct=outcome and valid and exact and citations,
                      citations_correct=citations, projection_exact=projected)
        result['correct'] = result['planning_correct'] and result['answer_correct'] and projected
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        result['scoring_error'] = str(error)
        result['correct'] = False
    return result
