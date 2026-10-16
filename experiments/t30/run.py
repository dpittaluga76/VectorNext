"""Q8 KV replay against retained T28, with unchanged API and two-call answering."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from deployment.client import Client
from evals.score import Scorer as T11Scorer
from evals.coverage.score import Scorer as T14Scorer
from evals.coverage.freeze import BLOCKS as T14_BLOCKS, public_inputs as t14_inputs, verify as verify_t14
from evals.independent.freeze import BLOCKS as T11_BLOCKS, public_inputs as t11_inputs
from .preflight import COMPOSE, NORMAL, ROOT, Samples, http, ready, shell, write
from model_worker.generator_profile import load, command

MODELS = ['12b-kv-q8']
IMAGES = ['vectornext-app:t30', 'vectornext-app-processor:t30', 'vectornext-app-llm:t30']
SUITES = {'t14': ('coverage', T14Scorer, T14_BLOCKS, t14_inputs),
          't11': ('independent', T11Scorer, [(n, 'ranked', p) for n, p in T11_BLOCKS], t11_inputs)}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def images():
    return {name: shell(['docker', 'image', 'inspect', name, '--format', '{{.Id}}']).stdout.strip()
            for name in IMAGES}


def execution_files():
    paths = set()
    for folder in ('src', 'model_worker', 'deployment', 'experiments/t30', 'experiments/t27', 'tests', 'frontend/e2e',
                   'evals/coverage', 'evals/independent'):
        paths.update(p for p in (ROOT/folder).rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts and p.suffix in {'.py', '.rs', '.json', '.md', '.txt', '.pdf', '.ts'})
    paths.update(ROOT/p for p in ['Cargo.toml', 'Cargo.lock', 'evals/score.py',
        'experiments/t02/models.lock.json', 'experiments/t02/models.26b.lock.json',
        'experiments/t02/encoders.py', 'experiments/t02/fetch_models.py',
        'processor/models.lock.json', 'compose.app.yaml', 'compose.app.models.yaml', 'compose.t30.yaml',
        'experiments/t30/processor.Dockerfile', 'experiments/t30/generator.Dockerfile', 'docker/app.Dockerfile', 'docker/app-processor.Dockerfile', 'docker/app-llm.Dockerfile'])
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(paths)}


def validate_inputs():
    verify_t14('data')
    # T11 combined its data/runtime freeze. Verify only its unchanged public corpus,
    # labels, requests and scorer here; T30 binds today's runtime separately.
    original = json.loads((ROOT/'evals/independent/freeze.json').read_bytes())
    for name, expected in original['files'].items():
        if name.startswith('evals/independent/') or name == 'evals/score.py':
            if digest(ROOT/name) != expected:
                raise ValueError('historical data/scorer changed: ' + name)
    for folder, _, _, public_inputs in SUITES.values():
        here = ROOT/'evals'/folder
        data, requests = [json.loads((here/p).read_bytes()) for p in ('dataset.json', 'requests.json')]
        public_inputs(data, requests)
        for doc in data['documents']:
            if digest(here/doc['path']) != doc['sha256']:
                raise ValueError('source hash mismatch: ' + doc['id'])


BASELINE = ROOT/'data/t28/replay-v1'

def baseline_identity():
    paths = [BASELINE/'execution-freeze.json', BASELINE/'complete.json']
    for suite, (_, _, blocks, _) in SUITES.items():
        paths += [BASELINE/suite/'documents.json', BASELINE/suite/'ingestion/complete.json']
        for block, _, _ in blocks:
            for model in ('12b',):
                folder = BASELINE/suite/block/model
                paths += list(folder.glob('*.json'))
    return {p.relative_to(BASELINE).as_posix(): digest(p) for p in sorted(set(paths))}


def freeze(target):
    validate_inputs()
    prior = json.loads((BASELINE/'execution-freeze.json').read_bytes())['images']
    current = images()
    for role in ('vectornext-app',):
        if current[role+':t30'] != prior[role+':t28']:
            raise ValueError('API/generator differs from retained baseline')
    value = {'created': datetime.now(timezone.utc).isoformat(),
             'baseline': baseline_identity(),
             'copy_manifest': digest(ROOT/'data/t30'/(target.name+'-corpus-copy.json')),
             'commit': shell(['git', 'rev-parse', 'HEAD']).stdout.strip(),
             'files': execution_files(), 'images': images(), 'requests': 208, 'holdout_run': False, 'api': 'retained T28 image; range extension excluded', 'answer_mode': 'two_call', 'profile_command': command(load('12b-kv-q8'))}
    path = target/'execution-freeze.json'
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
    return value


def verify(target):
    value = json.loads((target/'execution-freeze.json').read_bytes())
    if (execution_files() != value['files'] or images() != value['images']
            or baseline_identity() != value['baseline']
            or digest(ROOT/'data/t30'/(target.name+'-corpus-copy.json')) != value['copy_manifest']):
        raise ValueError('T30 execution identity changed; preserve attempt and use a new run')
    validate_inputs()
    return value


def evidence_ids(case):
    expected = case['expected']
    return set(e for group in expected.get('support_sets', []) for e in group) | set(
        e for alternative in expected.get('alternatives', []) for e in alternative['support_set'])


class Run:
    def __init__(self, name):
        if not name.replace('-', '').isalnum():
            raise ValueError('fresh alphanumeric run name required')
        self.name = name
        self.root = ROOT/'data/t30'/name
        self.root.mkdir(exist_ok=True)
        self.client = Client('http://127.0.0.1:8100')
        self.env = os.environ.copy()
        self.active_model = None

    def compose(self, *args):
        return shell(COMPOSE + list(args), self.env).stdout

    def call(self, path, body=None, expected=200):
        status, value = self.client.request(path, body)
        if status != expected:
            raise RuntimeError((path, status, value))
        return value

    def snapshot(self):
        return {d['document_id']: self.call('/v1/document', {'document_id': d['document_id']})['document']
                for d in self.call('/v1/documents')['documents']}

    def select(self, suite, model, strategy, target):
        self.env.update(VECTORNEXT_GENERATOR_PROFILE=model,
                        T30_DATABASE='/storage/' + self.name + '/' + suite,
                        T30_CACHE='/cache/' + self.name + '/' + suite + '/' + model + '/' + strategy)
        started = time.monotonic()
        if self.active_model != model:
            if self.active_model:
                (target/'previous-generator.log').write_text(self.compose('logs', '--no-color', 'llm'), encoding='utf-8')
            self.compose('stop', 'llm')
            self.compose('up', '-d', '--no-build', '--pull', 'never', '--force-recreate', 'llm')
            ready()
            warmup = {'model': load(model)['alias'],
                      'messages': [{'role': 'user', 'content': 'Return the integer 7 as JSON.'}],
                      'temperature': 0, 'seed': 42, 'max_tokens': 16, 'cache_prompt': False, 'reasoning': 'off',
                      'response_format': {'type': 'json_schema', 'json_schema': {'name': 'warmup', 'strict': True,
                          'schema': {'type': 'object', 'properties': {'value': {'const': 7}},
                                     'required': ['value'], 'additionalProperties': False}}}}
            code, raw = http('/v1/chat/completions', warmup)
            (target/'warmup.json').write_bytes(raw)
            if code != 200:
                raise RuntimeError('synthetic warmup failed')
            self.active_model = model
        self.compose('up', '-d', '--no-build', '--pull', 'never', '--force-recreate', 'vectornext', 'processor')
        ready(base='http://127.0.0.1:8100', path='/readyz')
        write(target/'startup.json', {'seconds': time.monotonic()-started,
            'images': images(), 'profile': model, 'database': self.env['T30_DATABASE'], 'cache': self.env['T30_CACHE']})
        (target/'compose.json').write_text(self.compose('config', '--format', 'json'), encoding='utf-8')

    def ingest(self, suite, here, data):
        # Storage was copied while stopped, with hashes verified before this run.
        target = self.root/suite/'ingestion'
        target.mkdir(parents=True, exist_ok=True)
        import shutil
        for relative in ('documents.json', 'ingestion/complete.json'):
            source, output = BASELINE/suite/relative, self.root/suite/relative
            if output.exists() and output.read_bytes() != source.read_bytes():
                raise ValueError('copied corpus metadata differs from T27')
            if not output.exists(): shutil.copyfile(source, output)
        return json.loads((self.root/suite/'documents.json').read_bytes())

    def block(self, suite, block, model, strategy, primary, data, requests, cases, documents, scorer_type):
        target = self.root/suite/block/model
        if (target/'complete.json').exists():
            return
        target.mkdir(parents=True, exist_ok=True)
        verify(self.root)
        attempt = target/f'start-{time.time_ns()}'
        attempt.mkdir()
        self.select(suite, model, block.split('-')[0], attempt)
        if self.snapshot() != documents:
            raise ValueError('committed corpus changed between paired blocks')
        scorer = scorer_type(data, documents)
        refs = {e['id']: e['document_id'] for e in data['evidence']}
        options = {'candidates': 30, 'rerank_limit': 20, 'primary_limit': primary,
                   'rerank': True, 'evidence_strategy': strategy}
        sampler = Samples(services=('vectornext', 'processor', 'llm'))
        sampler.thread.start()
        rows = []
        try:
            for identifier, case in cases.items():
                row_path = target/(identifier+'.row.json')
                marker = target/(identifier+'.attempt.json')
                if row_path.exists():
                    rows.append(json.loads(row_path.read_bytes()))
                    continue
                if marker.exists():
                    # Unknown interrupted outcome is a failed attempt, never a retry.
                    row = {'case': identifier, 'http_status': 0, 'wall_seconds': None, 'score': None,
                           'error': 'interrupted request outcome unknown; not resubmitted'}
                    write(row_path, row)
                    rows.append(row)
                    continue
                before = self.call('/v1/metrics')
                with marker.open('x', encoding='utf-8') as stream:
                    json.dump({'utc': datetime.now(timezone.utc).isoformat(), 'options': options}, stream)
                started = time.monotonic()
                try:
                    code, report = self.client.request('/v1/ask', {'request': requests[identifier], 'options': options})
                    raw, error = self.client.raw, None
                except Exception as failure:
                    code, report, raw, error = 0, None, b'', str(failure)
                wall = time.monotonic()-started
                if raw:
                    (target/(identifier+'.json')).write_bytes(raw)
                score, scoring_error = None, None
                if code == 200:
                    try:
                        score = scorer.case(case, report)
                    except Exception as failure:
                        scoring_error = str(failure)
                try:
                    after = self.call('/v1/metrics')
                except Exception as failure:
                    after = {'error': str(failure)}
                row = {'case': identifier, 'http_status': code, 'wall_seconds': wall, 'score': score,
                       'report_sha256': hashlib.sha256(raw).hexdigest() if raw else None,
                       'scoring_error': scoring_error, 'error': error,
                       'before': before, 'after': after,
                       'unavailable_source_documents': sorted({refs[e] for e in evidence_ids(case)}-documents.keys())}
                write(row_path, row)
                rows.append(row)
                print(suite, block, model, identifier, code, round(wall, 2),
                      score['answer_correct'] if score else False, flush=True)
        finally:
            sampler.stop.set()
            sampler.thread.join(10)
            write(attempt/'samples.json', sampler.values)
        write(target/'complete.json', {'cases': rows, 'options': options})

    def run(self):
        verify(self.root)
        stopped = False
        try:
            running = shell(['docker', 'inspect', NORMAL, '--format', '{{.State.Running}}'], check=False)
            if running.returncode == 0 and running.stdout.strip() == 'true':
                code, raw = http('/scheduler', base='docker://'+NORMAL)
                state = json.loads(raw)
                if code != 200 or state['active'] or state['interactive_waiting'] or state['background_waiting']:
                    raise RuntimeError('normal generation work is active')
                status, library = http('/v1/ui/library', base='http://127.0.0.1:8088')
                if status != 200: raise RuntimeError('cannot capture normal library')
                (self.root/'normal-library-before.json').write_bytes(library)
                shell(['docker', 'stop', NORMAL])
                stopped = True
            for suite, (folder, scorer, blocks, public_inputs) in SUITES.items():
                here = ROOT/'evals'/folder
                data, requests = [json.loads((here/p).read_bytes()) for p in ('dataset.json', 'requests.json')]
                cases = public_inputs(data, requests)
                documents = self.ingest(suite, here, data)
                for index, (block, strategy, primary) in enumerate(blocks):
                    for model in MODELS if index % 2 == 0 else reversed(MODELS):
                        self.block(suite, block, model, strategy, primary, data, requests, cases, documents, scorer)
            verify(self.root)
            write(self.root/'complete.json', {'requests': 208, 'finished': datetime.now(timezone.utc).isoformat()})
        finally:
            (self.root/f'generator-{time.time_ns()}.log').write_text(self.compose('logs', '--no-color', 'llm'), encoding='utf-8')
            self.compose('stop', 'vectornext', 'processor', 'llm')
            if stopped:
                shell(['docker', 'start', NORMAL])
                restored = ready(base='http://127.0.0.1:8088', path='/readyz')
                status, after = http('/v1/ui/library', base='http://127.0.0.1:8088')
                (self.root/'normal-library-after.json').write_bytes(after)
                write(self.root/'restoration.json', {'seconds': restored, 'library_unchanged': status == 200 and after == library})
                if status != 200 or after != library: raise RuntimeError('normal library changed')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--freeze', action='store_true')
    parser.add_argument('--preflight', type=Path, required=True)
    args = parser.parse_args()
    preflight = json.loads(args.preflight.read_bytes())
    if not preflight['passed'] or preflight['profile'] != '12b-kv-q8':
        raise ValueError('passing 12B preflight required')
    if preflight['image'] != images()['vectornext-app-llm:t30'] or preflight['command'] != command(load('12b-kv-q8')):
        raise ValueError('generator image/configuration differs from passing preflight')
    run = Run(args.run)
    if args.freeze:
        freeze(run.root)
        write(run.root/'preflight.json', preflight)
        import zipfile
        with zipfile.ZipFile(run.root/'source.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
            for path in execution_files(): archive.write(ROOT/path, path)
    run.run()


if __name__ == '__main__':
    main()
