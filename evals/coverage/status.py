"""Read-only progress view; not part of the frozen inference implementation."""
import argparse
import json
from pathlib import Path
import statistics
from .freeze import BLOCKS, ROOT


def status(run):
    root = ROOT / 'data/t14' / run
    for block, _, _ in BLOCKS:
        path = root / block / 'progress.json'
        if not path.exists():
            continue
        try:
            rows = json.loads(path.read_bytes())
        except json.JSONDecodeError:
            print(block, 'progress file updating'); continue
        scores = [row['score'] for row in rows if row['score']]
        print(block, 'completed', len(rows), 'exact', sum(s['answer_correct'] for s in scores),
              'errors', sum(r['http_status'] != 200 for r in rows),
              'proofs', sum(s['supported_with_annotated_proofs'] for s in scores),
              'context', sum(s['stages']['context']['complete'] is True for s in scores),
              'median', round(statistics.median(r['wall_seconds'] for r in rows), 3))
        last = rows[-1]
        print('  latest:', last['case'], last['http_status'],
              (last['score'] or {}).get('actual_status'),
              (last['score'] or {}).get('answer_correct'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--run', required=True)
    status(parser.parse_args().run)
