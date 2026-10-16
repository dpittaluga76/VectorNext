import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from .encoders import mean_pool_normalize
from .fetch_models import artifact_path, download_ranges, fetch, verify


class AssetTests(unittest.TestCase):
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
            with patch("model_assets.fetch_models.urlopen", side_effect=response_for):
                download_ranges("https://example.invalid/model", partial, len(content), workers=2, chunk_size=4)
            self.assertEqual(partial.read_bytes(), content)

    def test_range_download_rejects_ignored_range(self):
        response = io.BytesIO(b"not the requested bytes")
        response.status = 200
        response.headers = {}
        with tempfile.TemporaryDirectory() as directory:
            partial = Path(directory) / "model.part"
            partial.write_bytes(b"prefix")
            with patch("model_assets.fetch_models.urlopen", return_value=response):
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
            with patch("model_assets.fetch_models.LOCK", lock), patch("model_assets.fetch_models.urlopen") as network:
                with self.assertRaisesRegex(ValueError, "Missing or invalid"):
                    fetch(root, verify_only=True)
                network.assert_not_called()
