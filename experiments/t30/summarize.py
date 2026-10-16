"""Failure-inclusive sequential comparison against the retained 208 T28 responses."""
import argparse
import json
from pathlib import Path
from experiments.t27.summarize import compare
from .run import BASELINE, SUITES, baseline_identity
from .preflight import write


def summarize(root):
    frozen = json.loads((root/'execution-freeze.json').read_bytes())
    if baseline_identity() != frozen['baseline']: raise ValueError('baseline changed')
    blocks, failures, count = {}, [], 0
    for suite, (_, _, variants, _) in SUITES.items():
        for block, _, _ in variants:
            old = json.loads((BASELINE/suite/block/'12b/complete.json').read_bytes())['cases']
            new = json.loads((root/suite/block/'12b-kv-q8/complete.json').read_bytes())['cases']
            if len(new) != (16 if suite == 't14' else 28): raise ValueError('incomplete denominator')
            count += len(new)
            result = compare(old, new)
            result['case_changes'] = [{'case': a['case'], 'before': a.get('score'), 'after': b.get('score'),
                'before_http': a['http_status'], 'after_http': b['http_status']}
                for a, b in zip(old, new) if a.get('score') != b.get('score') or a['http_status'] != b['http_status']]
            blocks[suite+'/'+block] = result
            for gate in ('correctness_regressions', 'source_support_losses', 'new_false_support'):
                if result[gate]: failures.append({'block': suite+'/'+block, 'gate': gate, 'cases': result[gate]})
    if count != 208: raise ValueError('wrong request count')
    return {'requests': count, 'blocks': blocks, 'quality_gates_passed': not failures,
        'failures': failures, 'production': 'f16 retained; experimental q8 runtime only',
        'interpretation': 'Sequential observed-regression comparison; retained API excludes the new range validator.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists(): raise ValueError('preserve prior output')
    result = summarize(args.root)
    write(args.output, result)
    print(json.dumps({'requests': result['requests'], 'quality_passed': result['quality_gates_passed']}))
