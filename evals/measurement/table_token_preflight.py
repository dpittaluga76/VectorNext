"""CPU tokenizer-only D5 preflight in an existing processor container; no inference."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from .build_table_candidate import build, load_inputs, write
from .table_adapter import canonical

SCRIPT = r'''
import hashlib, json, sys, tokenizers
from pathlib import Path
from tokenizers import Tokenizer
payload = json.load(sys.stdin)
metadata = {}; encoders = {}
for role in ('embedding', 'reranker'):
    path = Path('/models') / role / 'tokenizer.json'
    tokenizer = Tokenizer.from_file(str(path)); tokenizer.no_truncation(); tokenizer.no_padding()
    encoders[role] = tokenizer
    metadata[role] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
for row in payload['records']:
    row['tokens'] = sum(encoders['embedding'].encode(row.pop('text'), add_special_tokens=True).attention_mask)
for row in payload['pairs']:
    row['tokens'] = sum(encoders['reranker'].encode(row.pop('question'), row.pop('text'), add_special_tokens=True).attention_mask)
payload['tokenizers'] = {'version': tokenizers.__version__, **metadata}
json.dump(payload, sys.stdout)
'''


def payload():
    annotations, sources, gold, _ = load_inputs()
    documents, _, _, _ = build()
    records, pairs = [], []
    cases = [c for c in gold['cases'] if c['format'] == 'json']
    for name, raw in sources.items():
        for version, document in [('v1', json.loads(raw)), ('v2', documents[name])]:
            for i, record in enumerate(document['records']):
                if 'cells' not in record:
                    continue
                # Structural JSON policy, intended /records selection; source rows have no /id.
                prefix = f'record /records/{i}; field /records/{i}\n\n'
                records.append({'document': name, 'version': version, 'row': i,
                    'data_row': annotations[name]['row_kinds'][str(i)] == 'data',
                    'text': prefix + canonical(record)})
                for case in cases:
                    if case['document'] == name:
                        pairs.append({'number': case['number'], 'document': name, 'version': version,
                            'row': i, 'question': case['question'], 'text': canonical(record)})
    return {'records': records, 'pairs': pairs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--container', required=True, help='Existing processor only; does not start a container')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    request = json.dumps(payload()).encode()
    result = subprocess.run(['docker', 'exec', '-i', args.container, 'python', '-c', SCRIPT],
        input=request, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    output = json.loads(result.stdout)
    output['input_sha256'] = hashlib.sha256(request).hexdigest()
    output['tool_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if json.dumps(payload()).encode() != request:
        raise ValueError('Source representation changed during token check')
    output['summary'] = {}
    for version in ('v1', 'v2'):
        records = [r for r in output['records'] if r['version'] == version]
        pairs = [r for r in output['pairs'] if r['version'] == version]
        output['summary'][version] = {
            'table_records': len(records), 'embedding_whole_record_over_256': sum(r['tokens'] > 256 for r in records),
            'max_whole_record_tokens': max(r['tokens'] for r in records),
            'question_record_pairs': len(pairs), 'reranker_pairs_over_512': sum(r['tokens'] > 512 for r in pairs),
            'max_pair_tokens': max(r['tokens'] for r in pairs)}
    output['scope'] = ('Tokenizer-only, no model inference, no truncation, no new containers. Whole records may '
        'split into JSON subtrees during ingestion; >256 is a fragmentation warning, not a proven ingestion failure. '
        'Complete-row question pairs are a representation-size screen, not observed reranker inputs: '
        'current reranking uses selected subtrees after JSON splitting; answer assembly restores complete records. '
        'Actual chunk counts, paired reranker inputs and full ingestion/retrieval remain pending.')
    write(args.output, output)
    print(json.dumps(output['summary']))


if __name__ == '__main__':
    main()
