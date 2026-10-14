"""CPU checks against real pinned MiniLM, with injected generation responses."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .cache import Cache, canonical, digest
from .server import Worker


class CacheTests(unittest.TestCase):
    def test_corruption_miss_and_bound(self):
        with tempfile.TemporaryDirectory() as root:
            c = Cache(root, max_bytes=600)
            for i in range(20):
                c.put(digest(i), "data" * 20)
            self.assertLessEqual(sum(p.stat().st_size for p in Path(root).iterdir()), 600)
            key = digest(19)
            self.assertEqual(c.get(key), (True, "data" * 20))
            p = Path(root) / (key + ".json")
            entry = json.loads(p.read_bytes()); entry["value"] = "corrupted"
            p.write_bytes(canonical(entry))
            self.assertEqual(c.get(key), (False, None))
            c.put(key, None)
            self.assertEqual(c.get(key), (True, None))


class WorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        with patch.dict(os.environ, {"VECTORNEXT_CACHE": cls.temp.name}):
            cls.worker = Worker()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def context(self):
        w = self.worker
        return {"space": w.space, "config": {"policy": "generated", "version": "prose-scope8000-reserve64-v1", "generator": w.generator},
                "evidence": "He scored three goals.", "structural_context": "Cup", "scope": [
                    {"span": {"block_id": "b0", "bytes": {"start": 0, "end": 23}}, "text": "Pele played in the Cup.", "sources": []}]}

    def mock_http(self, path, payload):
        if path == "/apply-template": return {"prompt": "rendered chat"}
        if path == "/tokenize": return {"tokens": [1] * 50}
        self.assertEqual(payload["temperature"], 0)
        return {"choices": [{"finish_reason": "stop", "message": {"content": '{"context":"Pele in the Cup."}'}}]}

    def test_real_embedding_and_no_truncation(self):
        w = self.worker
        a = w.handle({"op": "embed", "input": "A soccer player scored a goal."})
        b = w.handle({"op": "embed", "input": "A soccer player scored a goal."})
        self.assertEqual(a, b); self.assertEqual(len(a), 384)
        self.assertAlmostEqual(sum(x*x for x in a), 1, places=5)
        self.assertEqual(w.count(""), 2)
        with self.assertRaisesRegex(ValueError, "token limit"):
            w.handle({"op": "embed", "input": "goal " * 300})

    def test_context_cache_exact_inputs_and_invalidation(self):
        w = self.worker
        original = self.context()
        with patch.object(w, "http", side_effect=self.mock_http) as http:
            self.assertEqual(w.generate(original), "Pele in the Cup.")
            self.assertEqual(http.call_count, 3)
            self.assertEqual(w.generate(original), "Pele in the Cup.")
            self.assertEqual(http.call_count, 3)
            changed = copy.deepcopy(original); changed["structural_context"] += " new heading"
            w.generate(changed); self.assertEqual(http.call_count, 6)
            changed["scope"][0]["text"] += " Another passage."
            w.generate(changed); self.assertEqual(http.call_count, 9)
        changed = copy.deepcopy(original); changed["config"]["generator"]["revision"] = "other"
        with self.assertRaisesRegex(ValueError, "configuration mismatch"): w.generate(changed)

    def test_outage_overflow_and_bad_format_do_not_cache(self):
        w = self.worker; value = self.context(); value["evidence"] += " outage"
        with patch.object(w, "http", side_effect=ConnectionError("down")):
            with self.assertRaises(ConnectionError): w.generate(value)
        with patch.object(w, "http", side_effect=[{"prompt": "x"}, {"tokens": [1] * 4000}]):
            with self.assertRaisesRegex(ValueError, "budget"): w.generate(value)
        with patch.object(w, "http", side_effect=[{"prompt": "x"}, {"tokens": [1]},
                {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]}]):
            with self.assertRaisesRegex(ValueError, "finish"): w.generate(value)
        with patch.object(w, "http", side_effect=self.mock_http):
            self.assertEqual(w.generate(value), "Pele in the Cup.")

    def test_annotation_budget_and_schema(self):
        w = self.worker; value = self.context(); value["evidence"] += " invalid"
        with self.assertRaisesRegex(ValueError, "reservation"):
            w.validate_annotation("goal " * 80, value)
        with patch.object(w, "http", side_effect=[{"prompt": "x"}, {"tokens": [1]},
                {"choices": [{"finish_reason": "stop", "message": {"content": '{"other":3}'}}]}]):
            with self.assertRaisesRegex(ValueError, "schema"): w.generate(value)


if __name__ == "__main__": unittest.main()
