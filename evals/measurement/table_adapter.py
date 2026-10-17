"""D5: annotation-driven table context. No heuristics, questions or gold inputs."""
from copy import deepcopy
import hashlib
import json

VERSION = 'table-context-v1.2'
JOIN = ' | '
KINDS = ('caption', 'column_header', 'group_header', 'row_label', 'unit', 'qualifier')
ROW_KINDS = {'caption', 'column_header', 'unit_header', 'mixed_header', 'group_header',
             'group_and_header', 'data', 'blank'}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True)


def ref_key(ref):
    return canonical(ref)


def resolve(source, ref):
    """Exact cell or explicitly bounded UTF-8 paragraph excerpt; no invented text."""
    if 'row' in ref:
        if set(ref) not in ({'row', 'col'}, {'row', 'col', 'utf8_start', 'utf8_end'}) or any(type(ref[k]) is not int or ref[k] < 0 for k in ref):
            raise ValueError('Invalid cell coordinate')
        row = source['records'][ref['row']]
        if row.get('row_index') != ref['row']:
            raise ValueError('Row coordinate differs from original row index')
        text = row['cells'][ref['col']]
        if 'utf8_start' in ref:
            raw = text.encode('utf-8'); a, b = ref['utf8_start'], ref['utf8_end']
            if not 0 <= a < b <= len(raw):
                raise ValueError('Invalid literal unit excerpt')
            text = raw[a:b].decode('utf-8')
    else:
        if set(ref) != {'paragraph', 'utf8_start', 'utf8_end'}:
            raise ValueError('Invalid paragraph reference')
        if any(type(ref[k]) is not int for k in ref) or ref['paragraph'] < 0:
            raise ValueError('Invalid paragraph coordinate')
        raw = source['records'][ref['paragraph']]['text'].encode('utf-8')
        a, b = ref['utf8_start'], ref['utf8_end']
        if not 0 <= a < b <= len(raw):
            raise ValueError('Invalid paragraph span')
        text = raw[a:b].decode('utf-8')
    if not isinstance(text, str):
        raise ValueError('Source table types must stay strings')
    return text


def validate(source_bytes, annotation):
    if hashlib.sha256(source_bytes).hexdigest() != annotation['source_sha256']:
        raise ValueError('Source bytes differ from annotated version')
    source = json.loads(source_bytes)
    rows = {i: r for i, r in enumerate(source['records']) if 'cells' in r}
    kinds = annotation['row_kinds']
    if set(kinds) != {str(r) for r in rows} or any(k not in ROW_KINDS for k in kinds.values()):
        raise ValueError('Every table row requires an explicit classification')
    for i, row in rows.items():
        if row.get('row_index') != i or any(not isinstance(s, str) for s in row['cells']):
            raise ValueError('Original row indices and string types required')
    data_rows = {i for i in rows if kinds[str(i)] == 'data'}
    if set(annotation['row_labels']) != {str(r) for r in data_rows}:
        raise ValueError('Every data row needs an explicit row-label mapping')
    for row, refs in annotation['row_labels'].items():
        if not isinstance(refs, list) or not refs:
            raise ValueError('Row label requires a reference, even when its source cell is blank')
        for ref in refs:
            resolve(source, ref)
    ids = set(); units = set()
    for rule in annotation['rules']:
        if rule['id'] in ids or rule['kind'] not in KINDS or not rule['refs']:
            raise ValueError('Duplicate rule or invalid context kind/reference')
        ids.add(rule['id'])
        if rule['relation'] not in ('same_column', 'from_span', 'explicit_scope', 'same_row', 'cell_symbol'):
            raise ValueError('A structural relation must be explicit')
        if not rule['rows'] or not rule['columns'] or len(set(rule['rows'])) != len(rule['rows']) or len(set(rule['columns'])) != len(rule['columns']):
            raise ValueError('Empty or duplicate scope')
        for ref in rule['refs']:
            resolve(source, ref)
        for r in rule['rows']:
            if type(r) is not int or r not in data_rows:
                raise ValueError('Scope targets an unclassified/non-data row')
            for c in rule['columns']:
                if type(c) is not int or not 0 <= c < len(rows[r]['cells']):
                    raise ValueError('Column outside source row')
                if rule['relation'] == 'same_column' and any(ref.get('col') != c for ref in rule['refs']):
                    raise ValueError('Cross-column header mapping must be tagged from_span')
                if rule['kind'] == 'unit':
                    if (r, c) in units:
                        raise ValueError('Overlapping unit scopes require explicit adjudication')
                    units.add((r, c))
    return source


def annotate(source_bytes, annotation):
    source = validate(source_bytes, annotation)
    contexts = {}
    for row, kind in annotation['row_kinds'].items():
        r = int(row)
        if kind != 'data':
            continue
        fields = []
        for c in range(len(source['records'][r]['cells'])):
            paths = {k: [] for k in KINDS}
            for ref in annotation['row_labels'][row]:
                paths['row_label'].append({'text': resolve(source, ref), 'ref': ref,
                    'relation': 'same_row' if ref.get('row') == r else 'explicit_scope',
                    'annotation_rule': 'row_labels/' + row})
            for rule in annotation['rules']:
                if r not in rule['rows'] or c not in rule['columns']:
                    continue
                paths[rule['kind']].extend({'text': resolve(source, ref), 'ref': ref,
                    'relation': rule['relation'], 'annotation_rule': rule['id']} for ref in rule['refs'])
            fields.append({'column': c, 'paths': paths,
                           'unit_scope': 'annotated' if paths['unit'] else 'unspecified'})
        contexts[row] = fields
    return {'version': VERSION, 'table_id': annotation['table_id'],
            'source_sha256': annotation['source_sha256'], 'row_kinds': annotation['row_kinds'],
            'annotation_status': 'internal_source_only_not_independent', 'contexts': contexts}


