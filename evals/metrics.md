# Evaluation measurement contract v1

These definitions guide T04-T10. T01 validates fixture integrity only. T04 provides [source-coverage diagnostics](../docs/reports/t04-retrieval.md) on separately prepared synthetic records and supplied vectors; those diagnostics do not measure model or answer quality. T10 separately measures the integrated pipeline on the 13 development questions, with per-stage source coverage, answers, cost and latency in [the completed report](../docs/reports/t10-evaluation.md). The T01 labels and holdout split remain unchanged.

## Keep stages separate

| Stage | Required measurements | What a failure means |
| --- | --- | --- |
| Parse/source mapping | Exact TXT spans; exact JSON values/types; normalized native-PDF text; OCR character/digit errors; table row/header/unit and cross-page order checks | The searchable representation lost or changed source evidence |
| Candidate retrieval | Evidence recall at a recorded `k` for dense, keyword, and fused candidates; complete-support rate | Needed source locations never entered the candidate pool |
| Reranking | Same measures after reranking; first complete-support rank; fraction of initially complete cases losing support | Ranking dropped or delayed evidence already available |
| Context assembly | Complete-support rate within the recorded token budget; repeated/irrelevant tokens; required headers and neighbors retained | The final context is incomplete or wastes the budget |
| Answer extraction | Exact typed field accuracy; all-fields-correct rate; valid citations and factual support scored separately | Evidence was misread, unsupported fields were added, or facts were changed |
| Outcome classification | Confusion matrix for supported, ambiguous, and insufficient evidence | The system guessed, missed an answer, or failed to request clarification |
| Formatting/rewriting | Template exact match; preservation of entities, dates, constraints, values, and units | Presentation changed meaning or lost context |
| Runtime | Per-stage and end-to-end times, queue time, peak RAM/VRAM, ingestion throughput, errors/timeouts | Quality or responsiveness exceeded the measured resource budget |

## Evidence matching and denominators

1. Match a returned passage through its original source locations and document revision, never through an LLM-generated annotation or a chunk-ID string alone.
2. For TXT, returned byte ranges must cover the gold span. For JSON, returned source pointers must cover the gold subtree or collectively preserve its leaves and types; field names must retain parent meaning. For PDFs, compare page regions and reading order against the gold references. Merely returning the correct document is insufficient. Define any geometry tolerance explicitly in the eventual scorer and record it in each run.
3. Let `R(k)` be the unique gold evidence IDs whose locations are covered by the top `k` passages. Several passages may jointly cover a source span. For a supported case with acceptable support sets `S`, evidence recall is `max(|s intersect R(k)| / |s| for s in S)`. Complete support is 1 only when at least one full set is covered. Report both metrics averaged across supported cases, with the case count.
4. For ambiguous cases, require the evidence for **all** listed alternatives to be retained; report this separately from supported-case recall. For insufficient-evidence cases, recall is undefined, not 0 or 1. Evaluate outcome classification and unsupported-answer rate instead.
5. First complete-support rank is the smallest prefix that covers a full valid set (or all alternatives for ambiguity). A lone high-ranking row without its needed units does not receive full credit. Report retrieval rank before expansion and context completeness after expansion separately.
6. Repeated chunks do not add evidence credit. Report retrieved tokens and repeated/irrelevant context alongside recall so that returning the whole corpus cannot be presented as an efficient result. Keep chunking and candidate/token budgets fixed in controlled comparisons.

Location recall and parse fidelity are separate: a passage may point at the right scanned region while containing a wrong digit. Answer correctness must check the value against the source, not accept the location alone. The initial corpus has explicit labels, not exhaustive relevance judgments for every possible chunk; do not report nDCG or precision as authoritative without defining and reviewing those judgments.

## Answer and presentation scoring

Field accuracy uses exact typed values and units in `expected.fields`. Count missing/wrong fields as failures and report unexpected fields separately. All-fields-correct requires the expected field set with no unsupported additions. Schema compliance is a separate measurement and cannot stand in for correctness. An answer can have a valid schema and valid source ID while citing text that does not support its value.

Keep source-reference validity, evidence completeness, and factual entailment as separate checks. Until a reviewed automated judge exists, record factual-support decisions as manual review with reviewer notes; unavailable measurements must stay null or absent, never become a fabricated score.

The conversational case retains its original history. Free-form question rewrites should preserve or carry forward the resolved opponent/year; changing only visible wording is not evidence of retrieval improvement. Compare optional contextualization modes on the original question set. Do not use gold answers as generation prompts or indexed content.

## Timing and run records

Use a monotonic clock. Record request admission, queue wait, query resolution, embedding, dense/keyword search, fusion, reranking, expansion, generation, validation/rendering, and total response time. Parallel stages can overlap; do not add stage durations and call the result wall-clock latency. For streamed output, record time to first token and completion time separately. Report failures and timeouts alongside successful request timings.

Report cold and warm runs separately, including whether weights were loaded and which caches were populated. Include model loading, parsing, OCR, context generation, embeddings, and publication in ingestion measurements. Record peak process/container RAM and device VRAM, including measurement method, batch size, concurrency, and other GPU workloads. CPU-only T01 validation time is not GPU inference feasibility evidence.

Every future run must identify:

- Git revision and whether the worktree was dirty; dataset SHA-256 and all document hashes; selected split and question IDs.
- Hardware, OS/container/image identities, model artifacts/quantization, embedding space, parser/OCR versions, prompts, and tokenizer settings.
- Context policy, chunking configuration, search/filter/fusion settings, candidate counts, rerank/context budgets, and cache state.
- Per-case candidates/ranks with original source references, final context, structured answer/status, rendered output, timing/error records, and aggregate numerators/denominators.

Use dev questions to tune. Freeze configuration before a holdout run and record any later tuning that used holdout results. Nineteen related synthetic questions cannot establish state-of-the-art performance or reliable tail latency; broader independent data and repeated load tests remain follow-up work. Recovery/atomic-update tests are separate storage correctness checks under T03-T04.

## T10 implementation and limits

`score.py` implements source coverage, exact typed answers and classification; `summarize.py` re-scores captured responses without model calls and includes HTTP failures in denominators. `replay_score.py` scores the Rust replay. The [protocol](../docs/evaluation.md) fixes PDF geometry/text criteria and documents the distinction between raw body chunks, original source labels carried into reranking, and final neighbor-expanded evidence. Runtime chunk IDs are resolved back to exact document hashes/revisions. JSON parse fidelity is measured separately from pointer-location recall. No generated annotation earns evidence credit.

`prompt_tokens` is the prepared extraction input budget, not all tokens consumed: separate generation usage sums actual assessment/extraction prompt and completion tokens. Model-service queue/backend totals also include tokenizer/template calls. Body-span duplication excludes repeated labels/headings without block byte spans; a zero is not a claim that all rendered context is deduplicated. The fraction of final evidence items covering a gold reference is a descriptive source-density measure, not exhaustive relevance precision or an irrelevant-token estimate. Factual support requires recorded source review; unavailable semantic, streaming, and tail-latency measures remain unclaimed.
