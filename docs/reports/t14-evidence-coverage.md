# T14 — Question-aware evidence coverage

Completed 2026-10-14 (local date). Keep ranked five as the default. `coverage_v1` is a measured, opt-in experiment: it reduced median latency by 43.5–44.4% on this corpus, but did not increase strict exact outcomes and did not clear the predeclared adoption gate. All 96 requests completed; test services are stopped, with captures/data retained.

## Results

| Configuration | Exact outcomes, cold / warm | Median seconds, cold / warm | p95 seconds, cold / warm | HTTP rejections per pass |
| --- | --- | --- | --- | --- |
| Ranked five (default) | 8/16 · 8/16 | 29.18 · 28.53 | 37.33 · 36.70 | 5 |
| Ranked two | 7/16 · 7/16 | 18.19 · 17.34 | 22.07 · 22.57 | 4 |
| Field coverage, up to five | 8/16 · 8/16 | 16.50 · 15.86 | 31.75 · 30.80 | 5 |

These are 16 questions repeated six times, not 96 independent questions. Times include errors and abstentions; p95 uses nearest rank. Each strategy repeated the same correctness outcomes in both cache passes. No sources or failures were removed from denominators. The [machine-readable report](t14-evidence-coverage.json) contains all per-case outcomes, paired deltas, resource samples' maxima and raw-response hashes.

Both five and coverage produced six correct supported answers out of 13 supported cases, with all six passing annotated proof overlap. Two produced five. All strategies correctly handled the two insufficient-evidence cases. The one frozen ambiguity label failed everywhere, but its wording permits a reasonable minimum-distance interpretation; see the [source-review exception](t14-source-review.md). Do not describe all three responses to that case as equally wrong factual answers.

Seven of 14 planned source-support contexts were complete with ranked five/two, versus six with coverage, in each pass. The candidate's paired loss against five was the ambiguity case's three-alternative support set; that requirement is conservative given the wording issue. Rejected requests have no full success trace and receive no context/proof credit; this is not proof that their retrieval lacked support. The adoption gate failed on the frozen ambiguity outcome and its context requirement. The small corpus, annotation limitation and unresolved proof-validation defects support retaining the established default while making the faster option available explicitly.

## What the experiment showed

- **Field-specific selection can help within the candidate pool.** Coverage recovered all three launch sources and selected the correct years. The existing validator then rejected `Feb. 25,1969`. Ranked five omitted NEAR Shoemaker's launch evidence.
- **Selection cannot fix missing candidates.** Magellan's mass never reached the 20-candidate pool for the three-mass request. A future field-specific candidate search needs a separate experiment.
- **Document diversity alone is insufficient.** Ranked two selected Nepal metadata and the Sumatra event record. Coverage additionally selected Nepal's actual event record and answered both magnitudes; five also answered correctly.
- **Smaller contexts have different losses.** Coverage missed the first/second Mercury encounter ranges for the explicit three-flyby question. Five found all three and drafted correct values, but validation rejected the grouped number `48,069`.
- **JSON constraints worked, without a demonstrated gain over five here.** Existing typed paths, array coordinates, source null and zero were exercised with the actual local model. The baseline already answered these single-record cases correctly. Catalog existence/type checks cannot establish field semantics.
- **Numeric proof validation is the next priority.** Correct grouped numbers/date quotes were rejected. A separate deterministic probe also accepted quote `3` from `3,000` because boundaries are checked inside the quote. [Probe results](t14-proof-boundaries.json) and [source review](t14-source-review.md) are retained; T15 scopes the repair. It was not applied during this comparison.

[Readable coverage workflow](t14-coverage-workflow.md) · [Retained failure workflows](t14-failure-workflows.md). These are selected examples; the complete score report remains authoritative for evaluation totals.

## What was tested

The default ranked five, ranked two, and opt-in `coverage_v1` share the same exact hybrid index, 30/20 candidate budgets, source bytes, CPU embedding/reranking models, Gemma 4 26B A4B QAT configuration and validation rules. Coverage changes retrieval history focus, field-specific ranking, primary selection, neighbor expansion and JSON pointer constraints together. This is a bundled diagnostic experiment; it cannot attribute a gain to one component without a separate ablation.

The [protocol](../t14-protocol.md) predates acquisition/annotation, implementation and inference. [Data freeze](../../evals/coverage/data-freeze.json) binds eight new public sources, 16 questions, 27 references, public requests and annotation v2; [execution freeze](../../evals/coverage/execution-freeze.json) binds 77 runtime/runner/model-lock files. No T11 sources, labels, scorer or freeze was rewritten. The six T01 holdout questions remain unused. Inference code, prompts, labels and candidate rules stayed fixed during comparison.