def render_row(record, fields):
    """Fixed presentation; joined strings are context, NEVER gold/source cells.

    References and structural derivation tags stay in the hash-bound annotated
    context sidecar. Only this rendered representation enters the candidate corpus.
    """
    output = {k: deepcopy(v) for k, v in record.items() if k != 'headers'}
    context = {}
    for field in fields:
        if field['column'] == 0:
            continue
        paths = field['paths']
        entry = {}
        for kind in ('caption', 'column_header', 'group_header', 'qualifier'):
            texts = [p['text'] for p in paths[kind] if p['text']]
            if texts:
                entry[kind] = JOIN.join(texts)
        # Row labels remain the exact original cells; explicit carried labels are shown.
        carried = [p['text'] for p in paths['row_label'] if p['relation'] != 'same_row']
        if carried:
            entry['row_label'] = JOIN.join(carried)
        entry['unit_scope'] = (JOIN.join(p['text'] for p in paths['unit'])
                               if field['unit_scope'] == 'annotated' else 'unspecified')
        context[str(field['column'])] = entry
    output['structural_context'] = context
    return output


def adapt(source_bytes, annotation):
    source = validate(source_bytes, annotation)
    sidecar = annotate(source_bytes, annotation)
    result = deepcopy(source)
    for i, record in enumerate(result['records']):
        if str(i) in sidecar['contexts']:
            result['records'][i] = render_row(record, sidecar['contexts'][str(i)])
        elif 'cells' in record:
            # Keep every header/group/blank source row once, with its original cells.
            result['records'][i] = {k: v for k, v in record.items() if k != 'headers'}
    for before, after in zip(source['records'], result['records']):
        if 'cells' in before and before['cells'] != after['cells']:
            raise AssertionError('Original cells changed')
        if 'text' in before and before != after:
            raise AssertionError('Original narrative changed')
    return result, sidecar


def coordinate(annotation, ref):
    return {'table_id': annotation['table_id'], 'source_sha256': annotation['source_sha256'], **ref}


def proof_for(annotation, sidecar, row, col):
    """Value cell plus the specific annotated context, not matching value strings."""
    field = next(f for f in sidecar['contexts'][str(row)] if f['column'] == col)
    value = coordinate(annotation, {'row': row, 'col': col})
    refs = [value]
    for kind in KINDS:
        refs += [coordinate(annotation, p['ref']) for p in field['paths'][kind] if p['text']]
    unique = {ref_key(ref): ref for ref in refs}
    return {'value': value, 'required': list(unique.values())}


def visible_coordinates(source_bytes, annotation, record_index, captured_record, representation):
    """Map only actually captured record content, never unseen sidecar metadata.

    The caller must bind the captured document/revision to this representation's
    frozen file hash. This helper verifies the complete record, not a model quote.
    """
    source = validate(source_bytes, annotation)
    if type(record_index) is not int or not 0 <= record_index < len(source['records']):
        raise ValueError('Invalid captured record index')
    original = source['records'][record_index]
    if representation == 'v1':
        expected = original
        refs = []
        if 'cells' in original:
            refs += [{'row': record_index, 'col': c} for c in range(len(original['cells']))]
            if original.get('headers') != source['records'][0]['cells']:
                raise ValueError('v1 repeated-first-row assumption differs')
            refs += [{'row': 0, 'col': c} for c in range(len(original['headers']))]
    elif representation == 'v2':
        adapted, sidecar = adapt(source_bytes, annotation)
        expected = adapted['records'][record_index]
        refs = [{'row': record_index, 'col': c} for c in range(len(original.get('cells', [])))]
        for field in sidecar['contexts'].get(str(record_index), []):
            if field['column'] == 0:
                continue
            for kind in KINDS:
                refs += [p['ref'] for p in field['paths'][kind] if p['text']]
    else:
        raise ValueError('Unknown representation')
    if canonical(captured_record) != canonical(expected):
        raise ValueError('Captured record does not match frozen representation')
    if 'text' in original:
        refs = [{'paragraph': record_index, 'utf8_start': 0,
                 'utf8_end': len(original['text'].encode('utf-8'))}]
    return list({ref_key(ref): coordinate(annotation, ref) for ref in refs}.values())


def value_coordinate(source_bytes, annotation, record_index, pointer):
    """Only original cell pointers identify values; joined context is not a cell."""
    import re
    match = re.fullmatch(r'/cells/(0|[1-9][0-9]*)', pointer)
    if not match:
        raise ValueError('Rendered context, row IDs and metadata cannot identify a value cell')
    if type(record_index) is not int or str(record_index) not in annotation['row_kinds']:
        raise ValueError('Value does not identify an original table row')
    ref = {'row': record_index, 'col': int(match[1])}
    resolve(validate(source_bytes, annotation), ref)
    return coordinate(annotation, ref)
