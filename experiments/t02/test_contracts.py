import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from jsonschema import Draft202012Validator

from .benchmark import DATASET, answer_schema, messages_for, prepare, request_payload
from .encoders import mean_pool_normalize
from .fetch_models import artifact_path, download_ranges, fetch, verify


class ModelContractTests(unittest.TestCase):
    def test_status_schema_rejects_fields_on_non_answers(self):
        validator = Draft202012Validator(answer_schema(["goals"], "status"))
        for status in ["ambiguous", "insufficient_evidence"]:
            self.assertTrue(validator.is_valid({"status": status, "fields": {}, "source_ids": []}))
            for fields in [{"goals": None}, {"goals": 0}, {"unexpected": 1}]:
                self.assertFalse(validator.is_valid({"status": status, "fields": fields, "source_ids": []}))

    def test_status_schema_preserves_supported_null_and_zero(self):
        validator = Draft202012Validator(answer_schema(["assists"], "status"))
        for value in [None, 0, 3]:
            self.assertTrue(validator.is_valid({"status": "supported", "fields": {"assists": value}, "source_ids": ["source"]}))
        for fields in [{}, {"assists": "0"}, {"assists": False}, {"assists": 0, "extra": 1}]:
            self.assertFalse(validator.is_valid({"status": "supported", "fields": fields, "source_ids": ["source"]}))

    def test_status_schema_requires_every_requested_field(self):
        validator = Draft202012Validator(answer_schema(["year", "goals", "opponent"], "status"))
        self.assertFalse(validator.is_valid({"status": "supported", "fields": {"goals": 3}, "source_ids": ["source"]}))
        self.assertTrue(validator.is_valid({"status": "supported", "fields": {"year": 1954, "goals": 3, "opponent": "Argentina"}, "source_ids": ["source"]}))

    def test_schema_experiment_changes_only_response_format(self):
        passages, cases = prepare(json.loads(DATASET.read_text()))
        case = copy.deepcopy(cases[0])
        case["expected"] = {"sentinel": "DO_NOT_LEAK_GOLD_91234"}
        before, _ = request_payload(case, passages, schema_mode="legacy")
        after, _ = request_payload(case, passages, schema_mode="status")
        self.assertNotEqual(before.pop("response_format"), after.pop("response_format"))
        self.assertEqual(before, after)
        self.assertNotIn("DO_NOT_LEAK_GOLD_91234", json.dumps(request_payload(case, passages, schema_mode="status")))

    def test_range_download_resumes_prefix_without_gaps(self):
        content = b"abcdefghijklmnopqrstuvwxyz"

        def response_for(request, timeout):
            first, last = map(int, request.headers["Range"].removeprefix("bytes=").split("-"))
            response = io.BytesIO(content[first:last + 1])
            response.status = 206
            response.headers = {"Content-Range": f"bytes {first}-{last}/{len(content)}"}
            return response

        with tempfile.TemporaryDirectory() as directory:
            partial = Path(directory) / "model.part"
            partial.write_bytes(content[:3])
            with patch("experiments.t02.fetch_models.urlopen", side_effect=response_for):
                download_ranges("https://example.invalid/model", partial, len(content), workers=2, chunk_size=4)
            self.assertEqual(partial.read_bytes(), content)

    def test_range_download_rejects_ignored_range(self):
        response = io.BytesIO(b"not the requested bytes")
        response.status = 200
        response.headers = {}
        with tempfile.TemporaryDirectory() as directory:
            partial = Path(directory) / "model.part"
            partial.write_bytes(b"prefix")
            with patch("experiments.t02.fetch_models.urlopen", return_value=response):
                with self.assertRaisesRegex(ValueError, "exact download range"):
                    download_ranges("https://example.invalid/model", partial, 10, workers=1)
            self.assertEqual(partial.read_bytes(), b"prefix")

    def test_pooling_ignores_padding_and_normalizes(self):
        hidden = np.array([[[3, 4], [999, 999]], [[1, 0], [0, 1]]], dtype=np.float32)
        result = mean_pool_normalize(hidden, np.array([[1, 0], [1, 1]]))
        np.testing.assert_allclose(result, [[0.6, 0.8], [2 ** -0.5, 2 ** -0.5]], atol=1e-7)
        self.assertEqual(result.dtype, np.float32)

    def test_pooling_rejects_invalid_vectors(self):
        for hidden, mask in [(np.zeros((1, 1, 2)), np.ones((1, 1))), (np.ones((1, 1, 2)), np.zeros((1, 1))), (np.full((1, 1, 2), np.nan), np.ones((1, 1)))]:
            with self.assertRaises(ValueError):
                mean_pool_normalize(hidden, mask)

    def test_holdout_and_answer_labels_do_not_enter_prompts(self):
        data = json.loads(DATASET.read_text())
        passages, cases = prepare(data)
        self.assertTrue(all(case["split"] == "dev" for case in cases))
        case = copy.deepcopy(cases[0])
        case["expected"] = {"fields": {"sentinel": "DO_NOT_LEAK_GOLD_91234"}}
        messages, _ = messages_for(case, passages)
        self.assertNotIn("DO_NOT_LEAK_GOLD_91234", json.dumps(messages))
        case["split"] = "holdout"
        with self.assertRaisesRegex(ValueError, "Holdout"):
            messages_for(case, passages)

    def test_local_model_integrity_and_path_containment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / "model.bin"
            file.write_bytes(b"model bytes")
            artifact = {"size": 11, "sha256": hashlib.sha256(b"model bytes").hexdigest()}
            self.assertTrue(verify(file, artifact))
            file.write_bytes(b"other bytes")
            self.assertFalse(verify(file, artifact))
            with self.assertRaisesRegex(ValueError, "escapes"):
                artifact_path(root, {"directory": "encoder"}, {"path": "../../outside"})

    def test_offline_verification_cannot_download_missing_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock = root / "lock.json"
            lock.write_text(json.dumps({"models": {"test": {"directory": "test", "files": [{"path": "missing.bin", "size": 1, "sha256": "0" * 64}]}}}))
            with patch("experiments.t02.fetch_models.LOCK", lock), patch("experiments.t02.fetch_models.urlopen") as network:
                with self.assertRaisesRegex(ValueError, "Missing or invalid"):
                    fetch(root, verify_only=True)
                network.assert_not_called()


if __name__ == "__main__":
    unittest.main()
