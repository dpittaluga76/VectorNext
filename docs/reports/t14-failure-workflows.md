# T14 — selected workflow examples

Generated offline from retained responses. These examples were selected after the run; they are not the complete evaluation. [Results and limitations](t14-evidence-coverage.md).

The recorded evaluation command was:

```powershell
python -m evals.coverage.run --run 20261014-coverage --phase all
```

Each operation below identifies its API handler and high-level implementation calls. These references are not an instrumented call stack.

---

# VectorNext workflow — answering

T14 frozen comparison: two-cold/two\_earthquakes. Selected example; see the complete T14 report for all 96 outcomes. The runner called Client.request directly; there was no per-question client CLI invocation.

Client elapsed: 10.106 s (including API wait; report rendering and extra document inspection excluded).

## Invocation

Original client arguments were not recorded in this capture.

API handler reference: `POST /v1/ask → Application::ask() → answers::ask_with_options()`.

Code references identify the implementation behind each recorded step; they are not an instrumented call stack. Skipped or unrecorded steps do not list calls.

## Workflow

Question: **Give the USGS recorded magnitudes for the April 25, 2015 Nepal earthquake and December 26, 2004 Sumatra earthquake separately.**

**Outcome: Not enough evidence.**

- **Prepare question — completed.** Preserved the original question. Conversation messages: 0.
  Code: `answers::ask_with_options()`.

- **Filter documents — skipped.** 201 of 201 chunks eligible. No explicit source filter requested.

- **Semantic search — completed.** Compared meanings using a query embedding; retained 30 candidates.
  Code: `RemoteModels::embed()` → `SearchIndex::search_measured()`.

- **Keyword search — completed.** Matched the query terms; retained 30 candidates.
  Code: `FieldIndex::score()`.

- **Combine rankings and remove duplicates — completed.** Combined 47 candidates; suppressed 0 duplicates; returned 20 candidates.
  Code: `SearchIndex::search_measured()`.

- **Rerank passages — completed (0.352 s).** Ranked 20 candidates with cross-encoder/ms-marco-MiniLM-L6-v2.
  Code: `RemoteModels::rerank()`.

- **Assemble source context — completed.** Prepared 2 evidence groups within a limit of 2 primary passages. Groups can combine overlapping or neighboring passages.
  Code: `answers::add_evidence()` → `answers::bundle()`.

Passage omissions: primary limit: 18; duplicate evidence: 2.

Local generation model: google/gemma-4-26B-A4B-it-qat-q4\_0-gguf.

- **Assess answerability — completed (9.478 s).** Not enough evidence.
  Code: `RemoteModels::extract()` → `model_worker.answers.generate(..., ASSESS_PROMPT)`.

- **Extract fields — skipped.** No field-extraction result recorded.

- **Validate answer — completed.** Schema, source-reference and mechanical support checks passed. Semantic correctness is not automatically established.
  Code: `answers::validate_answer()`.

- **Format answer — skipped.** No supported formatted answer returned.

- **Optional prose rewrite — skipped.** No prose rewrite returned; it was not used for retrieval.

## Result

Not enough evidence.

## Selected evidence

**E1 — nepal**, JSON /metadata.

> \{"api":"2.8.1","count":1,"generated":1792026759000,"status":200,"title":"USGS Earthquakes","url":"https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&amp;starttime=2015-04-25&amp;endtime=2015-04-26&amp;minmagnitude=7.5&amp;orderby=time-asc"\}

**E2 — sumatra**, JSON /features/0.

