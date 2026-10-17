"""Assemble the internally reviewed pilot offline; never admits model requests.

All candidate content stays in the caller's private, new output directory. The
old independent execution gates and all original proposal bytes remain unchanged.
"""
import argparse
from copy import deepcopy
from pathlib import Path

from .activate_level_a import verify_previous
from .families import PRIMARY, digest, encoded, load, save
from .internal_custody import MANIFEST, aggregate, reconcile, require
from .table_adapter import adapt
from .typed_facts import validate_gold

ROOT = Path(__file__).resolve().parents[2]
REVIEW = ROOT / 'docs/reports/t39-internal-review-v1.7'
REVIEW_SHA = '3959f30357599b5980187ada62d01597e01a21890cbcb2f321c796fd25c00675'


def unique(rows, key):
    result = {r[key]: r for r in rows}
    require(len(result) == len(rows), 'Duplicate input identity')
    return result


def safe_file(root, name):
    path = root / name
    require(isinstance(name, str) and not Path(name).is_absolute() and
            '..' not in Path(name).parts and not path.is_symlink() and
            path.resolve().is_relative_to(root.resolve()), 'Input path escapes package')
    return path


def assemble_split(name, requests, gold, families, sources, source_texts, annotations, proofs, excluded):
    require(name in ('development', 'exposed_candidates'), 'Unknown internal split')
    reqs, facts, fams = (unique(rows, 'case_id') for rows in (requests, gold['cases'], families))
    require(set(reqs) == set(facts) == set(fams), 'Source/gold/family rosters differ')
    require(set(excluded) <= set(reqs), 'Unknown exclusion')
    validate_gold(gold)
    documents, cases, controls, original = {}, [], [], []
    files = {}
    source_split = 'development' if name == 'development' else 'sealed'
    for cid, request in reqs.items():
        case, family = facts[cid], fams[cid]
        require(request['split'] == source_split, 'Wrong original split')
        require(all(request[k] == case[k] for k in ('question', 'format', 'document')),
                'Question or source identity changed')
        require(case['pending_decisions'] == [], 'Unresolved gold decision')
        require(case['tier'] == family['tier'] and bool(family['family_key']), 'Family/tier mismatch')
        raw = sources[case['document']]
        require(digest(raw) == case['document_sha256'] == family['document_sha256'],
                'Source bytes differ from review')
        text = source_texts[cid]
        require(digest(text.encode('utf8')) == case['source_text_sha256'], 'Reviewed text changed')
        if cid in excluded:
            continue
        require(request.get('history', []) == [] and request.get('prose', False) is False,
                'Unexpected history or prose in frozen source request')
        filename = case['document']
        if filename not in documents:
            reps = {'v1': raw, 'v2': raw}
            annotation = annotations.get(filename)
            if case['format'] == 'json':
                require(annotation is not None, 'Missing reviewed table annotation')
                adapted, sidecar = adapt(raw, annotation)
                reps['v2'] = encoded(adapted)
                files[f'{name}/annotations/{filename}'] = encoded(annotation)
                files[f'{name}/contexts/{filename}'] = encoded(sidecar)
            representations = {}
            for version, body in reps.items():
                path = f'{name}/{version}/documents/{filename}'
                files[path] = body
                representations[version] = {'path': path, 'sha256': digest(body),
                    'bytes': len(body), 'record_pointer': '/records' if case['format'] == 'json' else None}
            documents[filename] = {'document': filename, 'format': case['format'],
                'original_sha256': digest(raw), 'representations': representations,
                'review_text_sha256': digest(text.encode('utf8')),
                'review_text_path': f'{name}/review-texts/{filename}.txt',
                'review_text_coordinates': 'Reviewed-source UTF-8; PDF container bytes bound separately'}
            files[f'{name}/review-texts/{filename}.txt'] = text.encode('utf8')
        else:
            require(documents[filename]['review_text_sha256'] == digest(text.encode('utf8')),
                    'Shared document has conflicting reviewed text')
        cases.append(deepcopy(case))
        original.append(deepcopy(request))
        if case['tier'] == PRIMARY:
            # Only the original question reaches the closed-book operation.
            controls.append({'case_id': cid, 'question': request['question']})
    selected = {c['case_id'] for c in cases}
    selected_proofs = [deepcopy(p) for p in proofs if p['case_id'] in selected]
    require({p['case_id'] for p in selected_proofs} ==
            {c['case_id'] for c in cases if c['format'] == 'json'}, 'Table proof coverage differs')
    # Control/planning payloads deliberately contain no fields, values, aliases or proofs.
    queries = [{'case_id': c['case_id'], 'document': c['document'], 'question': c['question'],
                'history': [], 'prose': False, 'family': fams[c['case_id']]['family_key'],
                'tier': c['tier']} for c in cases]
    result = {'cases': len(cases), 'primary': len(controls),
        'tiers': {tier: sum(c['tier'] == tier for c in cases) for tier in
                  (PRIMARY, 'derived_inference', 'stress_adjudication')},
        'documents': len(documents), 'exclusions': len(excluded)}
    for filename, value in {
        'gold.json': {**deepcopy(gold), 'status': 'internal_source_reviewed_not_independent',
                     'approved_for_execution': False, 'independent_review': False,
                     'blind_holdout': False, 'sealed_content_opened': True,
                     'implementation_exposed_candidates': 60,
                     'pending_global_decisions': ['runtime/scorer/control integration', 'committed execution freeze'],
                     'lineage_separation_certified': False, 'cases': cases},
        'questions.json': queries, 'controls.json': controls, 'original-requests.json': original,
        'documents.json': list(documents.values()),
        'families.json': [deepcopy(fams[c['case_id']]) for c in cases],
        'table-proofs.json': {'cases': selected_proofs},
        'exclusions.json': sorted(excluded),
    }.items():
        files[f'{name}/{filename}'] = encoded(value)
    return files, result


