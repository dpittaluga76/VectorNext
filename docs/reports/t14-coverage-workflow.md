# T14 — selected workflow examples

Generated offline from retained responses. These examples were selected after the run; they are not the complete evaluation. [Results and limitations](t14-evidence-coverage.md).

The recorded evaluation command was:

```powershell
python -m evals.coverage.run --run 20261014-coverage --phase all
```

Each operation below identifies its API handler and high-level implementation calls. These references are not an instrumented call stack.

---

# VectorNext workflow — answering

T14 frozen comparison: coverage-cold/two\_earthquakes. Selected example; see the complete T14 report for all 96 outcomes. The runner called Client.request directly; there was no per-question client CLI invocation.

Client elapsed: 31.747 s (including API wait; report rendering and extra document inspection excluded).

## Invocation

Original client arguments were not recorded in this capture.

API handler reference: `POST /v1/ask → Application::ask() → answers::ask_with_options()`.

Code references identify the implementation behind each recorded step; they are not an instrumented call stack. Skipped or unrecorded steps do not list calls.

## Workflow

Question: **Give the USGS recorded magnitudes for the April 25, 2015 Nepal earthquake and December 26, 2004 Sumatra earthquake separately.**

**Outcome: Supported answer.**

- **Prepare question — completed.** Preserved the original question. Conversation messages: 0.
  Code: `answers::ask_with_options()`.

- **Filter documents — skipped.** 201 of 201 chunks eligible. No explicit source filter requested.

- **Semantic search — completed.** Compared meanings using a query embedding; retained 30 candidates.
  Code: `RemoteModels::embed()` → `SearchIndex::search_measured()`.

- **Keyword search — completed.** Matched the query terms; retained 30 candidates.
  Code: `FieldIndex::score()`.

- **Combine rankings and remove duplicates — completed.** Combined 47 candidates; suppressed 0 duplicates; returned 20 candidates.
  Code: `SearchIndex::search_measured()`.

- **Rerank passages — completed (0.303 s).** Ranked 20 candidates with cross-encoder/ms-marco-MiniLM-L6-v2.
  Code: `RemoteModels::rerank()`.

- **Select evidence for requested fields — completed (0.641 s).** Ranked candidates for 2 fields; planned 4 primary passages and admitted 3. Automatic neighbor expansion disabled; original source labels retained. Coverage is a heuristic, not a correctness guarantee.
  Code: `answers::coverage::select()` → `RemoteModels::rerank()`.

- **Assemble source context — completed.** Prepared 3 evidence groups within a limit of 5 primary passages. Groups can combine overlapping or neighboring passages.
  Code: `answers::add_evidence()` → `answers::bundle()`.

Passage omissions: duplicate evidence: 1; outside field coverage selection: 16.

Local generation model: google/gemma-4-26B-A4B-it-qat-q4\_0-gguf.

- **Assess answerability — completed (14.651 s).** Supported answer.
  Code: `RemoteModels::extract()` → `model_worker.answers.generate(..., ASSESS_PROMPT)`.

- **Extract fields — completed (15.884 s).** Read exact fields from the selected evidence.
  Code: `model_worker.answers.generate(..., PROMPT)`.

- **Resolve JSON source values — completed.** JSON values were read directly from selected source pointers, preserving numeric precision, zero and null.
  Code: `answers::resolve_json_values()`.

- **Validate answer — completed.** Schema, source-reference and mechanical support checks passed. Semantic correctness is not automatically established.
  Code: `answers::validate_answer()`.

- **Format answer — completed.** Rendered the validated fields.
  Code: `answers::render()`.

- **Optional prose rewrite — skipped.** No prose rewrite returned; it was not used for retrieval.

## Result

**nepal\_magnitude: 7.8, sumatra\_magnitude: 9.1**

- nepal\_magnitude: **7.8** (number); source E3; record pointer /properties/mag.

- sumatra\_magnitude: **9.1** (number); source E2; record pointer /properties/mag.

## Selected evidence

**E1 — nepal**, JSON /metadata.

> \{"api":"2.8.1","count":1,"generated":1792026759000,"status":200,"title":"USGS Earthquakes","url":"https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&amp;starttime=2015-04-25&amp;endtime=2015-04-26&amp;minmagnitude=7.5&amp;orderby=time-asc"\}

**E2 — sumatra**, JSON /features/0.

> \{"geometry":\{"coordinates":\[95.982,3.295,30\],"type":"Point"\},"id":"official20041226005853450\_30","properties":\{"alert":null,"cdi":8.6,"code":"20041226005853450\_30","detail":"https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=official20041226005853450\_30&amp;format=geojson","dmin":null,"felt":5,"ga… \[preview shortened\]

**E3 — nepal**, JSON /features/0.

> \{"geometry":\{"coordinates":\[84.7314,28.2305,8.22\],"type":"Point"\},"id":"us20002926","properties":\{"alert":"red","cdi":8.2,"code":"20002926","detail":"https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=us20002926&amp;format=geojson","dmin":1.857,"felt":1134,"gap":12,"ids":",us20002926,gcmt201504250… \[preview shortened\]

Excerpts are short previews of the selected source context; locations describe the source spans, not an independent fact check.

## Timing and reuse

Application elapsed: 31.813 s. Stage times can overlap; do not add them.

Reported cached prompt tokens: 0. Embedding/reranking cache hits were not recorded per request.
