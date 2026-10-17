"""Reproduce D5 development artifacts without inference or sealed input access."""
import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re

from . import table_adapter as adapter
from .typed_facts import digest, floor, permitted_values

ROOT = Path(__file__).resolve().parents[2]
ANNOTATIONS = ROOT / 'evals/measurement/table-annotations-v1.2.json'
SOURCES = ROOT / 'evals/measurement/table-sources-v1.2'
GOLD = ROOT / 'docs/reports/t39-d4-gold-candidate-v1.1.json'
READINGS = ROOT / 'evals/measurement/table-proof-readings-v1.2.json'


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def write(path, value):
    with path.open('xb') as stream:
        stream.write(encoded(value))


def load_inputs():
    registry = json.loads(ANNOTATIONS.read_bytes())
    manifest = json.loads((SOURCES / 'manifest.json').read_bytes())
    annotations = {t['document']: t for t in registry['tables']}
    if manifest['split'] != 'development' or registry['sealed_content_opened'] is not False:
        raise ValueError('Only the reviewed development table registry is accepted')
    if len(annotations) != len(registry['tables']) or set(annotations) != {f['path'] for f in manifest['files']}:
        raise ValueError('Annotation/source inventory mismatch')
    # Validate every path before opening any fixture.
    for item in manifest['files']:
        if not re.fullmatch(r'tatqa-[0-9a-f-]{36}\.json', item['path']):
            raise ValueError('Unexpected source fixture path')
        path = SOURCES / item['path']
        if path.is_symlink() or not path.resolve().is_relative_to(SOURCES.resolve()):
            raise ValueError('Source fixture escapes development directory')
        if item['table_id'] != annotations[item['path']]['table_id']:
            raise ValueError('Source and annotation table identity differ')
    sources = {}
    for item in manifest['files']:
        raw = (SOURCES / item['path']).read_bytes()
        if len(raw) != item['bytes'] or hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ValueError('Changed source fixture')
        adapter.validate(raw, annotations[item['path']])
        sources[item['path']] = raw
    gold = json.loads(GOLD.read_bytes())
    if {c['document'] for c in gold['cases'] if c['format'] == 'json'} != set(sources):
        raise ValueError('Gold/source coverage mismatch')
    return annotations, sources, gold, json.loads(READINGS.read_bytes())


def coordinate_proofs(case, annotation, sidecar):
    """Expand previously adjudicated D4 locations, never value-match a new proof."""
    if len(case['roles']) != 1:
        raise ValueError('Table proof schema currently supports one role')
    proofs = []
    for original in case['roles'][0]['proof_sets']:
        refs = []
        value = None
        for loc in original:
            match = re.fullmatch(r'/records/(\d+)/cells/(\d+)', loc['pointer'])
            if not match or loc['document_sha256'] != annotation['source_sha256']:
                raise ValueError('D4 source proof is not the expected cell')
            row, col = map(int, match.groups())
            cell = adapter.coordinate(annotation, {'row': row, 'col': col})
            if value is None:
                value = cell
            refs.extend(adapter.proof_for(annotation, sidecar, row, col)['required']
                        if str(row) in sidecar['contexts'] else [cell])
        proofs.append({'value': value, 'required': list({adapter.ref_key(r): r for r in refs}.values())})
    return proofs


def numeric_key(text):
    """Audit leads only. This normalization is NEVER used by the scorer."""
    candidate = text.strip().replace(',', '').lstrip('$£')
    if not re.fullmatch(r'-?\d+(?:\.\d+)?%?', candidate):
        return None
    try:
        return str(Decimal(candidate.rstrip('%')).normalize())
    except InvalidOperation:
        return None


