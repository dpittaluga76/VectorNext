"""Read-only development label lint. Findings are review leads, never corrections."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


NUMBER = re.compile(
    r"(?<![\w.])[-+]?\d+(?:,\d{3})*(?:\.\d+)?"
    r"(?=$|[^\w.]|\.(?!\d)|(?:st|nd|rd|th|[kKmMbB])\b)"
)
QUALIFIER = re.compile(
    r"\b(almost|nearly|approximately|about|over|under|allegedly|"
    r"more than|less than|at least|at most|up to|just under)\s*$", re.I
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def numbers(text):
    # Preserve spelling. No floats, implicit scale conversion or numerical scoring.
    return [m.group() for m in NUMBER.finditer(text)]


def spans(text, needle):
    if not needle:
        return []
    return [m.start() for m in re.finditer(re.escape(needle), text)]


def evidence_for(case, answer):
    support = case['label']['support']
    if case['request']['source'] == 'qasper':
        return '\n'.join(
            p for annotation in support
            if answer in annotation.get('extractive_spans', [])
            for p in annotation.get('evidence', [])
        )
    if case['request']['source'] == 'tatqa':
        document = json.loads(case['source_text'])
        cells = []
        for match in support['possible_exact_cells']:
            # This is a candidate cell, not an adjudicated correct row/column proof.
            value = document['records'][match['record_index']]
            for part in match['pointer'].split('/')[1:]:
                value = value[int(part)] if isinstance(value, list) else value[part]
            cells.append(str(value))
        return '\n'.join(cells)
    # SQuAD supplies span annotations in the complete scoped paragraph.
    return case['source_text']


def audit_cases(cases):
    if any(c['request']['split'] != 'development' or
           c['label']['split'] != 'development' for c in cases):
        raise ValueError('Only development cases may be inspected')
    if len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Duplicate case')
    rows = []
    for case in cases:
        alternatives = case['label']['alternatives']
        alternative_rows = []
        numeric_sets = {tuple(numbers(a)) for a in alternatives if numbers(a)}
        for index, answer in enumerate(alternatives):
            text = case['source_text']
            trimmed = answer.strip()
            occurrences = spans(text, trimmed)
            flags = []
            if not occurrences:
                flags.append('not_literal_in_scoped_text')
            if trimmed not in evidence_for(case, answer):
                flags.append('not_literal_in_own_annotated_evidence')
            if occurrences and all(
                (start and text[start-1].isalnum()) or
                (start + len(trimmed) < len(text) and text[start+len(trimmed)].isalnum())
                for start in occurrences
            ):
                flags.append('only_subtoken_occurrences')
            containers = [j for j, other in enumerate(alternatives)
                          if trimmed != other.strip() and trimmed in other.strip()]
            if containers:
                flags.append('shorter_than_another_accepted_alternative')
            qualifiers = sorted({
                match.group(1).lower() for start in occurrences
                if (match := QUALIFIER.search(text[max(0, start-30):start]))
            })
            if qualifiers:
                flags.append('source_has_immediate_qualifier')
            if re.search(r'\b(the|a|an|to|of|and|or|with|by)\s*$', trimmed, re.I):
                flags.append('possible_clipped_ending')
            if numbers(answer) and len(numeric_sets) > 1:
                flags.append('alternatives_have_different_numeric_tokens')
            alternative_rows.append({
                'index': index, 'text': answer, 'numeric_tokens': numbers(answer),
                'flags': flags, 'containing_alternative_indices': containers,
                'immediate_source_qualifiers': qualifiers,
                'scoped_text_occurrences': len(occurrences),
            })
        numeric = any(a['numeric_tokens'] for a in alternative_rows)
        rows.append({
            'number': case['n'], 'case_id': case['id'],
            'question': case['request']['question'],
            'source': case['request']['source'],
            'document': case['request']['document'],
            'document_sha256': case['document_sha256'],
            'original_outcome': case['label']['expected'],
            'alternatives': alternative_rows,
            'numeric_policy': 'numeric-scoring-v1.1' if numeric else None,
            'numeric_binding_status': 'requires_semantic_quantity_and_scope_review' if numeric else None,
            'manual_semantic_review_required': True,
        })
    return {
        'kind': 'development_alternative_lint_not_label_approval',
        'approved_for_execution': False,
        'sealed_content_opened': False,
        'summary': {
            'development_cases': len(rows),
            'original_supported_cases': sum(r['original_outcome'] == 'supported' for r in rows),
            'accepted_alternatives': sum(len(r['alternatives']) for r in rows),
            'numeric_cases': sum(r['numeric_policy'] is not None for r in rows),
            'flagged_cases': sum(any(a['flags'] for a in r['alternatives']) for r in rows),
            'flags_by_kind': dict(sorted(Counter(
                flag for r in rows for a in r['alternatives'] for flag in a['flags']
            ).items())),
        },
        'limitations': [
            'Substring presence, qualifier adjacency and numeric differences do not establish semantic correctness.',
            'Short spans and answers ending inside sentences are often legitimate; flags are not rejection rules.',
            'PDF source_text is the reviewed transcription, not a PDF byte-offset coordinate system.',
            'SQuAD support is its full scoped paragraph; TAT-QA matches may include wrong-scope duplicate cells.',
            'Cause/effect, definitions, quantity roles, dates, units and spelled-out numbers need manual review.',
            'No labels or captured model scores are modified. Sealed records are excluded.',
        ],
        'cases': rows,
    }


def verified_input(audit_path, proposal):
    audit = json.loads(audit_path.read_text(encoding='utf-8'))
    if audit['opened_proposal_split'] != 'development':
        raise ValueError('Input must be a development-only source audit')
    # Validate all paths before reading any member, including accidental sealed paths.
    root = proposal.resolve()
    paths = []
    for entry in audit['verified_development_members']:
        relative = Path(entry['path'])
        if relative.is_absolute() or relative.parts[0] != 'development' or '..' in relative.parts:
            raise ValueError('Only development member paths are permitted')
        target = (root / relative).resolve()
        if not target.is_relative_to(root / 'development'):
            raise ValueError('Member escapes development directory')
        paths.append((entry, target))
    if sha256(root / 'manifest.json') != audit['manifest_sha256']:
        raise ValueError('Proposal manifest changed')
    for entry, target in paths:
        if sha256(target) != entry['sha256']:
            raise ValueError(f"Development member changed: {entry['path']}")
    return audit, len(paths)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--proposal', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    audit, count = verified_input(args.audit, args.proposal)
    result = audit_cases(audit['cases'])
    result['input'] = {
        'source_audit_sha256': sha256(args.audit),
        'proposal_manifest_sha256': audit['manifest_sha256'],
        'verified_development_members': count,
        'scanner_sha256': sha256(Path(__file__)),
    }
    with args.output.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    print(json.dumps(result['summary']))


if __name__ == '__main__':
    main()
