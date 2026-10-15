# VectorNext workflow — answering

Retained T11 case: ambiguous\_voyager. Rendered offline for T12; no new model call.

## Invocation

Original client arguments were not recorded in this capture.

API handler reference: `POST /v1/ask → Application::ask() → answers::ask_with_options()`.

Code references identify the implementation behind each recorded step; they are not an instrumented call stack. Skipped or unrecorded steps do not list calls.

## Workflow

Question: **On what date did Voyager launch?**

**Outcome: Clarification needed.**

- **Prepare question — completed.** Preserved the original question. Conversation messages: 0.
  Code: `answers::ask_with_options()`.

- **Filter documents — skipped.** 658 of 658 chunks eligible. No explicit source filter requested.

- **Semantic search — completed.** Compared meanings using a query embedding; retained 30 candidates.
  Code: `RemoteModels::embed()` → `SearchIndex::search_measured()`.

- **Keyword search — completed.** Matched the query terms; retained 30 candidates.
  Code: `FieldIndex::score()`.

- **Combine rankings and remove duplicates — completed.** Combined 50 candidates; suppressed 0 duplicates; returned 20 candidates.
  Code: `SearchIndex::search_measured()`.

- **Rerank passages — completed (0.505 s).** Ranked 20 candidates with cross-encoder/ms-marco-MiniLM-L6-v2.
  Code: `RemoteModels::rerank()`.

- **Assemble source context — completed.** Prepared 2 evidence groups within a limit of 5 primary passages. Groups can combine overlapping or neighboring passages.
  Code: `answers::add_evidence()` → `answers::bundle()`.

Passage omissions: primary limit: 15; duplicate evidence: 2.

Local generation model: google/gemma-4-26B-A4B-it-qat-q4\_0-gguf.

- **Assess answerability — completed (14.355 s).** Clarification needed.
  Code: `RemoteModels::extract()` → `model_worker.answers.generate(..., ASSESS_PROMPT)`.

- **Extract fields — skipped.** No field-extraction result recorded.

- **Validate answer — completed.** Schema, source-reference and mechanical support checks passed. Semantic correctness is not automatically established.
  Code: `answers::validate_answer()`.

- **Format answer — skipped.** No supported formatted answer returned.

- **Optional prose rewrite — skipped.** No prose rewrite returned; it was not used for retrieval.

## Result

Clarification needed.

## Selected evidence

**E2 — voyager2**, 12 text spans within lines 3–96.

> \# Voyager 2 \#\# In Depth: Voyager 2 Nation \| United States of America \(USA\) Objective\(s\) \| Jupiter Flyby, Saturn Flyby, Uranus Flyby, Neptune Flyby Spacecraft \| Voyager 2 Spacecraft Mass \| 1,592 pounds \(721.9 kilograms\) Mission Design and Management \| NASA / JPL Launch Vehicle \| Titan IIIE-Centaur \(T… \[preview shortened\]

**E1 — voyager1**, 42 text spans within lines 3–136.

> \# Voyager 1 The most distant human-made object Active Mission Why Discover the Science Goals where Where are They Now? What What's on the Golden Record No spacecraft has gone farther than NASA's Voyager 1. Launched in 1977 to fly by Jupiter and Saturn, Voyager 1 crossed into interstellar space in Au… \[preview shortened\]

Excerpts are short previews of the selected source context; locations describe the source spans, not an independent fact check.

## Timing and reuse

Application elapsed: 15.674 s. Stage times can overlap; do not add them.

Reported cached prompt tokens: 0. Embedding/reranking cache hits were not recorded per request.

---

# VectorNext workflow — answering

Retained T11 case: unknown\_station\_distance. Rendered offline for T12; no new model call.

## Invocation

Original client arguments were not recorded in this capture.

API handler reference: `POST /v1/ask → Application::ask() → answers::ask_with_options()`.

Code references identify the implementation behind each recorded step; they are not an instrumented call stack. Skipped or unrecorded steps do not list calls.

## Workflow

Question: **What is the numeric distance to the nearest station, dmin, in the supplied USGS Tohoku event record?**

**Outcome: Not enough evidence.**

- **Prepare question — completed.** Preserved the original question. Conversation messages: 0.
  Code: `answers::ask_with_options()`.

- **Filter documents — skipped.** 658 of 658 chunks eligible. No explicit source filter requested.

- **Semantic search — completed.** Compared meanings using a query embedding; retained 30 candidates.
  Code: `RemoteModels::embed()` → `SearchIndex::search_measured()`.

- **Keyword search — completed.** Matched the query terms; retained 30 candidates.
  Code: `FieldIndex::score()`.

- **Combine rankings and remove duplicates — completed.** Combined 52 candidates; suppressed 0 duplicates; returned 20 candidates.
  Code: `SearchIndex::search_measured()`.

- **Rerank passages — completed (0.363 s).** Ranked 20 candidates with cross-encoder/ms-marco-MiniLM-L6-v2.
  Code: `RemoteModels::rerank()`.

