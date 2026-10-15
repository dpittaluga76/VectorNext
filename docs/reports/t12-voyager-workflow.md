# VectorNext workflow — ingestion

Captured from a local API operation.

Client elapsed: 1.537 s (including API wait; report rendering and extra document inspection excluded).

## Invocation

Operation arguments recovered from the saved run record (report/capture switches omitted). Equivalent Python invocation, with POSIX shell quoting; outer Docker commands and environment are not captured:

```sh
python -m deployment.client ingest /app/evals/independent/fixtures/voyager1.txt --document voyager-workflow --job voyager-workflow-v1 --wait
```

API handler reference: `POST /v1/ingest → Application::upload()`.

Code references identify the implementation behind each recorded step; they are not an instrumented call stack. Skipped or unrecorded steps do not list calls.

## Workflow

Document: **voyager-workflow**; file: /app/evals/independent/fixtures/voyager1.txt; format: Txt.

**Outcome: Stored and searchable.**

Steps below reflect the durable job state, not a sampled timeline. Per-stage timing and cache reuse were not recorded.

- **Save original — completed.** The original source was accepted and saved.
  Code: `Database::submit_ingestion()`.

- **Read document — completed.** Read UTF-8 text and its structure.
  Code: `ingestion::prepare::parse()`.

- **Create chunks — completed.** Prepared 86 blocks and 25 searchable chunks.
  Code: `ingestion::prepare::chunk()`.

- **Prepare context — completed.** Context policy: structural.
  Code: `ContextProcessor::process()`.

- **Optional generated context — skipped.** This format or policy does not request generated annotations.

- **Create embeddings — completed.** Embedding model: sentence-transformers/all-MiniLM-L6-v2.
  Code: `ingestion::configured_input()` → `RemoteModels::embed()`.

- **Publish document — completed.** Published the complete document revision for search.
  Code: `Database::commit_ingestion()`.

---

# VectorNext workflow — search

Captured from a local API operation.

Client elapsed: 0.018 s (including API wait; report rendering and extra document inspection excluded).

## Invocation

Operation arguments recovered from the saved run record (report/capture switches omitted). Equivalent Python invocation, with POSIX shell quoting; outer Docker commands and environment are not captured:

```sh
python -m deployment.client search 'Voyager 1 launch Jupiter Saturn' --limit 3
```

API handler reference: `POST /v1/search → Application::search()`.

Code references identify the implementation behind each recorded step; they are not an instrumented call stack. Skipped or unrecorded steps do not list calls.

## Workflow

Search: **Voyager 1 launch Jupiter Saturn**

- **Filter documents — skipped.** 25 of 25 chunks eligible. No explicit source filter requested.

- **Semantic search — completed.** Compared meanings using a query embedding; retained 25 candidates.
  Code: `RemoteModels::embed()` → `SearchIndex::search_measured()`.

- **Keyword search — completed.** Matched the query terms; retained 24 candidates.
  Code: `FieldIndex::score()`.

- **Combine rankings and remove duplicates — completed.** Combined 25 candidates; suppressed 0 duplicates; returned 3 candidates.
  Code: `SearchIndex::search_measured()`.

- **Rerank and answer — skipped.** Standalone search returns passages without reranking or answer generation.

## Selected evidence

**Hit 1 — voyager-workflow**, 8 text spans within lines 65–79.

> Nation \| United States of America \(USA\) Objective\(s\) \| Jupiter Flyby, Saturn Flyby Spacecraft \| Voyager 1 Spacecraft Mass \| 1,592 pounds \(721.9 kilograms\) Spacecraft Power \| 3 Multi-Hundred Watt Radioisotope Thermoelectric Generators \(MHW-RTGs\) stacked in a series on a boom, producing about 158 We e… \[preview shortened\]

**Hit 2 — voyager-workflow**, lines 81–86, line 88, line 90.