All eight sources ingested into 201 chunks; all 27 source references passed parse fidelity. Acquisition retained full NASA article text (including footer distractions) and original USGS response bytes. This corpus covers TXT and JSON, not PDF quality; T13 exercised real PDF recovery separately. Sources and terms are in the [provenance manifest](../../evals/coverage/sources.json). The stored USGS tsunami flag is evaluated as a raw field, not as a historical claim about tsunami occurrence.

## Method and limits

Six counterbalanced blocks run five/two/coverage cold, then coverage/two/five warm, with 16 cases per block. Each strategy has its own application cache and new API/CPU processes per block; GPU weights stay loaded and generation response caching stays disabled. Cold does not mean cold operating-system/model memory. End-to-end times include extra field reranking, prompt tokenization, status assessment, extraction and validation. Startup is excluded from query latency; initial readiness took 126.01 seconds. A brief CPU-only diagnostic compilation ran during the final block; this and normal host activity limit timing precision. This is a local diagnostic comparison, not an isolated microbenchmark.

Sampled whole-device VRAM peaked at 6,365 MiB. The generator's sampled memory maximum was 22.97 GiB including mapped files/cache; processor and API maxima were about 783 MiB and 32.9 MiB. These are sampled maxima, not guaranteed transient peaks; whole-device VRAM includes desktop/other device usage. Median prompt tokens in available HTTP-200 reports were 1,965 for five, 1,214.5 for two and 978 for coverage (both passes). Error responses lack that token count, and HTTP 200 includes abstentions/wrong outcomes, so these are not all-request token medians.

Annotation v2 accepts only whitespace gaps between source spans and explicitly lists duplicate supporting occurrences. It never grants credit for missing source characters, units, another document or another revision. JSON proof scoring also checks the actual selected pointer, beyond record-level overlap. Mechanical validation and source overlap do not establish semantic entailment. HTTP failures remain in every overall denominator; they lack a full success report, so their context metrics are unavailable rather than evidence that retrieval itself failed. Manual review explains failures without changing frozen scores.

The adoption gate requires no per-case exact-answer or annotated-support regression in either pass, all negative outcomes correct, and at least 20% lower median latency in both passes. This small, related-domain corpus would still not establish general superiority even if it cleared the gate. The same implementation workflow authored the questions and annotations; this is a new frozen corpus, not an externally adjudicated or blind benchmark.

## Implementation and verification

- Rust keeps original questions/history, explicit filters, snapshot generations, source provenance and exact JSON values authoritative. Field selection is bounded, opt-in and auditable; default ranking/model messages are unchanged.
- Python derives typed pointer paths from the actual source record, including arrays and escaped names. It never transcribes authoritative JSON values; catalog limits and the prompt token budget fail closed.
- The client exposes `--evidence-strategy coverage_v1`. Workflow reports describe recorded selection and function references without claiming model reasoning or guaranteed coverage.
- 101 Rust checks and 116 Python checks passed; Linux formatting, Clippy, Compose validation and both final images passed. This includes new history/filter/selection, exact pointer/type/null/zero, whitespace-gap and client/report regressions. A first compilation used syntax unsupported by the pinned Rust compiler; it was corrected before freezing. Initial test commands also encountered missing host `jsonschema` and two incorrect module names; the documented Docker suites ran successfully afterward.

Actual runtime images, identical across strategies:

| Service | Image ID |
| --- | --- |
| API | `sha256:317850aeee7a55541f044885751b72ddaedda0e4bff0ae5fb29f5eb2200bade7` |
| CPU processor | `sha256:49907ea7d1ddb14f299dfe9bd394db97381dd5c9f0551c70d7c0936a784e4116` |
| GPU generator | `sha256:7c17888aac221414f8373c7bff0fadd5f6ee458ffa7b025255e3fefe65fb1949` |

The API/processor use T14 tags; the GPU runtime retains the pinned T10 tag/model settings (temperature 0, seed 42, 4,096-token context, 22 CPU expert layers). Runtime/model lock identities are captured with each block. T14 byte-bound fixtures/manifests preserve acquisition line endings through Git attributes.

## Artifacts

[Reproduction and experimental CLI](../../evals/coverage/README.md). Raw captures, resource samples and complete source inspections remain under `data/t14/20261014-coverage/`; the acquisition HTML remains under `data/t14/source-downloads/`. These paths are ignored by Git. Runtime data and caches are isolated in the stopped `vectornext-t14` project; no volumes were deleted. Historical T11 execution now differs in eight files, including the model worker; reproduce it from its original recorded commit rather than rewriting its freeze.
