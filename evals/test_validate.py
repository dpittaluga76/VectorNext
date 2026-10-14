"""Regression checks for bad gold labels and stale source references."""

from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from evals.validate import InvalidDataset, ROOT, read_json, resolve_pointer, typed_equal, validate_dataset
from evals.build_fixtures import build


class DatasetValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="vectornext-evals-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / "fixtures", self.root / "fixtures")
        self.data = read_json(ROOT / "dataset.json")
        self.path = self.root / "dataset.json"

    def save(self):
        self.path.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")

    def evidence(self, eid):
        return next(e for e in self.data["evidence"] if e["id"] == eid)

    def case(self, cid):
        return next(c for c in self.data["cases"] if c["id"] == cid)

    def reject(self, message):
        self.save()
        with self.assertRaisesRegex(InvalidDataset, message):
            validate_dataset(self.path)

    def test_reviewed_dataset_and_coverage(self):
        self.save()
        self.assertEqual(validate_dataset(self.path), {"documents": 5, "evidence": 22, "questions": 19, "ocr_regions_requiring_visual_review": 1})
        tags = {tag for case in self.data["cases"] for tag in case["tags"]}
        self.assertTrue({"wrapped_paragraph", "cross_page", "table_headers_units", "scanned_page", "nested_json", "year_distractor", "opponent_distractor", "ambiguity", "missing_evidence"} <= tags)
        self.assertEqual({c["split"] for c in self.data["cases"]}, {"dev", "holdout"})
        self.assertEqual({c["expected"]["status"] for c in self.data["cases"]}, {"supported", "ambiguous", "insufficient_evidence"})

    def test_changed_source_is_not_silently_accepted(self):
        path = self.root / "fixtures/fictional_matches.txt"
        path.write_bytes(path.read_bytes().replace(b"3 goals", b"9 goals"))
        self.reject("SHA-256 mismatch")

    def test_character_offsets_are_not_utf8_byte_offsets(self):
        self.evidence("pele_1954_argentina")["locator"]["byte_start"] -= 1
        self.reject("text at byte range")

    def test_line_numbers_must_match_source(self):
        self.evidence("mira_wrapped")["locator"]["line_end"] -= 1
        self.reject("line numbers")

    def test_float_locator_is_rejected_without_crash(self):
        self.evidence("pele_1954_argentina")["locator"]["byte_start"] = 0.0
        self.reject("integer tokens")

    def test_json_zero_is_not_false_or_string_or_float(self):
        entry = self.evidence("json_zero")
        for value in [False, "0", 0.0]:
            with self.subTest(value=value):
                entry["expected"] = value
                self.reject("JSON value or type")

    def test_null_is_not_missing(self):
        self.evidence("json_null")["locator"]["pointer"] = "/matches/1/stats/assists"
        self.reject("Missing JSON field")

    def test_publication_year_does_not_replace_match_year(self):
        self.evidence("json_publication_year")["locator"]["pointer"] = "/matches/0/match/year"
        self.reject("JSON value or type")

    def test_native_pdf_quote_must_be_inside_bbox(self):
        self.evidence("table_h2")["locator"]["bbox"] = [48, 232, 564, 262]
        self.reject("native PDF region text")

    def test_bbox_must_fit_page(self):
        self.evidence("table_h2")["locator"]["bbox"] = [48, 264, 900, 294]
        self.reject("PDF bbox")

    def test_page_must_exist(self):
        self.evidence("c7_end")["locator"]["page"] = 3
        self.reject("PDF page")

    def test_native_text_cannot_be_called_image_only(self):
        self.evidence("table_h2")["locator"]["method"] = "ocr"
        self.reject("image-only")

    def test_scan_has_no_hidden_native_answer(self):
        self.evidence("scan_j2")["locator"]["method"] = "native"
        self.reject("native PDF region text")

    def test_broken_answer_source_is_rejected(self):
        self.case("q_zero")["expected"]["support_sets"][0].append("nonexistent_evidence")
        self.reject("unknown evidence")

    def test_every_field_needs_a_source(self):
        del self.case("q_pele_exact")["expected"]["field_sources"]["goals"]
        self.reject("every answer field")

    def test_ambiguity_requires_distinct_options(self):
        options = self.case("q_ambiguous")["expected"]["alternatives"]
        options[1]["fields"]["year"] = 1954
        self.reject("identical clarification")

    def test_formatting_cannot_silently_change_values(self):
        self.case("q_pele_exact")["presentation"]["expected_text"] = "Match year: 1954, Pelé goals: 8, rival: Argentina"
        self.reject("formatted text")

    def test_duplicate_ids(self):
        self.data["evidence"].append(self.data["evidence"][0])
        self.reject("Duplicate evidence")

    def test_unknown_schema_fields(self):
        self.case("q_zero")["expected"]["confidence"] = 1
        self.reject("Schema")

    def test_fixture_paths_cannot_escape(self):
        self.data["documents"][0]["path"] = "fixtures/../../outside.txt"
        self.reject("invalid fixture path")

    def test_duplicate_json_keys_even_when_hash_matches(self):
        document = next(d for d in self.data["documents"] if d["id"] == "matches_json")
        path = self.root / document["path"]
        raw = b'{"goals": 0, "goals": 1}'
        path.write_bytes(raw)
        document["sha256"] = hashlib.sha256(raw).hexdigest()
        self.reject("duplicate JSON key")

    def test_command_returns_failure_for_invalid_dataset(self):
        self.data["documents"][0]["sha256"] = "0" * 64
        self.save()
        result = subprocess.run([sys.executable, "-m", "evals.validate", "--dataset", str(self.path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("SHA-256 mismatch", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


class JSONSemanticsTests(unittest.TestCase):
    def test_pointer_root_empty_key_and_escapes(self):
        source = {"": 1, "a/b": {"~key": [None, False, 0, "007"]}, "~1": 42}
        self.assertIs(resolve_pointer(source, ""), source)
        self.assertEqual(resolve_pointer(source, "/"), 1)
        self.assertEqual(resolve_pointer(source, "/a~1b/~0key/3"), "007")
        self.assertEqual(resolve_pointer(source, "/~01"), 42)
        self.assertIsNone(resolve_pointer(source, "/a~1b/~0key/0"))

    def test_invalid_pointers(self):
        for pointer in ["no-slash", "/~2", "/~", "/a/-", "/a/01", "/a/-1", "/a/9", "/a/0/child", "/missing"]:
            with self.subTest(pointer=pointer), self.assertRaises(InvalidDataset):
                resolve_pointer({"a": [None]}, pointer)

    def test_type_fidelity_is_recursive(self):
        self.assertFalse(typed_equal({"stats": [0]}, {"stats": [False]}))
        self.assertFalse(typed_equal({"stats": None}, {}))
        self.assertFalse(typed_equal("007", 7))
        self.assertTrue(typed_equal({"b": None, "a": 0}, {"a": 0, "b": None}))

    def test_nonfinite_numbers_are_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            for token in ["NaN", "Infinity", "-Infinity", "1e999"]:
                with self.subTest(token=token):
                    path.write_text('{"value": ' + token + '}')
                    with self.assertRaisesRegex(InvalidDataset, "non-finite"):
                        read_json(path)


class FixtureGenerationTests(unittest.TestCase):
    def test_rebuild_preserves_labels_and_repeats_in_same_toolchain(self):
        with tempfile.TemporaryDirectory(prefix="vectornext-rebuild-") as directory:
            root = Path(directory)
            with redirect_stdout(io.StringIO()):
                build(root)
                first = read_json(root / "dataset.json")
                self.assertEqual(validate_dataset(root / "dataset.json")["questions"], 19)
                build(root)
                self.assertTrue(typed_equal(first, read_json(root / "dataset.json")))
            canonical = read_json(ROOT / "dataset.json")
            # Raster pixels can differ across host Poppler/font versions.
            for dataset in (first, canonical):
                for document in dataset["documents"]:
                    del document["sha256"]
            self.assertTrue(typed_equal(first, canonical))


if __name__ == "__main__":
    unittest.main()
