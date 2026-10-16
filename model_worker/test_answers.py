import copy
import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import jsonschema
from .answers import schema, messages
from .server import Worker


class AnswerModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        with patch.dict(os.environ, {"VECTORNEXT_CACHE": cls.temp.name}): cls.worker = Worker()

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def value(self):
        return {"question": "What is the value?", "history": [], "fields": {
            "goals": {"kind": "integer", "nullable": True, "description": "", "pointer": "/goals"}},
            "evidence": [{"id": "E1", "key": {"document_id": "doc", "revision": "r1"}, "text": '{"goals":0}', "record": {"goals": 0}}]}

    def test_real_reranking_and_exact_cache(self):
        w = self.worker
        request = {"op": "rerank", "input": {"query": "How many goals did Pele score?", "passages": ["Pele scored 3 goals.", "Tighten the connector to 6 N m."]}}
        r = w.handle(request)
        self.assertGreater(r["scores"][0], r["scores"][1])
        self.assertEqual(len(r["pair_tokens"]), 2)
        calls = w.calls["rerank"]
        self.assertEqual(w.handle(request), r)
        self.assertEqual(w.calls["rerank"], calls)
        request["input"]["passages"] = ["word " * 600]
        with self.assertRaisesRegex(ValueError, "512"): w.handle(request)

    def test_status_fields_zero_null_and_missing(self):
        s = schema(self.value()["fields"])
        for value in (0, None):
            jsonschema.validate({"status": "supported", "fields": {"goals": {"value": value, "evidence_id": "E1", "quote": "", "pointer": "/goals"}}}, s)
        for status in ("ambiguous", "insufficient_evidence"):
            jsonschema.validate({"status": status, "fields": {}}, s)
            with self.assertRaises(jsonschema.ValidationError): jsonschema.validate({"status": status, "fields": {"goals": None}}, s)
        with self.assertRaises(jsonschema.ValidationError): jsonschema.validate({"status": "supported", "fields": {}}, s)

    def test_original_question_and_exact_json_text_survive_prompt(self):
        value = self.value()
        value["question"] = "What did he score in 1954, NOT 1955?"
        value["history"] = [{"role": "user", "text": "Pele against Argentina"}]
        value["evidence"][0]["text"] = '{"precise":9007199254740993.00000000000001}'
        user = json.loads(messages(value)[1]["content"])
        self.assertEqual(user["ORIGINAL QUESTION"], value["question"])
        self.assertEqual(user["EVIDENCE"][0]["text"], value["evidence"][0]["text"])

    def test_priority_budget_schema_and_no_answer_cache(self):
        w = self.worker; value = self.value()
        answer = {"status": "insufficient_evidence", "fields": {}}
        def http(path, payload, priority):
            self.assertEqual(priority, "interactive")
            if path == "/apply-template": return {"prompt": "chat"}
            if path == "/tokenize": return {"tokens": [1] * 100}
            if payload["max_tokens"] == 192:
                return {"choices": [{"finish_reason": "stop", "message": {"content": '{"status":"supported","reason":"One record matches."}'}}]}
            self.assertEqual(payload["max_tokens"], 768)
            return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(answer)}}]}
        with patch.object(w, "http", side_effect=http) as mock:
            for _ in range(2): self.assertEqual(w.handle({"op": "answer", "input": value, "lease":{"model":"gemma","token":"synthetic-test-lease"}})["answer"], answer)
            self.assertEqual(mock.call_count, 12)
            answer["fields"] = {"goals": None}
            with self.assertRaises(jsonschema.ValidationError): w.handle({"op": "answer", "input": value, "lease":{"model":"gemma","token":"synthetic-test-lease"}})
        with patch.object(w, "http", side_effect=[{"prompt": "chat"}, {"tokens": [1] * 3329}]):
            with self.assertRaisesRegex(ValueError, "budget"): w.handle({"op": "answer", "input": value, "lease":{"model":"gemma","token":"synthetic-test-lease"}})

    def test_wire_schema_keeps_status_before_dependent_fields(self):
        output_schema = schema(self.value()["fields"], self.value()["evidence"])
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value = b'{}'
        with patch("urllib.request.build_opener", return_value=opener):
            self.worker.http("/v1/chat/completions", {"schema": output_schema}, priority="interactive")
        req = opener.open.call_args.args[0]
        body = json.loads(req.data)
        self.assertEqual(list(body["schema"]["oneOf"][0]["properties"]), ["status", "fields"])
        self.assertEqual(list(body["schema"]["oneOf"][0]["properties"]["fields"]["properties"]["goals"]["properties"])[0], "evidence_id")
        self.assertEqual(req.get_header("X-vectornext-priority"), "interactive")

    def test_ambiguous_assessment_skips_extraction(self):
        with patch.object(self.worker, "http", side_effect=[{"prompt": "x"}, {"tokens": [1]},
                {"choices": [{"finish_reason": "stop", "message": {"content": '{"status":"ambiguous","reason":"Two events fit."}'}}]}]) as http:
            result = self.worker.handle({"op": "answer", "input": self.value(), "lease":{"model":"gemma","token":"synthetic-test-lease"}})
            self.assertEqual(result["answer"], {"status": "ambiguous", "fields": {}})
            self.assertEqual(http.call_count, 3)

    def test_evidence_dependent_schema_requires_json_pointers(self):
        s = schema(self.value()["fields"], self.value()["evidence"])
        answer = {"status": "supported", "fields": {"goals": {"value": None, "evidence_id": "E1", "quote": "", "pointer": "/goals"}}}
        jsonschema.validate(answer, s)
        answer["fields"]["goals"]["pointer"] = None
        with self.assertRaises(jsonschema.ValidationError): jsonschema.validate(answer, s)

    def test_json_selection_requires_placeholder_instead_of_model_transcription(self):
        value = self.value(); value["fields"]["goals"]["nullable"] = False
        # Candidate schema is not the public answer contract; Rust reads the exact value.
        jsonschema.validate({"status": "supported", "fields": {"goals": {"value": None, "evidence_id": "E1", "quote": "", "pointer": "/goals"}}},
                            schema(value["fields"], value["evidence"]))
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate({"status": "supported", "fields": {"goals": {"value": 0, "evidence_id": "E1", "quote": "", "pointer": "/goals"}}},
                                schema(value["fields"], value["evidence"]))

    def test_rewrite_preserves_exact_decimal_literal_and_rejects_rounding(self):
        exact = "9007199254740993.00000000000001"
        for returned, expected in ((exact, "draft"), ("9007199254740992.0", "rejected_missing_field_literals")):
            response = {"question": "What is the reading?", "answer": "Reading: " + returned}
            with patch("model_worker.answers.generate", return_value=(response, {})) as generate:
                result = self.worker.handle({"op": "rewrite", "lease":{"model":"gemma","token":"synthetic-test-lease"}, "input": {"question": "What is the reading?", "field_literals": {"reading": exact}}})
                self.assertEqual(result["status"], expected)
                prompt = json.loads(generate.call_args.args[1][1]["content"])
                self.assertEqual(prompt["validated_field_literals"]["reading"], exact)


if __name__ == "__main__": unittest.main()
