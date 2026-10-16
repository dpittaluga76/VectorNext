import copy
import json
import unittest
from model_worker.generator_profile import load, command, runtime_identity, validate_command
from model_worker.scheduler import validate, Rejected
from model_worker.cache import digest


class KvProfileTests(unittest.TestCase):
    def test_only_kv_types_and_alias_change(self):
        old, new = load('12b'), load('12b-kv-q8')
        self.assertEqual(old['spec'], new['spec'])
        args = command(new)
        self.assertEqual(args[args.index('--cache-type-k')+1], 'q8_0')
        self.assertEqual(args[args.index('--cache-type-v')+1], 'q8_0')
        stripped = args[:]
        for flag in ('--cache-type-k', '--cache-type-v'):
            at = stripped.index(flag); del stripped[at:at+2]
        stripped[stripped.index('--alias')+1] = old['alias']
        self.assertEqual(stripped, command(old))
        self.assertNotEqual(runtime_identity(old), runtime_identity(new))
        self.assertNotEqual(digest({'generator': runtime_identity(old)}), digest({'generator': runtime_identity(new)}))
        with self.assertRaises(ValueError): validate_command(new, command(old))

    def test_partial_unknown_and_mismatched_config_fail_closed(self):
        for k,v in [('q8_0',None), ('q4_0','q4_0'), (None,'f16')]:
            profile = copy.deepcopy(load('12b')); profile.update(cache_type_k=k, cache_type_v=v)
            with self.assertRaises(ValueError): command(profile)
            with self.assertRaises(ValueError): runtime_identity(profile)
        profile = load('12b-kv-q8')
        request = json.dumps({'model': load('12b')['alias'], 'max_tokens': 768, 'temperature': 0})
        with self.assertRaises(Rejected): validate('/v1/chat/completions',request,'interactive',profile['alias'])


if __name__ == '__main__': unittest.main()
