"""Derive scoring coordinates from captured evidence and frozen source bytes.

No model-produced coordinates are trusted. Missing, ambiguous or altered captures
stay observable gaps; this module never supplies missing evidence to a model.
"""
import json
import re

from .families import digest
from .internal_custody import require
from .table_adapter import visible_coordinates, value_coordinate


def bind_evidence(evidence, document_id, revision):
    key = evidence['key']
    require(key['document_id'] == document_id and key['revision'] == revision,
            'Evidence belongs to a different document revision')
    require(all(s['revision'] == revision for s in evidence['sources']), 'Source revision changed')
    require('text' in evidence and not evidence.get('text_truncated'), 'Full evidence capture required')


def table_coordinates(source_bytes, annotation, representation, evidence, document_id, revision):
    bind_evidence(evidence, document_id, revision)
    locators = [s['locator']['Json']['pointer'] for s in evidence['sources']
                if 'Json' in s['locator']]
    require(locators and len(set(locators)) == 1, 'Unambiguous original record locator required')
    match = re.fullmatch(r'/records/(0|[1-9][0-9]*)', locators[0])
    require(match is not None, 'Complete captured record locator required')
    row = int(match[1])
    record = evidence['record']
    # Rust's bundle puts the complete record in both places. A sidecar alone,
    # truncated display or unseen record cannot earn grounding credit.
    require(json.loads(evidence['text']) == record, 'Visible evidence differs from captured record')
    refs = visible_coordinates(source_bytes, annotation, row, record, representation)
    return {'record_index': row, 'visible_coordinates': refs}


def cell_coordinate(source_bytes, annotation, row, pointer):
    return value_coordinate(source_bytes, annotation, row, pointer)


def whitespace_map(text):
    """Collapse source whitespace while retaining original UTF-8 byte bounds.

    This is location alignment, not answer normalization. Punctuation, signs,
    currencies, case and non-whitespace characters are unchanged.
    """
    chars, offsets = [], []
    offset = 0
    for char in text:
        end = offset + len(char.encode('utf8'))
        if char.isspace():
            if chars and chars[-1] == ' ':
                offsets[-1] = (offsets[-1][0], end)
            else:
                chars.append(' '); offsets.append((offset, end))
        else:
            chars.append(char); offsets.append((offset, end))
        offset = end
    return ''.join(chars), offsets


def aligned_span(source, visible):
    haystack, mapping = whitespace_map(source)
    needle = whitespace_map(visible)[0].strip()
    if not needle:
        return None, 'empty_visible_text'
    positions, start = [], 0
    while True:
        found = haystack.find(needle, start)
        if found < 0:
            break
        positions.append(found)
        start = found + 1
    if len(positions) != 1:
        return None, 'ambiguous_source_alignment' if positions else 'source_alignment_missing'
    start = positions[0]
    return (mapping[start][0], mapping[start + len(needle) - 1][1]), None


def merge_spans(spans):
    result = []
    for start,end in sorted(spans):
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(result[-1][1], end))
        else:
            result.append((start,end))
    return result


def prose_coordinates(review_text, expected_text_sha256, original_sha256,
                      evidence, document, document_id, revision):
    bind_evidence(evidence, document_id, revision)
    require(document['document_id'] == document_id and document['revision'] == revision,
            'Frozen document identity differs')
    require(digest(review_text.encode('utf8')) == expected_text_sha256, 'Reviewed source text changed')
    blocks = {b['id']: b for b in document['blocks']}
    require(len(blocks) == len(document['blocks']), 'Duplicate frozen block identity')
    ranges, gaps = [], []
    for span in evidence['spans']:
        block = blocks.get(span['block_id'])
        require(block is not None, 'Unknown captured block')
        start, end = span['bytes']['start'], span['bytes']['end']
        raw = block['text'].encode('utf8')
        require(type(start) is int and type(end) is int and 0 <= start < end <= len(raw),
                'Invalid captured block interval')
        visible = raw[start:end].decode('utf8')
        require(visible in evidence['text'], 'Block span was not visible in evidence')
        match, gap = aligned_span(review_text, visible)
        if match:
            ranges.append(match)
        else:
            gaps.append({'block_id':block['id'],'reason':gap})
    return {'proofs':[{'document_sha256':original_sha256, 'utf8_start':a, 'utf8_end':b}
                      for a,b in merge_spans(ranges)],
            'alignment_gaps':gaps, 'coordinate_system':'reviewed_source_utf8'}