def verify_review():
    verify_previous()
    require(digest((REVIEW/'manifest.json').read_bytes()) == REVIEW_SHA, 'Review freeze changed')
    manifest = load(REVIEW/'manifest.json')
    predecessor = manifest['predecessor']
    predecessor_path = safe_file(ROOT, predecessor['path'])
    require(digest(predecessor_path.read_bytes()) == predecessor['sha256'], 'Gold freeze changed')
    for entry in load(predecessor_path)['artifacts']:
        require(digest(safe_file(ROOT, entry['path']).read_bytes()) == entry['sha256'],
                'Prior gold artifact changed')
    for entry in manifest['artifacts']:
        require(digest(safe_file(ROOT, entry['path']).read_bytes()) == entry['sha256'],
                'Reviewed artifact changed')
    return manifest


def prepare(proposal, private_audit, private_annotations, development_sources, candidate_sources, output):
    verify_review()
    require(not output.exists(), 'Output must be new')
    require(digest((proposal/'manifest.json').read_bytes()) == MANIFEST, 'Wrong T39 proposal')
    manifest = load(proposal/'manifest.json')
    for name, expected in manifest['files'].items():
        require(digest(safe_file(proposal, name).read_bytes()) == expected, 'Proposal member changed')
    ledger, receipt, overlay = (load(REVIEW/name) for name in
                              ('development-family-ledger.json', 'receipt.json', 'development-overlay.json'))
    audit = load(private_audit)
    require(digest(encoded(audit)) == receipt['private_audit_sha256'], 'Private review changed')
    require(encoded(aggregate(audit, ledger)) == encoded(receipt) and
            encoded(reconcile(receipt, ledger)) == encoded(overlay),
            'Review reconciliation changed')
    annotations = unique(load(private_annotations)['tables'], 'document')
    for row in audit['cases']:
        if row['format'] == 'json':
            require(digest(encoded(annotations[row['gold']['document']])) == row['annotation_sha256'],
                    'Private table annotation changed')
    source_annotations = unique(load(ROOT/'evals/measurement/table-annotations-v1.2.json')['tables'], 'document')
    dev_gold = load(ROOT/'docs/reports/t39-gold-review-v1.6/gold.json')
    dev_proofs = load(ROOT/'docs/reports/t39-d5-coordinate-proofs-v1.2.json')['cases']
    candidate_gold = {'version': 't39-internal-candidate-gold-v1.7', 'independent_review': False,
        'blind_holdout': False, 'cases': [r['gold'] for r in audit['cases']]}
    candidate_proofs = [{'case_id': r['case_id'], 'proof_sets': r['coordinate_proofs'],
                        'stress_readings': []} for r in audit['cases'] if r['format'] == 'json']
    text_audits = {'development': load(development_sources), 'exposed_candidates': load(candidate_sources)}
    require(text_audits['development']['opened_proposal_split'] == 'development' and
            text_audits['exposed_candidates']['opened_proposal_split'] == 'sealed_exposed_internal',
            'Wrong source-review text split')
    files, counts = {}, {}
    for name, original_name, gold, families, annotation_set, proofs, exclusions in (
        ('development', 'development', dev_gold, ledger['cases'], source_annotations, dev_proofs,
         {r['case_id'] for r in overlay['excluded_development']}),
        ('exposed_candidates', 'sealed', candidate_gold, audit['cases'], annotations, candidate_proofs, set())):
        requests = load(proposal/original_name/'requests.json')
        sources = {r['document']: safe_file(proposal/original_name/'documents', r['document']).read_bytes()
                   for r in requests}
        text_rows = unique(text_audits[name]['cases'], 'id')
        require(set(text_rows) == {r['case_id'] for r in requests}, 'Reviewed text roster differs')
        texts = {cid: r['source_text'] for cid,r in text_rows.items()}
        split_files, counts[name] = assemble_split(name, requests, gold, families, sources, texts,
                                                  annotation_set, proofs, exclusions)
        files.update(split_files)
        # Preserve the exact original human-labelled view separately.
        files[f'{name}/original-labels.json'] = (proposal/original_name/'proposed-labels.json').read_bytes()
    package = {'version': 't39-internal-successor-v1', 'approved_for_execution': False,
        'independent_review': False, 'blind_holdout': False, 'exposed_candidates': 60,
        'review_manifest_sha256': REVIEW_SHA, 'original_proposal_manifest_sha256': MANIFEST,
        'counts': counts, 'files': {name: digest(raw) for name, raw in sorted(files.items())},
        'builder_sha256': digest(Path(__file__).read_bytes()),
        'limitation': 'Internal pilot only; full lineage uncertified, primary n=147 below target; no default promotion.'}
    # Complete validation/assembly before any new package files are published.
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        path = safe_file(output, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    save(output/'manifest.json', package)
    return package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proposal', type=Path, required=True)
    parser.add_argument('--private-audit', type=Path, required=True)
    parser.add_argument('--private-annotations', type=Path, required=True)
    parser.add_argument('--development-sources', type=Path, required=True)
    parser.add_argument('--candidate-sources', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    package = prepare(args.proposal, args.private_audit, args.private_annotations,
                      args.development_sources, args.candidate_sources, args.output)
    print(encoded({'counts': package['counts'], 'approved_for_execution': False}).decode())


if __name__ == '__main__':
    main()
