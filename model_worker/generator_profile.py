"""Trusted local generation profiles, shared by workers and the GPU launcher."""
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
CATALOG = Path(__file__).with_name('generator_profiles.json')
MODEL_PROFILES = {'gemma': '12b', 'nuextract': 'nuextract3-requested-facts-v1'}


def load(name=None):
    catalog = json.loads(CATALOG.read_bytes())
    if catalog['version'] != 1:
        raise ValueError('unsupported generation profile version')
    name = name or os.environ.get('VECTORNEXT_GENERATOR_PROFILE', catalog['default'])
    if name not in catalog['profiles']:
        raise ValueError('unknown generation profile: ' + name)
    entry = catalog['profiles'][name]
    cache_types(entry)
    template_options(entry)
    answer_temperature(entry)
    answer_adapter(entry)
    planning_variant(entry)
    lock_path = (ROOT / entry['lock']).resolve()
    if not lock_path.is_relative_to(ROOT):
        raise ValueError('model lock escapes application root')
    spec = json.loads(lock_path.read_bytes())['models']['generator']
    artifacts = [f for f in spec['files'] if f['path'].endswith('.gguf')]
    if len(artifacts) != 1:
        raise ValueError('expected one generation artifact')
    return dict(entry, name=name, runtime=catalog['runtime'], spec=spec, artifact=artifacts[0])


def cache_types(profile):
    kinds = (profile.get('cache_type_k'), profile.get('cache_type_v'))
    if kinds == (None, None):
        return None
    raise ValueError('experimental KV cache overrides are no longer supported')


def answer_temperature(profile):
    value = profile.get('answer_temperature', 0)
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 2:
        raise ValueError('answer temperature must be finite and between zero and two')
    return value


def answer_adapter(profile):
    adapter = profile.get('answer_adapter')
    if adapter not in (None, 'nuextract3-v1'):
        raise ValueError('unsupported answer template adapter')
    return adapter


def planning_variant(profile):
    variant = profile.get('planning_variant')
    if variant not in (None, 'requested-facts-v1'):
        raise ValueError('unsupported planning variant')
    if variant is not None and answer_adapter(profile) != 'nuextract3-v1':
        raise ValueError('requested-facts variant requires the NuExtract adapter')
    return variant


def model_path(profile, root=Path('/models')):
    path = (root / profile['spec']['directory'] / profile['artifact']['path']).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('generation artifact escapes model directory')
    return path


def template_options(profile):
    options = profile.get('chat_template_kwargs')
    if options is None:
        return None
    # Only the tested non-thinking mode is supported. No arbitrary template flags.
    if (not isinstance(options, dict) or set(options) != {'enable_thinking'}
            or options['enable_thinking'] is not False):
        raise ValueError('template options must explicitly disable thinking')
    return json.dumps(options, sort_keys=True, separators=(',', ':'))


def verify(profile, root=Path('/models')):
    path = model_path(profile, root)
    artifact = profile['artifact']
    if not path.is_file() or path.stat().st_size != artifact['size']:
        raise ValueError('missing/incomplete generation artifact')
    with path.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != artifact['sha256']:
        raise ValueError('corrupt generation artifact')
    return path


def command(profile):
    container_path = PurePosixPath('/models') / profile['spec']['directory'] / profile['artifact']['path']
    if '..' in container_path.parts or not container_path.is_relative_to('/models'):
        raise ValueError('generation artifact escapes model directory')
    args = ['--model', str(container_path), '--alias', profile['alias'],
            '--host', '0.0.0.0', '--port', '8080', '--ctx-size', '4096',
            '--n-gpu-layers', '99']
    if profile['cpu_moe']:
        args += ['--n-cpu-moe', str(profile['cpu_moe'])]
    if kinds := cache_types(profile):
        args += ['--cache-type-k', kinds[0], '--cache-type-v', kinds[1]]
    if options := template_options(profile):
        args += ['--chat-template-kwargs', options]
    return args + ['--parallel', '1', '--n-predict', '256', '--batch-size', '512',
                   '--ubatch-size', '128', '--threads', '4', '--flash-attn', 'on',
                   '--jinja', '--reasoning', 'off', '--no-context-shift', '--no-ui',
                   '--offline', '--verbosity', '4']


def validate_command(profile, args):
    expected = command(profile)
    if args and args != expected:
        raise ValueError('launch command does not match selected generation profile')
    return expected


def runtime_identity(profile):
    # Preserve the existing identity byte-for-byte for saved 26B offload jobs.
    identity = (profile['runtime'] + ';ctx4096;parallel1;reasoning-off;cpu-moe'
                + str(profile['cpu_moe']))
    kinds = cache_types(profile)
    identity += (';cache-k=' + kinds[0] + ';cache-v=' + kinds[1] if kinds else '')
    options = template_options(profile)
    identity += (';chat-template-kwargs=' + options if options else '')
    if 'answer_temperature' in profile:
        identity += ';answer-temperature=' + str(answer_temperature(profile))
    if adapter := answer_adapter(profile):
        identity += ';answer-adapter=' + adapter
    if variant := planning_variant(profile):
        identity += ';planning-variant=' + variant
    return identity