def build():
    annotations, sources, gold, readings = load_inputs()
    documents, sidecars, tables = {}, {}, []
    for name, raw in sources.items():
        annotation = annotations[name]
        source = json.loads(raw)
        adapted, sidecar = adapter.adapt(raw, annotation)
        documents[name], sidecars[name] = adapted, sidecar
        table_rows = [r for r in source['records'] if 'cells' in r]
        data_indexes = [int(r) for r, kind in annotation['row_kinds'].items() if kind == 'data']
        header_rows = [int(r) for r, kind in annotation['row_kinds'].items()
                       if kind in ('column_header', 'mixed_header', 'group_and_header')]
        groups = [int(r) for r, kind in annotation['row_kinds'].items()
                  if kind in ('group_header', 'group_and_header')]
        tables.append({'table_id': annotation['table_id'], 'document': name,
            'v1_sha256': annotation['source_sha256'],
            'v2_sha256': hashlib.sha256(encoded(adapted)).hexdigest(),
            'sidecar_sha256': hashlib.sha256(encoded(sidecar)).hexdigest(),
            'table_rows': len(table_rows), 'cells': sum(len(r['cells']) for r in table_rows),
            'data_rows': len(data_indexes), 'rules': len(annotation['rules']),
            'original_cells_and_paragraphs_preserved': True,
            'changed_records': [i for i, pair in enumerate(zip(source['records'], adapted['records']))
                                if pair[0] != pair[1]],
            'header_rows': sorted(header_rows), 'multiple_header_rows': len(header_rows) > 1,
            'body_heading_rows': sorted(groups),
            'interior_heading_rows': sorted(r for r in groups if any(d < r for d in data_indexes)),
            'unspecified_data_unit_cells': sum(f['unit_scope'] == 'unspecified' for fields
                in sidecar['contexts'].values() for f in fields if f['column'] > 0)})
    cases, scans = [], []
    for case in gold['cases']:
        if case['format'] != 'json':
            continue
        name = case['document']; annotation = annotations[name]; sidecar = sidecars[name]
        source = json.loads(sources[name])
        proofs = coordinate_proofs(case, annotation, sidecar)
        role = case['roles'][0]
        values = permitted_values(role)
        exact, numeric, narrative = [], [], []
        key = numeric_key(role['value_string'])
        for row, record in enumerate(source['records']):
            for col, text in enumerate(record.get('cells', [])):
                if floor(text) in values:
                    exact.append({'row': row, 'col': col, 'text': text})
                if key is not None and numeric_key(text) == key:
                    numeric.append({'row': row, 'col': col, 'text': text})
            if 'text' in record:
                text = record['text']
                # Numeric matches are token bounded; textual aliases are whole words.
                for match in re.finditer(r'(?<![\w.])[$£]?-?\d[\d,]*(?:\.\d+)?%?(?![\w.])', text):
                    if key is not None and numeric_key(match[0]) == key:
                        narrative.append({'paragraph': row, 'utf8_start': len(text[:match.start()].encode()),
                            'utf8_end': len(text[:match.end()].encode()), 'text': match[0],
                            'classification': 'numeric_lead_not_proof'})
                if key is None:
                    for value in values:
                        for match in re.finditer(r'(?<!\w)' + re.escape(value) + r'(?!\w)', text):
                            narrative.append({'paragraph': row, 'utf8_start': len(text[:match.start()].encode()),
                                'utf8_end': len(text[:match.end()].encode()), 'text': match[0],
                                'classification': 'text_lead_not_proof'})
        extra = readings['cases'].get(case['case_id'], {})
        conditional = []
        for reading in extra.get('stress_readings', []):
            row, col = reading['row'], reading['col']
            if source['records'][row]['cells'][col] != reading['value_string']:
                raise ValueError('Conditional reading differs from source')
            conditional.append({**reading, 'proof_sets': [adapter.proof_for(annotation, sidecar, row, col)]})
        if extra.get('additional_required'):
            for ref in extra['additional_required']:
                adapter.resolve(source, ref)
            for proof in proofs:
                proof['required'].extend(adapter.coordinate(annotation, ref) for ref in extra['additional_required'])
        cases.append({'number': case['number'], 'case_id': case['case_id'], 'document': name,
            'tier': case['tier'], 'role_id': role['id'], 'proof_sets': proofs,
            'stress_readings': conditional, 'review_note': extra.get('note',
                'D4 source-selected value locations expanded by generic D5 context annotations.')})
        scans.append({'number': case['number'], 'case_id': case['case_id'], 'tier': case['tier'],
            'value_string': role['value_string'], 'exact_cells': exact,
            'numeric_equivalent_cell_leads': numeric, 'narrative_leads': narrative,
            'duplicate_exact_value': len(exact) > 1,
            'alternative_proofs_automatically_added': False})
    audit = {'version': '1.2', 'status': 'review_candidate_no_inference',
        'sealed_content_opened': False, 'model_outputs_inspected': False,
        'summary': {'tables': len(tables), 'table_questions': len(cases),
            'cells_preserved': sum(t['cells'] for t in tables),
            'annotated_data_rows': sum(t['data_rows'] for t in tables),
            'annotation_rules': sum(t['rules'] for t in tables),
            'multi_header_tables': sum(t['multiple_header_rows'] for t in tables),
            'tables_with_interior_headings': sum(bool(t['interior_heading_rows']) for t in tables),
            'duplicate_exact_value_cases': [s['number'] for s in scans if s['duplicate_exact_value']],
            'narrative_lead_cases': [s['number'] for s in scans if s['narrative_leads']],
            'table_tiers': dict(Counter(c['tier'] for c in cases))},
        'tables': tables, 'case_scans': scans}
    registry = {'version': '1.2', 'approved_for_execution': False,
        'D4_gold_sha256': digest(GOLD), 'annotation_sha256': digest(ANNOTATIONS),
        'reading_adjudications_sha256': digest(READINGS), 'cases': cases}
    return documents, sidecars, registry, audit


def diff_markdown(documents, audit):
    """All-table context diff, including every data row; original values stay out of the diff."""
    _, sources, _, _ = load_inputs()
    lines = ['# D5 all-table context diff', '',
        'Generated from source-only annotations, before inference. Original cells and narratives are unchanged.',
        'Each old data row repeated the first source row as `headers`. Each new data row carries the context below.',
        'Non-data rows lose only that repeated `headers` field. The full structured paths/references are in sidecars.', '']
    for item in audit['tables']:
        name = item['document']; original = json.loads(sources[name])
        lines += [f'## {name}', '', f"v1 SHA-256: `{item['v1_sha256']}`", '',
            f"v2 SHA-256: `{item['v2_sha256']}`", '',
            'Old repeated headers: `' + adapter.canonical(original['records'][0]['cells']).replace('`', '\\`') + '`', '']
        for row, record in enumerate(documents[name]['records']):
            if 'structural_context' in record:
                lines += [f"Row {row}: {record['cells'][0]}".rstrip(), '', '```json',
                          adapter.canonical(record['structural_context']), '```', '']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New directory; never replaces prior artifacts')
    args = parser.parse_args()
    documents, sidecars, proofs, audit = build()
    args.output.mkdir(parents=True, exist_ok=False)
    for directory, items in [('documents', documents), ('sidecars', sidecars)]:
        target = args.output / directory; target.mkdir()
        for name, value in items.items():
            write(target / name, value)
    write(args.output / 'proofs.json', proofs)
    write(args.output / 'audit.json', audit)
    with (args.output / 'diff.md').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(diff_markdown(documents, audit))
    print(json.dumps(audit['summary']))


if __name__ == '__main__':
    main()
