"""Rebuild synthetic source files and gold labels together; review changes before use."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parent
PAGE = (612, 792)


def write_json(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8"))


def new_pdf(path, title):
    pdf = canvas.Canvas(str(path), pagesize=PAGE, invariant=1, pageCompression=1)
    pdf.setTitle(title)
    pdf.setAuthor("VectorNext synthetic fixtures")
    return pdf


def line(pdf, text, top, x=48, size=11, bold=False):
    pdf.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    pdf.drawString(x, PAGE[1] - top, text)


def page_header(pdf, title, number):
    line(pdf, "VECTORNEXT / SYNTHETIC TEST DATA", 38, size=9)
    line(pdf, title, 72, size=20, bold=True)
    line(pdf, "Fictional equipment. Not operating instructions for real products.", 96, size=10)
    pdf.setStrokeColorRGB(0.25, 0.4, 0.55)
    pdf.line(48, 680, 564, 680)
    line(pdf, f"Synthetic fixture | Page {number}", 764, size=9)


def make_native_pdf(path):
    pdf = new_pdf(path, "Synthetic Harbor pump guide")
    page_header(pdf, "Harbor pump guide", 1)
    line(pdf, "Nominal flow at water temperature 20 C", 150, size=14, bold=True)
    line(pdf, "The table gives nominal flow, not the high-temperature limit.", 176)
    # All coordinates below use points from the top-left, as the gold locators do.
    for top in [198, 230, 262, 294, 326]:
        pdf.line(48, 792 - top, 564, 792 - top)
    for x in [48, 190, 390, 564]:
        pdf.line(x, 792 - 198, x, 792 - 326)
    for label, x in [("Model", 60), ("Flow (L/min)", 202), ("Water (C)", 402)]:
        line(pdf, label, 219, x=x, bold=True)
    for top, model, flow in [(251, "H1", "10"), (283, "H2", "12"), (315, "H3", "15")]:
        for value, x in [(model, 60), (flow, 202), ("20", 402)]:
            line(pdf, value, top, x=x)
    line(pdf, "H2 exception: above 35 C, maximum flow is 8 L/min.", 354)
    line(pdf, "Service conditions", 416, size=14, bold=True)
    line(pdf, "Code C3 requires checking the inlet filter before restarting.", 442)
    line(pdf, "Code C7 uses a timed restart procedure that continues on page 2.", 466)
    line(pdf, "C7 restart procedure", 674, size=14, bold=True)
    line(pdf, "When the Harbor H2 pump reports code C7, stop the motor and", 704)
    pdf.showPage()
    page_header(pdf, "Harbor pump guide - continued", 2)
    line(pdf, "wait 8 minutes before restarting it. This delay applies only to code C7.", 150)
    line(pdf, "Maintenance", 214, size=14, bold=True)
    line(pdf, "Replace the H2 inlet filter every 90 operating days.", 242)
    line(pdf, "The H1 filter interval is 60 operating days.", 266)
    pdf.save()


def make_scanned_pdf(path):
    # A clean raster scan is the first OCR baseline; no hidden text layer is added.
    with tempfile.TemporaryDirectory(prefix="vectornext-scan-") as directory:
        temp = Path(directory)
        source = new_pdf(temp / "source.pdf", "Synthetic scan master")
        page_header(source, "Connector inspection note", 1)
        line(source, "Inspection record: SCAN-004", 154, size=14, bold=True)
        line(source, "Connector J2 on cable B4 requires a tightening torque of 6 N m.", 198)
        line(source, "Connector J3 on cable B4 requires a tightening torque of 9 N m.", 230)
        line(source, "Recorded by the fictional Harbor test workshop.", 290)
        source.save()
        subprocess.run(["pdftoppm", "-r", "120", "-singlefile", "-png", str(temp / "source.pdf"), str(temp / "scan")], check=True, capture_output=True)
        result = new_pdf(path, "Synthetic image-only inspection note")
        result.drawImage(ImageReader(str(temp / "scan.png")), 0, 0, width=612, height=792)
        result.save()


def build(output):
    fixtures = output / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    text = (
        "SYNTHETIC TEST DATA - all matches below are invented.\n"
        "The Pelé/1954 example is hypothetical, not verified sports history.\n\n"
        "Fictional match F-001\n"
        "Pelé scored 3 goals against Argentina in 1954.\n\n"
        "Fictional match F-002\n"
        "Pelé scored 1 goal against Argentina in 1955.\n\n"
        "Fictional match F-003\n"
        "Pelé scored 2 goals against Uruguay in 1954.\n\n"
        "Fictional match F-004\n"
        "In the invented 1960 match against Chile, Mira Costa scored\n"
        "4 goals. The match was played at Harbor Field.\n\n"
        "These four records are the complete contents of this fictional match log.\n"
    )
    (fixtures / "fictional_matches.txt").write_bytes(text.encode("utf-8"))
    nested = {
        "synthetic": True,
        "description": "Invented records; not historical match results.",
        "publication": {"year": 2026, "edition": "01"},
        "matches": [
            {"id": "m-001", "player": {"id": "007", "name": "Iris Vega"}, "match": {"year": 2021, "opponent": "Lakeside"}, "stats": {"goals": 0, "assists": None}, "notes": "Goals are recorded as zero; assists were not recorded."},
            {"id": "m-002", "player": {"id": "007", "name": "Iris Vega"}, "match": {"year": 2022, "opponent": "Lakeside"}, "stats": {"goals": 2}},
            {"id": "m-003", "player": {"id": "007", "name": "Iris Vega"}, "match": {"year": 2021, "opponent": "Hilltown"}, "stats": {"goals": 5}}
        ],
        "labels": {"home/away": "away", "review~state": "checked"}
    }
    write_json(fixtures / "nested_matches.json", nested)
    write_json(fixtures / "array_matches.json", [
        {"synthetic": True, "id": "a-001", "player": "Sol Marin", "opponent": "Riverside", "year": 2023, "goals": 4},
        {"synthetic": True, "id": "a-002", "player": "Sol Marin", "opponent": "Riverside", "year": 2024, "goals": 1}
    ])
    make_native_pdf(fixtures / "equipment_guide.pdf")
    make_scanned_pdf(fixtures / "scanned_note.pdf")

    documents = []
    for doc_id, filename, media_type in [
        ("matches_txt", "fictional_matches.txt", "text/plain"),
        ("matches_json", "nested_matches.json", "application/json"),
        ("array_json", "array_matches.json", "application/json"),
        ("guide_pdf", "equipment_guide.pdf", "application/pdf"),
        ("scan_pdf", "scanned_note.pdf", "application/pdf")
    ]:
        documents.append({"id": doc_id, "path": "fixtures/" + filename, "media_type": media_type, "sha256": hashlib.sha256((fixtures / filename).read_bytes()).hexdigest()})

    evidence = []

    def add(eid, doc, locator, expected):
        evidence.append({"id": eid, "document_id": doc, "locator": locator, "expected": expected})

    for eid, quote in [
        ("pele_1954_argentina", "Pelé scored 3 goals against Argentina in 1954."),
        ("pele_1955_argentina", "Pelé scored 1 goal against Argentina in 1955."),
        ("pele_1954_uruguay", "Pelé scored 2 goals against Uruguay in 1954."),
        ("mira_wrapped", "In the invented 1960 match against Chile, Mira Costa scored\n4 goals. The match was played at Harbor Field.")
    ]:
        raw = text.encode("utf-8")
        start = raw.index(quote.encode("utf-8"))
        end = start + len(quote.encode("utf-8"))
        add(eid, "matches_txt", {"kind": "text", "byte_start": start, "byte_end": end, "line_start": raw[:start].count(b"\n") + 1, "line_end": raw[:end - 1].count(b"\n") + 1}, quote)

    for index, record in enumerate(nested["matches"]):
        add(f"json_match_{index + 1}", "matches_json", {"kind": "json", "pointer": f"/matches/{index}"}, record)
    for eid, pointer, value in [
        ("json_zero", "/matches/0/stats/goals", 0),
        ("json_null", "/matches/0/stats/assists", None),
        ("json_player_id", "/matches/0/player/id", "007"),
        ("json_publication_year", "/publication/year", 2026),
        ("json_slash_key", "/labels/home~1away", "away"),
        ("json_tilde_key", "/labels/review~0state", "checked")
    ]:
        add(eid, "matches_json", {"kind": "json", "pointer": pointer}, value)
    add("array_record", "array_json", {"kind": "json", "pointer": "/0"}, {"synthetic": True, "id": "a-001", "player": "Sol Marin", "opponent": "Riverside", "year": 2023, "goals": 4})
    for eid, page, bbox, quote in [
        ("table_heading", 1, [48, 134, 550, 156], "Nominal flow at water temperature 20 C"),
        ("table_columns", 1, [48, 200, 564, 230], "Model Flow (L/min) Water (C)"),
        ("table_h2", 1, [48, 264, 564, 294], "H2 12 20"),
        ("table_exception", 1, [48, 338, 564, 362], "H2 exception: above 35 C, maximum flow is 8 L/min."),
        ("c7_start", 1, [48, 688, 564, 714], "When the Harbor H2 pump reports code C7, stop the motor and"),
        ("c7_end", 2, [48, 134, 564, 160], "wait 8 minutes before restarting it. This delay applies only to code C7."),
        ("filter_h2", 2, [48, 226, 564, 250], "Replace the H2 inlet filter every 90 operating days.")
    ]:
        add(eid, "guide_pdf", {"kind": "pdf", "page": page, "bbox": bbox, "method": "native"}, quote)
    add("scan_j2", "scan_pdf", {"kind": "pdf", "page": 1, "bbox": [48, 180, 564, 210], "method": "ocr"}, "Connector J2 on cable B4 requires a tightening torque of 6 N m.")

    cases = []

    def supported(cid, question, tags, fields, sources, split="dev", **extra):
        field_sources = sources if isinstance(sources, dict) else {key: sources for key in fields}
        support = list(dict.fromkeys(e for refs in field_sources.values() for e in refs))
        cases.append({"id": cid, "split": split, "question": question, "tags": tags, "expected": {"status": "supported", "fields": fields, "field_sources": field_sources, "support_sets": [support]}, **extra})

    supported("q_pele_exact", "In the fictional log, how many goals did Pelé score against Argentina in 1954?", ["exact_constraints", "formatting"], {"year": 1954, "goals": 3, "opponent": "Argentina"}, ["pele_1954_argentina"], presentation={"template": "Match year: {year}, Pelé goals: {goals}, rival: {opponent}", "expected_text": "Match year: 1954, Pelé goals: 3, rival: Argentina"})
    supported("q_pele_year", "In the fictional log, how many goals did Pelé score against Argentina in 1955?", ["year_distractor"], {"goals": 1}, ["pele_1955_argentina"], split="holdout")
    supported("q_pele_opponent", "In the fictional log, how many goals did Pelé score against Uruguay in 1954?", ["opponent_distractor"], {"goals": 2}, ["pele_1954_uruguay"], split="holdout")
    supported("q_wrapped", "How many goals did Mira Costa score against Chile in the invented 1960 match?", ["wrapped_paragraph"], {"goals": 4}, ["mira_wrapped"])
    supported("q_followup", "Then I wondered, how many goals did Pelé score in that match?", ["conversational_reference"], {"year": 1954, "goals": 3, "opponent": "Argentina"}, ["pele_1954_argentina"], history=[{"role": "user", "content": "Use the fictional match log. I am asking about Pelé against Argentina in 1954."}])
    cases.append({"id": "q_ambiguous", "split": "dev", "question": "In the fictional log, how many goals did Pelé score against Argentina in the match?", "tags": ["ambiguity"], "expected": {"status": "ambiguous", "clarification_fields": ["year"], "alternatives": [{"fields": {"year": 1954, "goals": 3}, "support_set": ["pele_1954_argentina"]}, {"fields": {"year": 1955, "goals": 1}, "support_set": ["pele_1955_argentina"]}]}})
    for cid, question, reason, split in [
        ("q_missing_match", "In the fictional log, how many goals did Pelé score against Brazil in 1954?", "No matching opponent and year occur in the source corpus.", "dev"),
        ("q_missing_json_field", "How many assists did Iris Vega make against Lakeside in 2022?", "The matching record omits assists. Missing does not mean zero.", "holdout"),
        ("q_null_unknown", "How many assists did Iris Vega make against Lakeside in 2021?", "The assists value is null and the note says it was not recorded. No numeric answer is supported.", "dev")
    ]:
        cases.append({"id": cid, "split": split, "question": question, "tags": ["missing_evidence"], "expected": {"status": "insufficient_evidence", "reason": reason}})
    supported("q_zero", "How many goals did Iris Vega score against Lakeside in 2021?", ["nested_json", "zero", "publication_year_distractor"], {"goals": 0}, ["json_match_1", "json_zero"])
    supported("q_raw_null", "What is the raw JSON assists value in record m-001?", ["null_value"], {"assists": None}, ["json_match_1", "json_null"])
    supported("q_player_id", "What is Iris Vega's player ID in record m-001? Preserve its JSON type.", ["string_identity"], {"player_id": "007"}, ["json_match_1", "json_player_id"])
    supported("q_nested_opponent", "How many goals did Iris Vega score against Hilltown in 2021?", ["nested_json", "opponent_distractor"], {"goals": 5}, ["json_match_3"], split="holdout")
    supported("q_array", "How many goals did Sol Marin score against Riverside in 2023?", ["root_array"], {"goals": 4}, ["array_record"])
    supported("q_table", "What is the nominal flow of Harbor H2 at water temperature 20 C?", ["table_headers_units"], {"flow": 12, "unit": "L/min", "water_temperature_c": 20}, ["table_heading", "table_columns", "table_h2"])
    supported("q_table_exception", "What is the maximum flow of Harbor H2 above 35 C?", ["table_exception"], {"flow": 8, "unit": "L/min"}, ["table_exception"], split="holdout")
    supported("q_cross_page", "How long must I wait before restarting Harbor H2 after code C7?", ["cross_page"], {"wait": 8, "unit": "minutes"}, ["c7_start", "c7_end"])
    supported("q_native_pdf", "How often should the Harbor H2 inlet filter be replaced?", ["native_pdf"], {"interval": 90, "unit": "operating days"}, ["filter_h2"], split="holdout")
    supported("q_scan", "What tightening torque does connector J2 on cable B4 require?", ["scanned_page", "ocr_digit"], {"torque": 6, "unit": "N m"}, ["scan_j2"])
    write_json(output / "dataset.json", {"schema_version": "1.0", "provenance": {"synthetic": True, "description": "All source content and gold labels were authored for VectorNext. Matches (including Pelé/1954) are hypothetical, never verified sports history. Equipment and workshop are fictional. See README.md for source and review limitations."}, "documents": documents, "evidence": evidence, "cases": cases})
    print(f"Built {len(documents)} documents, {len(evidence)} evidence references, {len(cases)} questions in {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT)
    build(parser.parse_args().output.resolve())
