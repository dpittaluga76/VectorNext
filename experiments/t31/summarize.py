"""Post-run reporting only: inspect retained captures without new inference."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
from tokenizers import Tokenizer


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def stats(values):
    return {'min': min(values), 'median': statistics.median(values), 'max': max(values)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    summary = json.loads((args.run/'summary.json').read_bytes())
    freeze = json.loads((args.run/'execution-freeze.json').read_bytes())
    result = {k: v for k, v in summary.items() if k != 'ingestion'}
    result.update(image=freeze['image'], freeze_sha256=hashlib.sha256(
        (args.run/'execution-freeze.json').read_bytes()).hexdigest(),
        source_zip_sha256=hashlib.sha256((args.run/'source.zip').read_bytes()).hexdigest(),
        scope='Observed source-retrieval regression; no generated-answer evaluation',
        ingestion={}, chunk_comparison={}, stage_changes=[], token_counts={})
    reranker = Tokenizer.from_file('/models/reranker/tokenizer.json')
    reranker.no_truncation()
    reranker.no_padding()
    for suite in ('nist', 'nasa'):
        canonical = {}
        for model, directory in (('minilm', 'embedding'), ('bge-small-en-v1.5', 'embedding-bge-small-en-v1.5')):
            key = suite+'/'+model
            report = summary['ingestion'][key]
            folder = args.run/suite/model
            documents = next(r['documents'] for r in rows(folder/'00-ingest.jsonl') if r.get('kind') == 'finish')
            canonical[model] = {d['document_id']: [
                {'evidence': c['evidence'], 'structure': c['structural_context'], 'spans': c['spans'],
                 'locators': [s['locator'] for s in c['sources']]} for c in d['chunks']]
                for d in documents}
            tokenizer = Tokenizer.from_file('/models/'+directory+'/tokenizer.json')
            tokenizer.no_truncation()
            tokenizer.no_padding()
            counts = [len(tokenizer.encode('\n\n'.join(p for p in
                (c['structural_context'], c['evidence']) if p)).ids) for d in documents for c in d['chunks']]
            queries = rows(folder/'01-cold.jsonl')
            pair_counts = [len(reranker.encode(r['question'], p).ids)
                           for r in queries if r.get('status') == 'ok' for p in r['passages']]
            result['token_counts'][key] = {'embedding_input': stats(counts), 'rerank_pair': stats(pair_counts)}
            result['ingestion'][key] = {k: report[k] for k in ('documents', 'chunks', 'elapsed_ms')}
            result['ingestion'][key].update(
                failures=[r for r in report['records'] if r['result']['status'] != 'ok'],
                worker_startup_ms=report['profile']['elapsed_ms'], space=report['profile']['profile']['space'],
                space_ids=sorted({s for d in documents for c in d['chunks'] for s in c['vectors']}))
        result['chunk_comparison'][suite] = {
            'identical_text_structure_spans_locators': canonical['minilm'] == canonical['bge-small-en-v1.5']}
        for phase in ('cold', 'warm'):
            a = summary['scores'][suite+'/minilm/'+phase]['cases']
            b = summary['scores'][suite+'/bge-small-en-v1.5/'+phase]['cases']
            for x, y in zip(a, b):
                assert x['id'] == y['id']
                changes = {stage: {'minilm': x[stage]['covered'], 'bge': y[stage]['covered']}
                    for stage in ('raw', 'selected', 'primary') if x[stage]['covered'] != y[stage]['covered']}
                if changes:
                    result['stage_changes'].append({'suite': suite, 'pass': phase, 'id': x['id'], 'changes': changes})
    args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('requests', 'chunk_comparison', 'token_counts', 'stage_changes')}))


if __name__ == '__main__':
    main()
