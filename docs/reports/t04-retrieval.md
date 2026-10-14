# T04 retrieval diagnostics

Date: 2026-10-14. Status: algorithm correctness and source-coverage tracing verified.

Implemented our own exact cosine search, per-field BM25 postings, typed filters, weighted reciprocal rank fusion, and conservative evidence deduplication. Each index is bound to one committed database generation and embedding space. Original source evidence remains separate from generated context. See the [retrieval contract](../retrieval.md) for formulas, defaults, and visibility rules.

## Verification

- 38 tests passed in the offline Docker core service: 18 storage regressions, 18 retrieval tests, and two source-coverage diagnostic tests. The storage subprocess helper is invoked by its parent test and is intentionally ignored as a standalone test.
- Exact cosine rankings/scores matched an independently normalized reference on 64 deterministic vectors, including a filtered top-k subset. Separate cases cover ties, very small/large magnitudes, negative/zero scores, unknown spaces, and invalid queries.
- Hand-calculated cases verified BM25 document frequencies, length normalization, scores, stable corpus statistics under filtering, RRF ranks, and weighted contributions. Other tests verified field separation, generated-field opt-in, exact numeric filters, missing/null/trust behavior, nested pointers, and deduplication boundaries.
- Search results remain consistent across atomic replacement/deletion, old reader generations, checkpoint/replay, and concurrent read-only queries. Uncommitted or invalid records stay absent.
- Container formatting and lint checks passed: `cargo fmt --check` and `cargo clippy --locked --offline --all-targets -- -D warnings`. The report-helper lint issue found during verification was fixed, and its tests reran successfully.

## Recorded source coverage

The [machine-readable report](t04-retrieval.json) contains six hand-prepared synthetic TXT documents, eight chunks, supplied vectors, all request settings, and eight diagnostic cases. Gold source intervals are evaluated only after search. Matching text in another logical document does not receive source credit. No T01 holdout questions were used.

Cells show covered required source spans, not answer accuracy. Supported cases have one acceptable support set each; the ambiguous case requires both alternatives. The no-support case has undefined recall.

| Diagnostic case | Dense | Keyword | Fused | Final | Observation |
| --- | --- | --- | --- | --- | --- |
| Keyword rescues dense cutoff | 0/1 | 1/1 | 1/1 | 1/1 | Keyword retrieval restores evidence omitted by dense top-1; final complete-support rank is 2 |
| Final limit loses rescued evidence | 0/1 | 1/1 | 1/1 | 0/1 | Reducing the final budget to one removes the recovered evidence |
| Explicit year filter | 0/1 | 1/1 | 1/1 | 1/1 | Filtering before branch limits removes the other year; final complete-support rank is 1 |
| Incorrect explicit filter | 0/1 | 0/1 | 0/1 | 0/1 | A deliberately wrong year excludes the gold evidence before scoring |
| Unit/value budget loss | 2/2 | 2/2 | 2/2 | 1/2 | Final top-1 retains the unit but loses the value |
| Unit/value retained | 2/2 | 2/2 | 2/2 | 2/2 | Final top-2 preserves both required spans |
| Ambiguous year alternatives | 2/2 | 2/2 | 2/2 | 2/2 | Both alternatives survive; no answer/outcome classification is performed |
| No support defined | — | — | — | — | Recall stays null even when lexical matches are returned |

The JSON also records eligibility outcomes, each candidate key/rank/score, keyword field/term contributions, suppressed duplicates, deduplicated lists, first complete-support ranks, original hashes/locations, and retained evidence bytes. Eligible-stage order is key order, not a relevance ranking. Duplicate chunks do not add evidence credit.

## Reproduction and identities

From the repository root with Docker Desktop running Linux containers:

```sh
docker compose build core
docker compose run --rm core
docker compose run --rm core cargo run --locked --offline --example search_eval
```

The example prints its report or accepts an output path as its final argument. When recording a new run, optional `VECTORNEXT_GIT_REVISION`, `VECTORNEXT_WORKTREE_DIRTY` (`true`/`false`), and `VECTORNEXT_IMAGE_ID` environment variables capture provenance. Omitted environment fields remain null; source hashes are always generated from the compiled inputs. Keep archived results intact when experimenting with new settings.

- Recorded image: `sha256:1fee548049054007b5e52edfe4631aecf25755abb0f41a17488c738ac166b90f`.
- Rust: 1.87.0; Linux x86_64; locked dependencies; networking disabled at test/report execution; no model/GPU service.
- Git base: `171bf3a52ec20e6775d71eb0853a211b8ba2be35`, dirty worktree. Exact retrieval/helper source hashes and Cargo lock hash are in the JSON and were checked against the workspace after generation.
- Prepared corpus SHA-256: `8d3da9aa30316b2afc3274e63d9304faf92bad948c5dc5806b575b3feb718186`.
- Case definitions SHA-256: `f9366d0f4faf7c6f4ace2c29dace9f60f3dd6a7799bda1d4dce4b0e8da763973`.

These are controlled algorithm diagnostics, not semantic retrieval-quality results. Vectors are hand-supplied; records/source mappings are prepared fixtures; the cases deliberately expose candidate losses. No ingestion, PDF/OCR, real embedding, reranking, context expansion, answer generation, latency, or scale benchmark was performed. Performance tuning and broader retrieval evaluation remain later tasks. T05 is next: TXT/JSON ingestion and durable jobs.
