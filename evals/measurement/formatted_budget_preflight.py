"""Token-only replay of retained assembly candidates with the frozen D4 format.

No ranking, field planning, generation, scoring or model switching. Run in an
isolated processor image with fresh CPU cache and only an existing idle NuExtract.
"""
import argparse
import json
from pathlib import Path
import urllib.request
import uuid

from .evaluation_worker import EvaluationWorker
from .families import digest, load, save
from .format_contract import INSTRUCTION


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    # Read only the named public development capture, never labels or sealed data.
    if load(args.capture / 'input.json')['kind'] != 't39_table_budget_preflight':
        raise ValueError('Expected development budget capture')
    if not load(args.capture / 'process.json')['valid_preflight_identity']:
        raise ValueError('Source preflight identity failed')
    files = sorted((args.capture / 'result').glob('case-*.json'))
    records = [(file, load(file)) for file in files]
    if len(records) != 3 or any(not r['stopped_before_generation'] for _, r in records):
        raise ValueError('Expected the three completed, unscored assembly probes')
    args.output.mkdir(parents=True, exist_ok=False)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open('http://llm:8080/health', timeout=5) as response:
        health = json.load(response)
    save(args.output / 'health-before.json', health)
    if health['loaded_model'] != 'nuextract' or health['lease'] or health['active'] or health['interactive_waiting']:
        raise ValueError('NuExtract must already be resident and idle; no model switching')
    worker = EvaluationWorker()
    worker.capture_directory, worker.transport_sequence, worker.measurements = args.output, 0, []
    token = 'formatted-budget-' + uuid.uuid4().hex
    lease = {'model': 'nuextract', 'token': token, 'owner': token, 'priority': 'interactive'}
    rows = []
    try:
        identity = worker.http('/control/acquire', lease)
        save(args.output / 'identity.json', identity)
        if identity['model'] != 'nuextract' or identity['token'] != token or identity['activation_seconds'] != 0:
            raise ValueError('Unexpected preflight model activation/identity')
        for path, case in records:
            counts = []
            for event in case['events']:
                if event['operation'] != 'answer_tokens':
                    continue
                count = worker.handle({'op': 'answer_tokens', 'input': event['input'], 'lease': lease})
                counts.append({'production_tokens': event['tokens'], 'formatted_tokens': count,
                               'evidence_records': len(event['input']['evidence'])})
            row = {'number': case['number'], 'capture_sha256': digest(path.read_bytes()),
                'counts': counts, 'final_tokens': counts[-1]['formatted_tokens'],
                'all_assembly_candidates_fit': all(c['formatted_tokens'] <= 3328 for c in counts),
                'headroom_tokens': 3328 - counts[-1]['formatted_tokens']}
            save(args.output / f"case-{case['number']}.json", row)
            rows.append(row)
    finally:
        released = worker.http('/control/release', {'token': token})
        save(args.output / 'release.json', released)
    save(args.output / 'summary.json', {'kind': 'token_only_format_preflight', 'cases': rows,
        'instruction_sha256': digest(INSTRUCTION.read_bytes()),
        'worker_sha256': digest(Path(__file__).with_name('evaluation_worker.py').read_bytes()),
        'tool_sha256': digest(Path(__file__).read_bytes()), 'generation_calls': 0, 'answers_scored': 0,
        'limits': {'input': 3328, 'context': 4096, 'output_reserved': 768},
        'limitations': ['Generic explicit string field; actual automatic plans must be budgeted again.',
            'Three questions in two tables, not the whole benchmark.',
            'Replays captured assembly candidates; does not run retrieval or scoring.']})
    print(json.dumps(rows))


if __name__ == '__main__':
    main()
