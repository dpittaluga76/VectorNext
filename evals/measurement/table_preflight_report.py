"""Summarize retained budget captures without labels, quality scores or inference."""
import argparse
import json
from pathlib import Path

from .families import digest, load, save


def summarize(directory):
    payload = load(directory / 'input.json')
    manifest = load(directory / 'preflight.json')
    process = load(directory / 'process.json')
    if digest((directory / 'input.json').read_bytes()) != manifest['input_sha256']:
        raise ValueError('Input capture changed')
    if process['exit_code'] or not process['valid_preflight_identity']:
        raise ValueError('Incomplete/changed preflight cannot be reported as passed')
    folder = directory / 'result'
    finish = load(folder / 'finished.json')
    if finish['work_error'] or finish['release_error'] or finish['generation_calls'] != 0:
        raise ValueError('Incomplete preflight or generation invoked')
    documents = []
    for n, source in enumerate(payload['documents']):
        row = load(folder / f'document-{n}.json')
        if row['stage'] != 'Committed' or row['error'] or not row['chunks']:
            raise ValueError('Document ingestion failed')
        original = json.loads(source['source_text'])
        chunks = row['chunks']
        for chunk in chunks:
            if not 0 < chunk['embedding_tokens'] <= row['config']['space']['max_tokens']:
                raise ValueError('Embedding budget violation')
            attr = chunk['chunk']['attributes']['record']
            pointer = attr['sources'][0]['locator']['Json']['pointer']
            if attr['value'] != original['records'][int(pointer.split('/')[2])]:
                raise ValueError('Full source record changed during ingestion')
        oversized = []
        for warning in payload['oversized_rows']:
            if warning['document'] != source['name']:
                continue
            prefix = f"/records/{warning['row']}"
            parts = [c for c in chunks if c['chunk']['attributes']['record']['sources'][0]
                     ['locator']['Json']['pointer'] == prefix]
            if len(parts) <= 1:
                raise ValueError('Expected oversized row to split into multiple chunks')
            oversized.append({'row': warning['row'], 'whole_record_tokens': warning['tokens'],
                'chunks': len(parts), 'max_chunk_tokens': max(c['embedding_tokens'] for c in parts),
                'pointers': [c['chunk']['sources'][0]['locator']['Json']['pointer'] for c in parts]})
        documents.append({'document': source['name'], 'source_sha256': digest(source['source_text'].encode()),
            'revision': row['revision'], 'stage': row['stage'], 'chunks': len(chunks),
            'max_embedding_tokens': max(c['embedding_tokens'] for c in chunks),
            'all_full_records_preserved': True, 'oversized_rows': oversized})
    cases = []
    for case in payload['cases']:
        captured = load(folder / f"case-{case['number']}.json")
        if not captured['stopped_before_generation']:
            raise ValueError('Budget probe failed before reaching generation boundary')
        rerank = next(e for e in captured['events'] if e['operation'] == 'rerank')
        counts = [e['tokens'] for e in captured['events'] if e['operation'] == 'answer_tokens']
        final = captured['events'][-1]['input']
        if not counts or counts[-1] is None or counts[-1] > 3328 or rerank['error']:
            raise ValueError('Final answer/rerank budget check failed')
        original = json.loads(next(d['source_text'] for d in payload['documents'] if d['name'] == case['document']))
        for evidence in final['evidence']:
            pointer = evidence['sources'][0]['locator']['Json']['pointer']
            if evidence['record'] != original['records'][int(pointer.split('/')[2])]:
                raise ValueError('Answer assembly did not restore the full source record')
        cases.append({'number': case['number'], 'reranked_passages': len(rerank['passages']),
            'max_reranker_pair_tokens': max(rerank['result']['pair_tokens']),
            'final_evidence_records': len(final['evidence']), 'full_records_restored': True,
            'final_prompt_tokens': counts[-1], 'input_headroom_tokens': 3328 - counts[-1],
            'generation_calls': 0, 'answer_scored': False})
    return {'version': 1, 'kind': 'operational_budget_preflight_not_quality_evaluation',
        'documents': documents, 'cases': cases, 'model_identity': load(folder / 'lease-identity.json'),
        'profile': load(folder / 'profile.json'), 'source_code_hashes': manifest['source_files'],
        'capture_hashes': {p.relative_to(directory).as_posix(): digest(p.read_bytes()) for p in sorted(directory.rglob('*'))
                           if p.is_file()},
        'limits': {'embedding': 256, 'reranker': 512, 'generation_input': 3328, 'generation_output_reserved': 768},
        'limitations': ['Current production prompt, not final D4 evaluation instruction.',
            'Generic string answer field; automatic field planning not exercised.',
            'Two complete tables and their three questions only; not all 32 tables or a quality score.',
            'CPU cache was shared with the normal processor; final evaluation needs separate caches.',
            'Temporary Linux database removed with the container; captures retained.',
            'Source-relative ambiguity/derived labels not evaluated; no inferred answers or control results.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = summarize(args.capture)
    save(args.output, result)
    print(json.dumps({'documents': len(result['documents']), 'cases': len(result['cases']),
                      'oversized_rows': sum(len(d['oversized_rows']) for d in result['documents'])}))


if __name__ == '__main__':
    main()
