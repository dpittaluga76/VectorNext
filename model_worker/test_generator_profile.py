import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import generator_profile as profiles
from .cache import digest
from .scheduler import validate, Rejected


class GeneratorProfileTests(unittest.TestCase):
    def test_only_two_supported_profiles_and_stable_gemma_identity(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(profiles.load()['name'], '12b')
            with self.assertRaises(ValueError): profiles.load('26b-offload22')

    def test_legacy_identity_and_cpu_models_unchanged(self):
        old = profiles.load('12b')
        self.assertEqual(profiles.runtime_identity(old),
            'llama.cpp-b11617-14310190cd0a0c831fe949ac8cbedd8abdc90695;ctx4096;parallel1;reasoning-off;cpu-moe0')
        original = json.loads((profiles.ROOT / old['lock']).read_bytes())
        candidate = json.loads((profiles.ROOT / profiles.load('12b')['lock']).read_bytes())
        for role in ('embedding', 'reranker'):
            self.assertEqual(original['models'][role], candidate['models'][role])

    def test_full_gpu_and_offload_commands_are_bound(self):
        for name in ('12b', 'nuextract3-requested-facts-v1'):
            profile = profiles.load(name)
            args = profiles.command(profile)
            self.assertEqual(profiles.validate_command(profile, []), args)
            self.assertEqual(profiles.validate_command(profile, args), args)
            self.assertEqual('--n-cpu-moe' in args, name == '26b-offload22')
            bad = list(args)
            bad[bad.index('--ctx-size') + 1] = '2048'
            with self.assertRaisesRegex(ValueError, 'does not match'):
                profiles.validate_command(profile, bad)
        with patch.dict(os.environ, {'VECTORNEXT_GENERATOR_PROFILE': 'missing'}):
            with self.assertRaisesRegex(ValueError, 'unknown generation profile'):
                profiles.load()

    def test_scheduler_only_accepts_selected_alias(self):
        for name in ('12b', 'nuextract3-requested-facts-v1'):
            alias = profiles.load(name)['alias']
            request = {'model': alias, 'max_tokens': 768, 'temperature': profiles.answer_temperature(profiles.load(name))}
            validate('/v1/chat/completions', json.dumps(request), 'interactive', alias, profiles.answer_temperature(profiles.load(name)))
            wrong = profiles.load('12b' if name != '12b' else 'nuextract3-requested-facts-v1')['alias']
            with self.assertRaises(Rejected):
                validate('/v1/chat/completions', json.dumps(request), 'interactive', wrong)
            with self.assertRaises(Rejected):
                validate('/v1/chat/completions', json.dumps(request), 'background', alias)

    def test_artifact_verification_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = copy.deepcopy(profiles.load('12b'))
            profile['spec']['directory'] = 'fixture'
            profile['artifact'].update(path='test.gguf', size=3, sha256=hashlib.sha256(b'abc').hexdigest())
            with self.assertRaisesRegex(ValueError, 'missing/incomplete'):
                profiles.verify(profile, root)
            path = root / 'fixture/test.gguf'
            path.parent.mkdir()
            path.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError, 'corrupt'):
                profiles.verify(profile, root)
            path.write_bytes(b'abc')
            self.assertEqual(profiles.verify(profile, root), path)
            profile['artifact']['path'] = '../../escape.gguf'
            with self.assertRaisesRegex(ValueError, 'escapes'):
                profiles.model_path(profile, root)

    def test_generation_cache_identity_separates_models_and_placement(self):
        identities = []
        for name in ('12b', 'nuextract3-requested-facts-v1'):
            profile = profiles.load(name)
            identities.append({'model': profile['spec']['repo'],
                'revision': profile['spec']['revision'],
                'artifact_sha256': profile['artifact']['sha256'],
                'runtime': profiles.runtime_identity(profile)})
        self.assertEqual(len({digest({'operation': 'context-v1', 'input': {'config': {'generator': i}}})
                              for i in identities}), 2)


if __name__ == '__main__':
    unittest.main()