> Key Dates \| March 5, 1979: Jupiter flyby - closest approach Nov. 12, 1980: Saturn flyby - closest approach Feb.17, 1998: Became the most distant human-made object after overtaking NASA's Pioneer 10 Jan. 1, 1990: Voyager Interstellar Mission \(VIM\) officially began Aug. 16, 2006: 100 astronomical unit… \[preview shortened\]

**Hit 3 — voyager-workflow**, line 179, line 181, line 183, line 185.

> Jupiter Saturn Our Solar System Universe

Excerpts are short previews of the selected source context; locations describe the source spans, not an independent fact check.

Per-stage timing and cache reuse were not recorded for standalone search.

---

# VectorNext workflow — answering

Captured from a local API operation.

Client elapsed: 33.499 s (including API wait; report rendering and extra document inspection excluded).

## Invocation

Operation arguments recovered from the saved run record (report/capture switches omitted). Equivalent Python invocation, with POSIX shell quoting; outer Docker commands and environment are not captured:

```sh
python -m deployment.client ask /app/tests/fixtures/answers/voyager.json
```

API handler reference: `POST /v1/ask → Application::ask() → answers::ask_with_options()`.

Code references identify the implementation behind each recorded step; they are not an instrumented call stack. Skipped or unrecorded steps do not list calls.

## Workflow

Question: **In which year was Voyager 1 launched, and in which years did it fly past Jupiter and Saturn?**

**Outcome: Supported answer.**

- **Prepare question — completed.** Preserved the original question. Conversation messages: 0.
  Code: `answers::ask_with_options()`.

- **Filter documents — skipped.** 25 of 25 chunks eligible. No explicit source filter requested.

- **Semantic search — completed.** Compared meanings using a query embedding; retained 25 candidates.
  Code: `RemoteModels::embed()` → `SearchIndex::search_measured()`.

- **Keyword search — completed.** Matched the query terms; retained 24 candidates.
  Code: `FieldIndex::score()`.

- **Combine rankings and remove duplicates — completed.** Combined 25 candidates; suppressed 0 duplicates; returned 20 candidates.
  Code: `SearchIndex::search_measured()`.

- **Rerank passages — completed (0.392 s).** Ranked 20 candidates with cross-encoder/ms-marco-MiniLM-L6-v2.
  Code: `RemoteModels::rerank()`.

- **Assemble source context — completed.** Prepared 1 evidence group within a limit of 5 primary passages. Groups can combine overlapping or neighboring passages.
  Code: `answers::add_evidence()` → `answers::bundle()`.

Passage omissions: primary limit: 15; duplicate evidence: 2.

Local generation model: google/gemma-4-26B-A4B-it-qat-q4\_0-gguf.

- **Assess answerability — completed (13.867 s).** Supported answer.
  Code: `RemoteModels::extract()` → `model_worker.answers.generate(..., ASSESS_PROMPT)`.

- **Extract fields — completed (18.416 s).** Read exact fields from the selected evidence.
  Code: `model_worker.answers.generate(..., PROMPT)`.

- **Validate answer — completed.** Schema, source-reference and mechanical support checks passed. Semantic correctness is not automatically established.
  Code: `answers::validate_answer()`.

- **Format answer — completed.** Applied the requested template.
  Code: `answers::render()`.

- **Optional prose rewrite — skipped.** No prose rewrite returned; it was not used for retrieval.

## Result

**Voyager 1 \| Launch: 1977 \| Jupiter: 1979 \| Saturn: 1980**

- jupiter\_year: **1979** (integer); source E1.

- launch\_year: **1977** (integer); source E1.

- saturn\_year: **1980** (integer); source E1.

## Selected evidence

**E1 — voyager-workflow**, 47 text spans within lines 3–120.

> March 5, 1979: Jupiter flyby - closest approach

> Launched in 1977 to fly by Jupiter and Saturn

> Nov. 12, 1980: Saturn flyby - closest approach

Excerpts are short previews of the selected source context; locations describe the source spans, not an independent fact check.

## Timing and reuse

Application elapsed: 33.491 s. Stage times can overlap; do not add them.

Reported cached prompt tokens: 0. Embedding/reranking cache hits were not recorded per request.
