"""Sequential T28 comparisons to both immutable T27 arms."""
import argparse
import json
from pathlib import Path
from experiments.t27.summarize import compare
from .run import SUITES, BASELINE, baseline_identity
from .preflight import write


def summarize(root):
    frozen = json.loads((root/'execution-freeze.json').read_bytes())
    if baseline_identity() != frozen['baseline']: raise ValueError('baseline captures changed')
    blocks, failures, count = {}, [], 0
    for suite, (_, _, variants, _) in SUITES.items():
        for block, _, _ in variants:
            candidate = json.loads((root/suite/block/'12b/complete.json').read_bytes())['cases']
            expected = 16 if suite == 't14' else 28
            if len(candidate) != expected: raise ValueError('incomplete denominator')
            count += len(candidate)
            key = suite+'/'+block
            comparisons = {}
            for model in ('26b-offload22', '12b'):
                old = json.loads((BASELINE/suite/block/model/'complete.json').read_bytes())['cases']
                result = compare(old, candidate)
                comparisons[model] = result
                for gate in ('correctness_regressions', 'source_support_losses', 'new_false_support'):
                    if result[gate]: failures.append({'block': key, 'baseline': model, 'gate': gate, 'cases': result[gate]})
                if model == '26b-offload22' and block.startswith('five-'):
                    if result['candidate']['exact'] < (13 if suite == 't14' else 16):
                        failures.append({'block': key, 'gate': 'control_floor'})
                    if result['control']['missing_timings'] or result['candidate']['missing_timings']:
                        failures.append({'block': key, 'gate': 'incomplete_latency'})
                    for gate in ('median_reduction', 'common_median_reduction'):
                        if result[gate] is None or result[gate] < .20:
                            failures.append({'block': key, 'gate': gate, 'value': result[gate]})
            blocks[key] = comparisons
    if count != 208: raise ValueError('incorrect total denominator')
    return {'requests': count, 'blocks': blocks, 'evaluation_gates_passed': not failures,
            'failures': failures, 'promotion': 'requires all separate application and hardware gates',
            'interpretation': 'Sequential observed-regression comparison to retained T27 controls, not paired timing or independent quality.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): raise ValueError('preserve existing output')
    result = summarize(args.root)
    write(args.output, result)
    print(json.dumps({'requests': result['requests'], 'passed': result['evaluation_gates_passed'], 'failed_gates': len(result['failures'])}))
