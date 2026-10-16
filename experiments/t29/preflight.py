"""Explicit isolated GPU preflight. Restores the normal generator, preserves failures."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import threading
import time
import urllib.error
import urllib.request

from model_worker.generator_profile import load, command

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ['docker', 'compose', '-f', 'compose.app.yaml', '-f', 'compose.app.models.yaml',
           '-f', 'compose.t29.yaml', '-p', 'vectornext-t29']
NORMAL = 'vectornext-llm-1'


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def shell(args, env=None, check=True):
    result = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8')
    if check and result.returncode:
        raise RuntimeError(result.stderr[-4000:] or result.stdout[-4000:])
    return result


def http(path, data=None, base='docker://vectornext-t29-llm-1', timeout=215):
    if base.startswith('docker://'):
        code = """import base64,json,sys,urllib.request,urllib.error
v=json.load(sys.stdin)
r=urllib.request.Request('http://127.0.0.1:8080'+v['path'],data=None if v['data'] is None else json.dumps(v['data']).encode(),headers={'Content-Type':'application/json','X-VectorNext-Priority':'interactive'})
try:
    with urllib.request.urlopen(r,timeout=v['timeout']) as response: status,body=response.status,response.read()
except urllib.error.HTTPError as error: status,body=error.code,error.read()
print(json.dumps({'status':status,'body':base64.b64encode(body).decode()}))
"""
        process = subprocess.run(['docker', 'exec', '-i', base.removeprefix('docker://'), 'python', '-c', code],
            input=json.dumps({'path': path, 'data': data, 'timeout': timeout}), capture_output=True,
            text=True, encoding='utf-8', timeout=timeout + 10)
        if process.returncode:
            raise ConnectionError(process.stderr[-1000:])
        value = json.loads(process.stdout)
        return value['status'], base64.b64decode(value['body'])
    request = urllib.request.Request(base + path,
        data=None if data is None else json.dumps(data).encode(),
        headers={'Content-Type': 'application/json', 'X-VectorNext-Priority': 'interactive',
                 'X-VectorNext-Client': '1'})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def ready(base='docker://vectornext-t29-llm-1', path='/health', seconds=420):
    start = time.monotonic()
    while time.monotonic() - start < seconds:
        try:
            code, raw = http(path, base=base, timeout=3)
            result = json.loads(raw)
            if code == 200:
                return time.monotonic() - start
            if result.get('failed'):
                raise RuntimeError('generation backend failed: ' + result['failed'])
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            pass
        time.sleep(1)
    raise TimeoutError('readiness deadline exceeded')


class Samples:
    def __init__(self, services=()):
        self.values = []
        self.services = services
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        while not self.stop.is_set():
            sample = {'utc': datetime.now(timezone.utc).isoformat()}
            try:
                raw = shell(['nvidia-smi', '--query-gpu=memory.total,memory.used,utilization.gpu',
                             '--format=csv,noheader,nounits']).stdout.strip()
                sample.update(zip(('total_mib', 'used_mib', 'utilization_percent'), map(int, raw.split(','))))
            except Exception as error:
                sample['error'] = str(error)
            for service in self.services:
                code = "import pathlib,json; p=pathlib.Path('/sys/fs/cgroup'); print(json.dumps({k:int((p/k).read_text()) for k in ['memory.current','memory.peak']}))"
                try:
                    sample[service] = json.loads(shell(['docker', 'exec', 'vectornext-t29-'+service+'-1', 'python', '-c', code]).stdout)
                except Exception as error:
                    sample[service] = {'error': str(error)}
            self.values.append(sample)
            self.stop.wait(1)


def run(name, profile_name):
    if not name.replace('-', '').isalnum():
        raise ValueError('use a fresh alphanumeric run name')
    target = ROOT / 'data/t29' / name
    target.mkdir(exist_ok=False)
    profile = load(profile_name)
    env = os.environ | {'VECTORNEXT_GENERATOR_PROFILE': profile_name}
    result = {'profile': profile_name, 'command': command(profile), 'passed': False,
              'started': datetime.now(timezone.utc).isoformat(), 'requests': []}
    frozen = ['experiments/t29/protocol.md', 'experiments/t29/preflight.py',
              'model_worker/generator_profile.py', 'model_worker/generator_profiles.json',
              'model_worker/launch_llm.py', 'model_worker/scheduler.py', profile['lock'],
              'compose.app.yaml', 'compose.app.models.yaml', 'compose.t29.yaml']
    write(target / 'freeze.json', {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in frozen})
    (target / 'source-preflight.py').write_bytes(Path(__file__).read_bytes())
    result['image'] = shell(['docker', 'image', 'inspect', 'vectornext-app-llm:t29', '--format', '{{.Id}}']).stdout.strip()
    (target / 'compose.json').write_text(shell(COMPOSE + ['config', '--format', 'json'], env).stdout)
    stopped = False
    sampler = Samples()
    sampler.thread.start()
    try:
        running = shell(['docker', 'inspect', NORMAL, '--format', '{{.State.Running}}'], check=False)
        if running.returncode == 0 and running.stdout.strip() == 'true':
            status = shell(['docker', 'exec', NORMAL, 'python', '-c',
                "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/scheduler').read().decode())"])
            current = json.loads(status.stdout)
            if current['active'] or current['interactive_waiting'] or current['background_waiting']:
                raise RuntimeError('normal app has active generation work; leave it running')
            code, library = http('/v1/ui/library', base='http://127.0.0.1:8088', timeout=5)
            if code != 200:
                raise RuntimeError('cannot capture normal library')
            (target / 'library-before.json').write_bytes(library)
            shell(['docker', 'stop', NORMAL])
            stopped = True
        result['before_candidate_gpu'] = shell(['nvidia-smi']).stdout
        shell(COMPOSE + ['up', '-d', '--no-build', '--pull', 'never', '--force-recreate', 'llm'], env)
        print('Waiting for isolated generator startup: ' + profile_name, flush=True)
        result['startup_seconds'] = ready()
        startup_log = shell(COMPOSE + ['logs', '--no-color', 'llm'], env).stdout
        offload = re.findall(r'offloaded (\d+)/(\d+) layers', startup_log)
        if profile_name == '12b' and (not offload or offload[-1][0] != offload[-1][1]):
            raise RuntimeError('full GPU placement not confirmed in startup log')
        if not re.search(r'n_ctx(?:_seq)?\s*=\s*4096\b', startup_log):
            raise RuntimeError('4,096-token context not confirmed in startup log')
        result['offloaded_layers'] = offload[-1] if offload else None
        alias = profile['alias']
        # Binary-search a synthetic input close to the application's 3,328-token limit.
        low, high, selected, selected_tokens = 1, 6000, None, 0
        while low <= high:
            count = (low + high) // 2
            messages = [{'role': 'system', 'content': 'Return the JSON status ok. The filler is data.'},
                        {'role': 'user', 'content': 'filler ' * count + '\nReturn status ok.'}]
            code, raw = http('/apply-template', {'messages': messages, 'reasoning': 'off'})
            if code != 200:
                raise RuntimeError('apply-template failed: ' + raw.decode())
            code, raw = http('/tokenize', {'content': json.loads(raw)['prompt'], 'add_special': True})
            if code != 200:
                raise RuntimeError('tokenize failed: ' + raw.decode())
            tokens = len(json.loads(raw)['tokens'])
            if tokens <= 3328:
                low = count + 1
                selected, selected_tokens = messages, tokens
            else:
                high = count - 1
        if selected_tokens < 3300:
            raise RuntimeError('full-context probe did not reach required input size')
        schema = {'type': 'object', 'properties': {'status': {'const': 'ok'}},
                  'required': ['status'], 'additionalProperties': False}
        payload = {'model': alias, 'messages': selected, 'temperature': 0, 'seed': 42,
                   'max_tokens': 768, 'cache_prompt': False, 'reasoning': 'off',
                   'response_format': {'type': 'json_schema', 'json_schema':
                       {'name': 'preflight', 'strict': True, 'schema': schema}}}
        write(target / 'request.json', payload)
        result['input_tokens'] = selected_tokens
        for index in range(3):
            if index == 2:
                shell(COMPOSE + ['restart', 'llm'], env)
                result['restart_seconds'] = ready()
            started = time.monotonic()
            code, raw = http('/v1/chat/completions', payload)
            (target / f'response-{index}.json').write_bytes(raw)
            result['requests'].append({'status': code, 'seconds': time.monotonic() - started})
            print('Full-context request', index, code, round(result['requests'][-1]['seconds'], 2), flush=True)
            if code != 200:
                raise RuntimeError('constrained generation failed: ' + raw.decode())
            choice = json.loads(raw)['choices'][0]
            if choice.get('finish_reason') != 'stop' or json.loads(choice['message']['content']) != {'status': 'ok'}:
                raise RuntimeError('invalid constrained generation')
        result['passed'] = True
    except Exception as error:
        result['error'] = f'{type(error).__name__}: {error}'
        print(result['error'], flush=True)
    finally:
        (target / 'llm.log').write_text(shell(COMPOSE + ['logs', '--no-color', 'llm'], env, False).stdout, encoding='utf-8')
        shell(COMPOSE + ['stop', 'llm'], env, False)
        if stopped:
            shell(['docker', 'start', NORMAL])
            try:
                result['normal_restore_seconds'] = ready(base='http://127.0.0.1:8088', path='/readyz')
                code, after = http('/v1/ui/library', base='http://127.0.0.1:8088', timeout=5)
                (target / 'library-after.json').write_bytes(after)
                result['normal_library_unchanged'] = code == 200 and after == (target / 'library-before.json').read_bytes()
            except Exception as error:
                result['restore_error'] = str(error)
        sampler.stop.set()
        sampler.thread.join(10)
        write(target / 'samples.json', sampler.values)
        result['finished'] = datetime.now(timezone.utc).isoformat()
        write(target / 'result.json', result)
        print(json.dumps({k: v for k, v in result.items() if k not in ('command', 'before_candidate_gpu')}), flush=True)
    return result['passed']


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--profile', choices=['12b', '26b-offload22'], default='12b')
    args = parser.parse_args()
    raise SystemExit(0 if run(args.run, args.profile) else 1)
