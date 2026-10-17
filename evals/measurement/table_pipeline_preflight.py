"""Prepare/run the bounded, unscored D5 ingestion and token-budget probe."""
import argparse
import json
from pathlib import Path
import subprocess

from .activate_level_a import verify_previous
from .build_table_candidate import build
from .families import digest, encoded, load, save

ROOT = Path(__file__).resolve().parents[2]


def prepare(output):
    verify_previous()
    screen = load(ROOT / 'docs/reports/t39-d5-token-preflight-v1.2.json')
    oversized = [r for r in screen['records'] if r['version'] == 'v2' and r['tokens'] > 256]
    names = sorted({r['document'] for r in oversized})
    documents, _, _, _ = build()
    gold = load(ROOT / 'docs/reports/t39-gold-review-v1.6/gold.json')
    payload = {'kind': 't39_table_budget_preflight', 'split': 'development',
        'documents': [{'name': name, 'source_text': encoded(documents[name]).decode()} for name in names],
        'oversized_rows': oversized,
        # Source-only requests: do not give gold values, fields, aliases or proof cells.
        'cases': [{k: c[k] for k in ('number', 'question', 'document')} for c in gold['cases']
                  if c['document'] in names]}
    output.mkdir(parents=True, exist_ok=False)
    save(output / 'input.json', payload)
    paths = [*sorted((ROOT / 'src').rglob('*.rs')), ROOT / 'Cargo.toml', ROOT / 'Cargo.lock',
             ROOT / 'examples/measurement_table_preflight.rs', Path(__file__),
             ROOT / 'evals/measurement/build_table_candidate.py',
             ROOT / 'evals/measurement/table_adapter.py',
             ROOT / 'evals/measurement/table-annotations-v1.2.json']
    manifest = {'kind': 'operational_preflight_not_quality_evaluation', 'input_sha256': digest(encoded(payload)),
        'source_files': {p.relative_to(ROOT).as_posix(): digest(p.read_bytes()) for p in paths},
        'generator_prompt': 'unchanged production template; final D4 instruction not installed',
        'fields': 'one generic string answer field; no automatic field planning',
        'scope': 'Two complete development tables, nine flagged rows and three original questions; no answer inference.',
        'storage': 'temporary Linux directory; no application database mount',
        'cache': 'existing processor CPU cache; future benchmark requires isolated caches',
        'model_calls': 'CPU embedding/reranking plus resident NuExtract template/tokenization only'}
    save(output / 'preflight.json', manifest)
    return payload, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run', action='store_true', help='One temporary Docker container; no generation calls')
    args = parser.parse_args()
    output = args.output.resolve()
    payload, manifest = prepare(output)
    if not args.run:
        print(json.dumps({'documents': len(payload['documents']), 'oversized_rows': len(payload['oversized_rows'])}))
        return
    image = 'vectornext-core:latest'
    identities = {}
    for name in (image, 'vectornext-processor-1', 'vectornext-llm-1'):
        command = ['docker', 'image', 'inspect', name] if name == image else ['docker', 'inspect', name]
        identities[name] = json.loads(subprocess.check_output(command))
    save(output / 'docker-identities.json', identities)
    command = ['docker', 'run', '--rm', '--network', 'vectornext_local', '--cpus', '4', '--memory', '6g',
        '--pids-limit', '128', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
        '--label', 'vectornext.measurement=T39-budget-preflight']
    for name in ('src', 'examples', 'Cargo.toml', 'Cargo.lock'):
        command += ['--mount', f'type=bind,source={ROOT / name},target=/app/{name},readonly']
    command += ['--mount', f'type=bind,source={output},target=/out', image,
        'cargo', 'run', '--locked', '--offline', '--features', 'measurement',
        '--example', 'measurement_table_preflight', '--', '/out/input.json', '/out/result', 'http://processor:8090']
    save(output / 'command.json', command)
    with (output / 'process.log').open('xb') as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=False)
    changed = [path for path, sha in manifest['source_files'].items() if digest((ROOT / path).read_bytes()) != sha]
    save(output / 'process.json', {'exit_code': result.returncode, 'changed_code': changed,
                                  'valid_preflight_identity': not changed})
    if result.returncode or changed:
        raise SystemExit('Preflight incomplete; retain process.log and all partial output')
    print(json.dumps({'output': str(output), 'state': 'captured_unscored_preflight'}))


if __name__ == '__main__':
    main()
