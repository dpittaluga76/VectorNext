# T08 local retrieval and answers

Date: 2026-10-14. Design reference: architecture sections 7–9. Machine: the existing RTX 4060 8-GB host, with Gemma 4 26B A4B QAT Q4_0 and 22 CPU expert layers. Exact identities, responses, measurements, and earlier development failures are preserved in [the JSON report](t08-answers.json).

## Implementation

The Rust `answers::ask` library and Docker `ask` tool now query a committed snapshot, preserve the original question/conversation, embed with MiniLM, retrieve with our own cosine/BM25/RRF implementation, rerank with the pinned CPU cross-encoder, and assemble original source evidence. Generated annotations can help retrieval but cannot serve as answer evidence. Source intervals, headings, PDF table labels/units, and complete JSON records remain traceable; overlapping bundles merge without repeating table rows. Actual model token counts enforce the input/output budget.

Gemma assesses answerability before extracting source-linked fields. Prose requires exact quotes containing literal values. For JSON, the model selects the record and relative pointer; Rust reads the exact value instead of letting the model copy it. This preserves arbitrary-precision numbers and distinguishes zero, raw null, missing fields, and unsupported counts. Null placeholders in model selections are not public answer values. An explicit null that cannot satisfy a non-nullable field becomes an audited insufficient-evidence result. Explicit filtered JSON lookup can bypass generation entirely.

Templates render validated fields deterministically. Optional conversational question/answer rewrites are labeled drafts and do not replace authoritative inputs, values, or citations. The fictional Pelé case produces:

> Match year 1954, Pele goals: 3, rival: Argentina

The GPU container now admits requests through a bounded priority wrapper. Interactive requests precede waiting enrichment; active inference finishes first. Queue deadlines and overload errors prevent indefinite waits. Backend uncertainty stops further admission until restart. The backend binds loopback; no model port is exposed on the host. See [the contract](../answers.md) for exact bounds.

## Verification and interpretation

The Rust suite passed 83 tests, including 10 answer tests. All 10 answer tests also passed on a Docker disk volume. Python coverage totals 18 tests: the 17-test worker/answer/scheduler suite passed, then the final nine answer tests passed after adding exact presentation literals. Formatting, Linux Clippy with warnings denied using the final source, and Compose validation passed. Tests cover exact source types/precision, forged proof rejection, source separation, budgets, filters, ambiguity in complete structured lookup, PDF table deduplication, queue priority/FIFO/non-preemption, expiry, overload, and uncertain-backend rejection.

Live development checks use the five existing synthetic source documents indexed by T07 under the generated policy: 28 chunks at generation 5. They exercise the requested formatted answer and prose draft, conversational references, ambiguity, absent evidence, JSON zero/raw-null/unknown-count/missing fields, scanned text, cross-page instructions, table units, deterministic structured lookup, and aggregate rejection. Expected results are scored separately from schema/source validation. No T01 holdout labels or fixture regeneration were used. These cases informed prompt/schema changes and therefore do not establish held-out retrieval or answer quality.

All 13 cases passed in the complete final answer pass. The later presentation-only change passes exact Rust display literals as strings to Python, preventing decimal rounding; its nine Python answer tests and live Pelé prose check passed. Both image identities and this separate follow-up are recorded in the JSON. The complete pass's eleven model-dependent CLI calls ranged from 10.23 to 26.91 seconds, median 17.79 seconds. Structured lookup and aggregate rejection took about 1.27–1.29 seconds; the final optional-prose follow-up took 26.44 seconds.

The live scheduler test completed in the order active background → interactive → waiting background. Active work was not interrupted, and health responded in 8.1 ms while generation ran. Individual completion times from submission were 4.55, 8.66, and 12.88 seconds respectively. With Gemma stopped, structured zero/null lookup succeeded in 1.72 seconds; a generation-dependent question failed explicitly in 2.51 seconds. The database reopened at generation 5 with five documents, 28 chunks, and all five jobs committed. Only VectorNext's GPU service was stopped; stored data/cache were retained.

Per-case timings in the JSON report include a fresh CLI/CPU-model process, retrieval/reranking, evidence token counting, generation, and optional rewriting. Embedding/reranking caches are reusable; generation prompt caching was disabled. This is one sequential pass on a small corpus, not a throughput benchmark, a cold-cache comparison, or a new peak-memory measurement. Two-stage supported answers cost two model calls; optional prose adds a third.

## Failures that shaped the implementation

Earlier runs are retained in the JSON report rather than discarded:

- A combined extraction prompt picked the first event for an ambiguous question. Separate answerability assessment resolved that development case, at additional latency.
- Alphabetically serialized schemas placed dependent fields before status. Keeping explicit wire order improved status handling; evidence IDs now precede source-format-dependent proofs for the same reason.
- An optional rewrite returned another question instead of a declarative answer. The prompt and draft checks now require the answer's literal fields, but semantic faithfulness still needs evaluation.
- Gemma copied a stored null count as zero even when null was permitted by the candidate schema. Exact-source validation rejected it. The final JSON contract removes value transcription: Rust materializes the model-selected pointer and applies nullability afterward.
- Selecting proof values before evidence IDs made a mixed TXT/JSON query enter the prose branch and fabricate a quote. Source checks rejected it; selecting the evidence ID first addressed the schema-order problem.
- Initial PDF expansion repeated a complete ancestor table alongside its rows. Expansion now adds ancestor headings and sourced labels, merges shared context, and checks the real PDF artifact for duplicate rows/headers.
- Another workload caused heavy GPU contention during a late null-count test. The user authorized retries. That semantic error also reproduced with the GPU available, so it was not attributed solely to contention. Only VectorNext's service was stopped after testing.

## Remaining boundaries

Schema validity and mechanical source support do not prove that the right event, field, or interpretation was chosen. Status assessment and JSON record/pointer selection remain model decisions. Exact quotes can still be semantically misapplied. Retrieval/top-k/token budgets can omit competing evidence; this is not exhaustive ambiguity detection. Prose drafts have no automatic semantic guarantee. The English aggregate guard is conservative, not a complete intent classifier; full corpus aggregation is not implemented.

The generation queue is in memory, cannot preempt active work, and can expire a waiting interactive request during long inference. Sustained interactive traffic can starve background work, whose retry state belongs to durable ingestion jobs. There is no shared CPU admission yet. The CLI releases its writer lock before inference but still needs that lock to open its initial snapshot; simultaneous same-database ingestion and answering need the shared application owner in T09. API/readiness, integrated deployment, and exercised export/restore remain T09. Broader quality/latency comparisons remain T10.

## Reproduction

Use README's model setup and T07 corpus commands, then build the current ingestion image. With that corpus and a healthy idle generation service:

```sh
docker compose -p vectornext-t07 -f compose.ingestion.yaml run --rm --entrypoint python ingest -m model_worker.verify_answers /storage/policy-check/generated /storage/t08-check
docker compose -p vectornext-t07 -f compose.ingestion.yaml run --rm --entrypoint python ingest -m model_worker.verify_scheduler
docker compose -p vectornext-t07 -f compose.ingestion.yaml stop llm
```

The recorded session reused `/storage/t07-corpus/generated` in the `vectornext-t07_ingestion-data` volume. Raw reports remain under ignored `data/t08/`; the compact committed JSON preserves final answers/evidence/audits and earlier outcomes. Models, source database, and reusable caches remain local and outside Git.