- **Assemble source context — completed.** Prepared 5 evidence groups within a limit of 5 primary passages. Groups can combine overlapping or neighboring passages.
  Code: `answers::add_evidence()` → `answers::bundle()`.

Passage omissions: duplicate evidence: 9; primary limit: 10.

Local generation model: google/gemma-4-26B-A4B-it-qat-q4\_0-gguf.

- **Assess answerability — completed (17.812 s).** Not enough evidence.
  Code: `RemoteModels::extract()` → `model_worker.answers.generate(..., ASSESS_PROMPT)`.

- **Extract fields — skipped.** No field-extraction result recorded.

- **Validate answer — completed.** Schema, source-reference and mechanical support checks passed. Semantic correctness is not automatically established.
  Code: `answers::validate_answer()`.

- **Format answer — skipped.** No supported formatted answer returned.

- **Optional prose rewrite — skipped.** No prose rewrite returned; it was not used for retrieval.

## Result

Not enough evidence.

## Selected evidence

**E1 — tohoku\_json**, JSON /features/0.

> \{"geometry":\{"coordinates":\[142.373,38.297,29\],"type":"Point"\},"id":"official20110311054624120\_30","properties":\{"alert":null,"cdi":9.1,"code":"20110311054624120\_30","detail":"https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=official20110311054624120\_30&amp;format=geojson","dmin":null,"felt":145… \[preview shortened\]

**E2 — maule\_json**, JSON /metadata.

> \{"api":"2.8.1","count":1,"generated":1792015577000,"status":200,"title":"USGS Earthquakes","url":"https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&amp;starttime=2010-02-27&amp;endtime=2010-02-28&amp;minmagnitude=8.5&amp;orderby=time-asc"\}

**E3 — tohoku\_json**, JSON /metadata.

> \{"api":"2.8.1","count":1,"generated":1792015577000,"status":200,"title":"USGS Earthquakes","url":"https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&amp;starttime=2011-03-11&amp;endtime=2011-03-12&amp;minmagnitude=9&amp;orderby=time-asc"\}

**E4 — maule\_json**, JSON /features/0.

> \{"geometry":\{"coordinates":\[-72.898,-36.122,22.9\],"type":"Point"\},"id":"official20100227063411530\_30","properties":\{"alert":null,"cdi":9.1,"code":"20100227063411530\_30","detail":"https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=official20100227063411530\_30&amp;format=geojson","dmin":null,"felt":… \[preview shortened\]

**E5 — pioneer10**, 14 text spans within lines 1–165.

> \# Pioneer 10 \#\# In Depth: Pioneer 10 The spacecraft crossed Saturn’s orbit in February 1976, recording data that indicated that Jupiter’s enormous magnetic tail, almost 800 million kilometers long, covered the whole distance between the two planets. Still operating nominally, Pioneer 10 crossed the … \[preview shortened\]

Excerpts are short previews of the selected source context; locations describe the source spans, not an independent fact check.

## Timing and reuse

Application elapsed: 18.748 s. Stage times can overlap; do not add them.

Reported cached prompt tokens: 0. Embedding/reranking cache hits were not recorded per request.

---

# VectorNext workflow — answering

Retained T11 case: maule\_json\_magnitude\_depth. Rendered offline for T12; no new model call.

## Invocation

Original client arguments were not recorded in this capture.

API handler reference: `POST /v1/ask → Application::ask() → answers::ask_with_options()`.

Code references identify the implementation behind each recorded step; they are not an instrumented call stack. Skipped or unrecorded steps do not list calls.

## Workflow

- **Request — failed.** invalid record: selected JSON pointer is missing

No completed workflow trace was returned. Parsing, retrieval, model work and validation details are unrecorded; this does not mean they never ran. No supported result is available from this response.

---

# VectorNext workflow — ingestion

Retained T11 Apollo PDF job state. Rendered offline for T12; no new ingestion.

## Invocation

Original client arguments were not recorded in this capture.

API handler reference: `POST /v1/ingest → Application::upload()`.

Code references identify the implementation behind each recorded step; they are not an instrumented call stack. Skipped or unrecorded steps do not list calls.

## Workflow

Document: **apollo11\_pdf**; file: apollo11\_pdf; format: Pdf.

**Outcome: Failed.**

Steps below reflect the durable job state, not a sampled timeline. Per-stage timing and cache reuse were not recorded.

- **Save original — completed.** The original source was accepted and saved.
  Code: `Database::submit_ingestion()`.

- **Read document — failed.** invalid record: partial PDF extraction rejected; inspect diagnostics or explicitly allow partial
  Code: `PdfProcessor::process()`.

- **Create chunks — not reached.** No completed result recorded for this step.

- **Prepare context — not reached.** No completed result recorded for this step.

- **Create embeddings — not reached.** No completed result recorded for this step.

- **Publish document — not reached.** No completed result recorded for this step.

Recorded failure: invalid record: partial PDF extraction rejected; inspect diagnostics or explicitly allow partial

Saved failed attempts: 1.
