"""Publish selected completed-run traces without new API/model calls."""
import argparse
import json
from deployment import workflow
from .freeze import ROOT, HERE, BLOCKS, verify


def publish(run):
    verify()
    root = ROOT / 'data/t14' / run
    if not all((root / block / 'complete.json').exists() for block, _, _ in BLOCKS):
        raise ValueError('finish all frozen blocks before publishing examples')
    targets = {'t14-coverage-workflow.md': [('coverage-cold', 'two_earthquakes')],
               't14-failure-workflows.md': [('two-cold', 'two_earthquakes'), ('coverage-cold', 'three_launches'), ('five-cold', 'mission_photos')]}
    captures = ROOT / 'docs/reports/t14-captures'
    if captures.exists() or any((ROOT / 'docs/reports' / name).exists() for name in targets):
        raise ValueError('published examples already exist')
    requests = json.loads((HERE / 'requests.json').read_bytes())
    captures.mkdir()
    for filename, pairs in targets.items():
        entries = []
        for block, identifier in pairs:
            rows = json.loads((root / block / 'complete.json').read_bytes())['cases']
            row = next(r for r in rows if r['case'] == identifier)
            entry = workflow.capture('ask', (root / block / row['report_file']).read_bytes(),
                status=row['http_status'], elapsed=row['wall_seconds'],
                context={'question': requests[identifier]['question']},
                note=f'T14 frozen comparison: {block}/{identifier}. Selected example; see the complete T14 report for all 96 outcomes. The runner called Client.request directly; there was no per-question client CLI invocation.')
            entry['evaluation'] = {'block': block, 'case': identifier, 'raw_response_sha256': row['report_sha256'],
                                   'score': row['score'], 'public_request': requests[identifier]}
            (captures / (block + '-' + identifier + '.json')).write_text(json.dumps(entry, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            entries.append(entry)
        introduction = ('# T14 — selected workflow examples\n\n'
            'Generated offline from retained responses. These examples were selected after the run; '
            'they are not the complete evaluation. [Results and limitations](t14-evidence-coverage.md).\n\n'
            'The recorded evaluation command was:\n\n'
            '```powershell\npython -m evals.coverage.run --run ' + run + ' --phase all\n```\n\n'
            'Each operation below identifies its API handler and high-level implementation calls. '
            'These references are not an instrumented call stack.\n\n---\n\n')
        (ROOT / 'docs/reports' / filename).write_text(introduction + workflow.render_many(entries), encoding='utf-8')
        print(filename)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--run', required=True)
    publish(parser.parse_args().run)