> \{"geometry":\{"coordinates":\[95.982,3.295,30\],"type":"Point"\},"id":"official20041226005853450\_30","properties":\{"alert":null,"cdi":8.6,"code":"20041226005853450\_30","detail":"https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=official20041226005853450\_30&amp;format=geojson","dmin":null,"felt":5,"ga… \[preview shortened\]

Excerpts are short previews of the selected source context; locations describe the source spans, not an independent fact check.

## Timing and reuse

Application elapsed: 10.086 s. Stage times can overlap; do not add them.

Reported cached prompt tokens: 0. Embedding/reranking cache hits were not recorded per request.

---

# VectorNext workflow — answering

T14 frozen comparison: coverage-cold/three\_launches. Selected example; see the complete T14 report for all 96 outcomes. The runner called Client.request directly; there was no per-question client CLI invocation.

Client elapsed: 28.139 s (including API wait; report rendering and extra document inspection excluded).

## Invocation

Original client arguments were not recorded in this capture.

API handler reference: `POST /v1/ask → Application::ask() → answers::ask_with_options()`.

Code references identify the implementation behind each recorded step; they are not an instrumented call stack. Skipped or unrecorded steps do not list calls.

## Workflow

Input: Give the launch years of Mariner 6, Mariner 9 and NEAR Shoemaker separately.

- **Request — failed.** answer rejected: invalid record: quoted source does not contain the exact answer value

## Rejected answer diagnostics

Stopped at: validate\_answer. **The draft failed validation; it is not a supported answer.**

Question: Give the launch years of Mariner 6, Mariner 9 and NEAR Shoemaker separately.

- Unvalidated mariner\_6\_year: 1969 (integer); evidence E1; quoted text: Feb. 25,1969.

- Unvalidated mariner\_9\_year: 1971 (integer); evidence E2; quoted text: May 30, 1971.

- Unvalidated near\_shoemaker\_year: 1996 (integer); evidence E3; quoted text: Feb. 17, 1996.

## Selected evidence

**E3 — near\_shoemaker**, 8 text spans within lines 1–56.

> \# NEAR Shoemaker \#\# What was NEAR Shoemaker? Spacecraft Mass \| 1,775 pounds \(805 kilograms\) Mission Design and Management \| NASA / GSFC / APL Launch Vehicle \| Delta 7925-8 \(no. D232\) Launch Date and Time \| Feb. 17, 1996 / 20:43:27 UT Launch Site \| Cape Canaveral, Fla. / Launch Complex 17B Scientific… \[preview shortened\]

**E1 — mariner\_6**, 12 text spans within lines 3–43.

> \# Mariner 6 Occurred 55 years ago Type Flyby Launch Feb. 25,1969 Target Mars status Successful \#\#\# What was Mariner 6? Mariner 6—along with its twin Mariner 7—was designed to make a close flyby of Mars to look for signs of life and to develop technology for future missions. It returned photos showin… \[preview shortened\]

**E2 — mariner\_9**, 11 text spans within lines 3–60.

> \# Mariner 9 \#\#\# What was Mariner 9? Launch Date and Time \| May 30, 1971 / 22:23:04 UT Launch Site \| Cape Canaveral, Fla. / Launch Complex 36B Scientific Instruments \| 1. Imaging System 2. Ultraviolet Spectrometer 3. Infrared Spectrometer 4. Infrared Radiometer A diagram of the Mariner 1971 series of… \[preview shortened\]

Excerpts are short previews of the selected source context; locations describe the source spans, not an independent fact check.

Inspect selected evidence, field quotes and JSON pointers. This draft failed validation and is not a supported answer.

---

# VectorNext workflow — answering

T14 frozen comparison: five-cold/mission\_photos. Selected example; see the complete T14 report for all 96 outcomes. The runner called Client.request directly; there was no per-question client CLI invocation.

Client elapsed: 37.293 s (including API wait; report rendering and extra document inspection excluded).

## Invocation

Original client arguments were not recorded in this capture.

API handler reference: `POST /v1/ask → Application::ask() → answers::ask_with_options()`.

Code references identify the implementation behind each recorded step; they are not an instrumented call stack. Skipped or unrecorded steps do not list calls.

## Workflow

Input: How many photos had Mariner 9 returned by last contact, including the moon photos?

- **Request — failed.** answer rejected: invalid record: quoted source does not contain the exact answer value

## Rejected answer diagnostics

Stopped at: validate\_answer. **The draft failed validation; it is not a supported answer.**

Question: How many photos had Mariner 9 returned by last contact, including the moon photos?

- Unvalidated photos: 7329 (integer); evidence E1; quoted text: returning 7,329 photos, including at least 80 photos of Phobos and Deimos.

## Selected evidence

**E1 — mariner\_9**, 11 text spans within lines 3–76.

> \# Mariner 9 \#\#\# What was Mariner 9? NASA's Mariner 9 was the first spacecraft to orbit another planet, when it beat the Soviet Mars 2—which had an 11-day head start—to the Red Planet. Mariner 9 mapped 85% of the Martian surface and sent back more than 7,000 pictures, including images of Olympus Mons… \[preview shortened\]

**E2 — mariner\_10**, 12 text spans within lines 3–110.

> \# Mariner 10 \#\# Results During the coast, there were numerous technical problems, including malfunctions in the high-gain antenna and the attitude control system. In January 1974, Mariner 10 successfully returned data \(sans photographs\) on Comet C/1973 E1 Kohoutek, the first time a spacecraft return… \[preview shortened\]

**E3 — mariner\_6**, 9 text spans within lines 3–78.

> \# Mariner 6 \#\#\# Results The 11-foot \(3.35-meter\) tall spacecraft was built around an eight-sided magnesium framework with four rectangular solar panels for 449 watts of power. The heart of the spacecraft was the 26-pound \(11.8-kilogram\) Control Computer and Sequencer \(CC&amp;S\) computer which was design… \[preview shortened\]

Excerpts are short previews of the selected source context; locations describe the source spans, not an independent fact check.

Inspect selected evidence, field quotes and JSON pointers. This draft failed validation and is not a supported answer.
