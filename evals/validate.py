"""Validate gold data integrity and source locations without running a model."""

import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import string
import sys

from jsonschema import Draft202012Validator
import pdfplumber


ROOT = Path(__file__).resolve().parent


class InvalidDataset(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise InvalidDataset(message)


def read_json(path):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"{path}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    def bad_constant(value):
        raise InvalidDataset(f"{path}: non-finite JSON number {value}")

    # Also reject valid-looking exponent literals that overflow Python's float.
    def finite_float(value):
        import math
        parsed = float(value)
        require(math.isfinite(parsed), f"{path}: non-finite JSON number {value}")
        return parsed

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object, parse_constant=bad_constant, parse_float=finite_float)


def typed_equal(left, right):
    """Do not let Python equate false with zero or discard numeric representation."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(typed_equal(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(typed_equal(a, b) for a, b in zip(left, right))
    return left == right


def resolve_pointer(value, pointer):
    require(pointer == "" or pointer.startswith("/"), f"Invalid JSON pointer {pointer!r}")
    if pointer == "":
        return value
    for encoded in pointer[1:].split("/"):
        require(re.search(r"~(?![01])", encoded) is None, f"Invalid JSON pointer escape in {pointer!r}")
        token = encoded.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict):
            require(token in value, f"Missing JSON field in pointer {pointer!r}")
            value = value[token]
        elif isinstance(value, list):
            require(re.fullmatch(r"0|[1-9][0-9]*", token) is not None, f"Invalid JSON array index in {pointer!r}")
            index = int(token)
            require(index < len(value), f"JSON array index out of range in {pointer!r}")
            value = value[index]
        else:
            raise InvalidDataset(f"JSON pointer traverses a scalar: {pointer!r}")
    return value


def by_id(items, label):
    result = {}
    for item in items:
        require(item["id"] not in result, f"Duplicate {label} id: {item['id']}")
        result[item["id"]] = item
    return result


def normalized(text):
    return " ".join(text.split())


def validate_dataset(path=ROOT / "dataset.json", schema_path=ROOT / "dataset.schema.json"):
    path = Path(path).resolve()
    root = path.parent
    data = read_json(path)
    schema = read_json(Path(schema_path))
    Draft202012Validator.check_schema(schema)
    for error in Draft202012Validator(schema).iter_errors(data):
        where = "/".join(str(part) for part in error.absolute_path)
        raise InvalidDataset(f"Schema at /{where}: {error.message}")
    documents = by_id(data["documents"], "document")
    evidence = by_id(data["evidence"], "evidence")
    cases = by_id(data["cases"], "case")
    sources = {}
    source_paths = set()
    manual_ocr = 0

    with ExitStack() as stack:
        for doc_id, doc in documents.items():
            relative = PurePosixPath(doc["path"])
            require("\\" not in doc["path"] and ":" not in doc["path"] and not relative.is_absolute() and ".." not in relative.parts, f"{doc_id}: invalid fixture path")
            source = (root / relative).resolve()
            require(source.is_relative_to((root / "fixtures").resolve()), f"{doc_id}: fixture path escapes fixtures directory")
            require(source not in source_paths, f"{doc_id}: duplicate source path")
            source_paths.add(source)
            raw = source.read_bytes()
            require(hashlib.sha256(raw).hexdigest() == doc["sha256"], f"{doc_id}: source SHA-256 mismatch")
            media = doc["media_type"]
            suffix = {"text/plain": ".txt", "application/json": ".json", "application/pdf": ".pdf"}[media]
            require(source.suffix == suffix, f"{doc_id}: media type and file extension disagree")
            if media == "text/plain":
                raw.decode("utf-8")
                sources[doc_id] = raw
            elif media == "application/json":
                sources[doc_id] = read_json(source)
            else:
                sources[doc_id] = stack.enter_context(pdfplumber.open(source))

        for eid, entry in evidence.items():
            doc_id = entry["document_id"]
            require(doc_id in documents, f"{eid}: unknown document {doc_id}")
            loc, expected = entry["locator"], entry["expected"]
            kind = loc["kind"]
            integer_keys = {"text": ["byte_start", "byte_end", "line_start", "line_end"], "pdf": ["page"], "json": []}[kind]
            require(all(type(loc[key]) is int for key in integer_keys), f"{eid}: source indices must use integer tokens")
            require(documents[doc_id]["media_type"] == {"text": "text/plain", "json": "application/json", "pdf": "application/pdf"}[kind], f"{eid}: locator kind does not match document")
            source = sources[doc_id]
            if kind == "text":
                start, end = loc["byte_start"], loc["byte_end"]
                require(0 <= start < end <= len(source), f"{eid}: invalid UTF-8 byte range")
                require(source[start:end].decode("utf-8") == expected, f"{eid}: text at byte range differs from expected")
                require(source[:start].count(b"\n") + 1 == loc["line_start"] and source[:end - 1].count(b"\n") + 1 == loc["line_end"], f"{eid}: line numbers disagree with byte range")
            elif kind == "json":
                require(typed_equal(resolve_pointer(source, loc["pointer"]), expected), f"{eid}: JSON value or type differs from expected")
            else:
                require(isinstance(expected, str) and expected.strip(), f"{eid}: PDF evidence requires nonempty text")
                require(loc["page"] <= len(source.pages), f"{eid}: PDF page does not exist")
                page = source.pages[loc["page"] - 1]
                require(page.rotation == 0 and tuple(page.mediabox[:2]) == (0, 0), f"{eid}: v1 fixtures require unrotated pages with zero MediaBox origin")
                x0, top, x1, bottom = loc["bbox"]
                require(0 <= x0 < x1 <= page.width and 0 <= top < bottom <= page.height, f"{eid}: PDF bbox outside page or empty")
                region = page.crop(tuple(loc["bbox"]))
                if loc["method"] == "native":
                    require(normalized(expected) == normalized(region.extract_text() or ""), f"{eid}: native PDF region text differs from expected")
                else:
                    require(not page.chars and region.images, f"{eid}: OCR baseline must be image-only with an image in the evidence region")
                    manual_ocr += 1

    def check_refs(refs, label):
        for ref in refs:
            require(ref in evidence, f"{label}: unknown evidence {ref}")

    for cid, case in cases.items():
        expected = case["expected"]
        status = expected["status"]
        if status == "supported":
            fields, field_sources = expected["fields"], expected["field_sources"]
            require(fields.keys() == field_sources.keys(), f"{cid}: every answer field must have source references")
            all_refs = set()
            for support in expected["support_sets"]:
                check_refs(support, cid)
                all_refs.update(support)
            for field, refs in field_sources.items():
                check_refs(refs, f"{cid}/{field}")
                require(set(refs) <= all_refs, f"{cid}/{field}: field sources absent from support sets")
            require(all_refs == {ref for refs in field_sources.values() for ref in refs}, f"{cid}: support sets contain unused evidence")
        elif status == "ambiguous":
            options = expected["alternatives"]
            signatures = []
            for option in options:
                check_refs(option["support_set"], cid)
                require(all(k in option["fields"] for k in expected["clarification_fields"]), f"{cid}: clarification field missing from an alternative")
                signature = json.dumps({k: option["fields"][k] for k in expected["clarification_fields"]}, sort_keys=True)
                require(signature not in signatures, f"{cid}: alternatives have identical clarification values")
                signatures.append(signature)
        if "presentation" in case:
            require(status == "supported", f"{cid}: a formatted answer requires supported fields")
            template = case["presentation"]["template"]
            # Only simple named placeholders: do not evaluate attributes or indexes.
            for _, name, spec, conversion in string.Formatter().parse(template):
                if name is not None:
                    require(name in expected["fields"] and not spec and not conversion, f"{cid}: invalid presentation placeholder")
            require(template.format_map(expected["fields"]) == case["presentation"]["expected_text"], f"{cid}: formatted text differs from answer fields")

    return {"documents": len(documents), "evidence": len(evidence), "questions": len(cases), "ocr_regions_requiring_visual_review": manual_ocr}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "dataset.json")
    args = parser.parse_args()
    try:
        result = validate_dataset(args.dataset)
    except (ValueError, OSError, KeyError, IndexError) as error:
        print(f"INVALID: {error}", file=sys.stderr)
        return 1
    print("VALID: " + json.dumps(result, sort_keys=True))
    print("Integrity checks only. OCR transcription needs visual review; no retrieval or answer quality has been measured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
