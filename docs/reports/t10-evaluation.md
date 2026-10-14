# T10 architecture evaluation

Date: 2026-10-14. Status: complete. Design reference: architecture sections 6–10 and [the protocol and recorded amendments](../evaluation.md). Full measurements, identities, per-case outcomes and source review are in the [JSON evidence](t10-evaluation.json). The comparison uses the unchanged five synthetic source files and 13 development questions; the six holdout questions remain unused. This establishes behavior on a correctness seed set, not state-of-the-art or real-world retrieval quality.

## Recommendation

Keep structural context, exact cosine/BM25 fusion, CPU reranking, the pinned Gemma 4 26B A4B QAT Q4_0, and the existing three-service deployment. Generated context remains optional: it improves one intermediate table rank but adds substantial ingestion work without improving the final development answers. Keep 30 candidates per branch, 20 reranked candidates and five primary passages as the general defaults. Two primaries reduced median response time by 30–32% while preserving all development answers; expose this as an opt-in experiment pending independent multi-passage evaluation. One primary demonstrably loses an answer. No measured bottleneck justifies an approximate index, Redis, MinIO, or distributed infrastructure.

## Quality and cost

Each row uses the same questions, model artifacts, temperature 0, seed 42, source bytes and 180-token soft chunk target. All policies produced the same 28 chunk bodies/spans. Generated context reserved additional embedding space but did not change these boundaries. Ingestion is one measured pass per policy after CPU readiness; it includes PDF/OCR preparation, publication and polling. GPU/model startup is separate.

| Configuration | Correct outcomes, cold / warm | Median response, cold / warm | Ingestion, five files |
| --- | --- | --- | --- |
| Plain embeddings, inherited structural keywords | 13/13 / 13/13 | 19.660 / 18.360 s | 28.206 s |
| Fully plain retrieval: structural/generated keyword weights 0/0 | 13/13 / 13/13 | 18.230 / 17.742 s | Reuses plain ingestion |
| Structural, default five primaries | 13/13 / 13/13 | 18.077 / 17.952 s | 24.757 s |
| Generated, default five primaries | 13/13 / 13/13 | 17.842 / 17.572 s | 72.157 s |
| Structural, one primary | 12/13 / 12/13 | 9.727 / 9.617 s | Reuses structural ingestion |
| Structural, two primaries | 13/13 / 13/13 | 12.577 / 12.229 s | Reuses structural ingestion |

The initial application's keyword weights were 1/1/1 for evidence/structural/generated fields, independently of embedding policy. The first plain row is retained and labeled accordingly; the second row corrects the comparison with explicit zero context-field weights. Source structure remains stored for inspection and mandatory evidence expansion. The correction did not change answer/model prompts, chunks, vectors or labels. The API now exposes independent structural/generated weights; defaults are unchanged.

All baseline passes preserved 18/18 exact typed fields across ten supported questions, the one deterministic template, one ambiguous outcome and two insufficient-evidence outcomes. Zero, raw null, unknown assists, the string ID `007`, table units, a cross-page condition and the scanned torque all remained distinct. Fourteen development source references passed the format-specific parsing checks under every policy. Source inspection checked each distinct quoted/pointer proof against its cited original source representation and question constraints. This is Codex source review, not an independent human judgment or calibrated automatic entailment score. Free-form presentation drafts were not benchmarked here.

Raw body-chunk recall is 96.7%, with complete raw support in 9/10 supported cases: table column labels live in source-backed metadata rather than a separate body chunk. Those labels are already reattached before reranking. Including original source labels gives complete top-five support in 10/10 cases, and baseline final assembled context has complete support in 10/10. Both ambiguity alternatives survive. Insufficient-evidence questions have no recall denominator. The raw/body difference is not a lost table header or a reranker error; both measurements remain in the scorer.

There is a genuine ranking weakness: the H2 high-temperature exception outranks the requested nominal-flow row after reranking. The complete table support's fused rank is 4 with plain embeddings, 2 with structural embeddings, and 1 with generated embeddings/keywords. Disabling the generated keyword field returns that last rank to 2; increasing its weight from 1 to 2 adds no further gain. Reranking places the nominal row second in all three baseline policies, removing the generated policy's intermediate advantage. Neighbor/source expansion then supplies a correct answer. With one primary, the row is omitted and Gemma correctly returns insufficient evidence; this is a false negative caused by context selection, not a fabricated value.

The baseline includes much more context than these questions need. Across the ten supported cold-pass questions, 11 of 55 plain evidence items and 11 of 54 structural/generated items cover at least one gold source reference. That approximately 20% source density is a descriptive proxy, not exhaustive relevance precision: some remaining items are useful background. Recorded body-span overlap is zero, but repeated labels/headings without body byte spans are outside that metric; rendered text can still repeat. Returning a larger context is not treated as a relevance improvement.

Two primaries restored the nominal H2 row, its units and its 20 C condition. Both passes retained complete final context in 10/10 supported cases, 18/18 exact typed fields, the ambiguity outcome and both insufficient-evidence outcomes. Median prepared extraction size fell from 1,078 to 648 tokens; gold-bearing item density rose from 11/54 to 10/22, about 45%. Median response time fell by 30.4% cold and 31.9% warm. Each pass used 23 generation calls and 14,008 input tokens, compared with 24 calls and 23,965 tokens for the structural baseline; the unknown-count case abstained during assessment instead of after extraction. These are repeated measurements of the same 13 questions, not 26 independent examples.

The one-primary trial retained only 9/10 complete supported contexts, mean source recall 93.3%, and 15/18 exact fields. Its table answer was insufficient evidence in both passes; it did not fabricate the nearby exception value. Its smaller 577-token prepared prompt and faster median include that failed answer and its skipped extraction, so the speed result cannot be treated as an equivalent-quality improvement. All trial responses are retained.

## Runtime and resources

These are sequential local runs, one request at a time, with weights loaded and normal host activity. The cold-cache pass recreates API/CPU services with fresh processing caches; readiness includes a synthetic reranker warmup. The warm pass repeats the same 13 questions. The answer is generated again every time; there is no answer cache or prompt-KV reuse requested. OS file caches are uncontrolled. The two passes do not establish reliable tail latency or statistically significant differences of a few tenths of a second.

Structural baseline medians:

| Stage | Cold-cache | Warm-cache |
| --- | --- | --- |
| Query embedding/token preparation | 12.664 ms | 2.920 ms |
| Exact dense search | 0.030 ms | 0.026 ms |
| Keyword search | 0.012 ms | 0.011 ms |
| Fusion/deduplication | 0.030 ms | 0.024 ms |
| All core search stages | 0.096 ms | 0.077 ms |
| Reranking and source preparation | 180.731 ms | 1.378 ms |
| Assembly/model tokenization | 404.178 ms | 384.479 ms |
| Answer-model operations | 17.358 s | 17.572 s |
| Model-service queue, total per question | 1.868 ms | 2.021 ms |

Generation dominates latency. Nested stages overlap and must not be added as wall time. Model operations include assessment and, when supported, extraction; the source-null guard can abstain after extraction. Each baseline pass used 24 generation calls. Prepared extraction prompt medians were 1,108 / 1,078 / 1,067 tokens for plain / structural / generated, while actual total model input per pass was 24,392 / 23,965 / 23,720 tokens. The JSON report separates these quantities and actual completion tokens.

Generated ingestion produced eight annotations, mostly redundant summaries. Its context stage took 47.215 seconds, versus about 0.05 seconds for the plain no-generation stage. CPU readiness plus complete ingestion/snapshot/sampling wall time was 40.067 / 33.088 / 80.895 seconds for plain / structural / generated. CPU process readiness accounted for 11.102 / 7.628 / 7.725 seconds respectively. PDF preparation dominates the non-generated ingestion work. The difference between the two non-generated policies is one sequential measurement with uncontrolled file caches, not proof of a structural parsing speedup.

Memory comes from cgroup `memory.current`, anonymous/file breakdowns and separately labeled lifetime peaks, plus whole-device NVIDIA samples. Probes add overhead, generally sample about every 1.3–1.4 seconds, and can miss instantaneous peaks. File memory includes model mmap/page cache; summing separate service maxima is not a simultaneous peak. Missing samples remain unavailable, not zero.

| Resource | Maximum sampled usage across measured phases |
| --- | --- |
| Whole GPU, including other host usage | 6,352 MiB of 8,188 MiB |
| Rust API container | 28.9 MiB |
| CPU processor container | 1,777.3 MiB, during ingestion |
| Generation container | 23,398.8 MiB, including mapped model/file cache |
| Sum of three container currents in the same sample | 23.733 GiB |

Generation-container anonymous memory peaked at 9,308.3 MiB and file memory at 13,996.7 MiB; these are separate maxima. This placement fits the observed 63.1-GiB system RAM, but the 8-GB GPU alone does not describe its memory needs. Model restart to full API readiness took **136.817 seconds**, including weight verification/loading with the CPU service already ready. File-cache state was uncontrolled; this is a measured restart, not physical cold boot.

The live queue completed active background work, then the interactive request, then waiting background work. Their elapsed times were 4.848 / 8.837 / 12.977 seconds; health responded in 6.36 ms during generation. Queue wait accumulated 13.658 seconds across the three requests and backend work 12.999 seconds. Overlapping waits are not wall time. This confirms non-preemption and priority over waiting work; it is not a sustained-load or starvation test. Model-service counters also include tokenizer/template operations, which are distinct from generation calls.

## Capacity and parameter replays

On the same Ryzen 5 7600 / RTX 4060 host, a release-mode core-only probe built 400 synthetic documents averaging 20,428 bytes, with 32 chunks each: 12,800 supplied 384-dimensional vectors. Across 30 queries, full hybrid search median was **9.946 ms** (dense 6.515 ms); a 20-document filter reduced it to **0.725 ms**. Index construction took **0.200 seconds**, and peak process RSS was **79.3 MiB**. Supplied-record preparation took 0.757 seconds on container tmpfs; this excludes parsing, embeddings, generation and disk durability throughput. The model service was resident but idle. This supports retaining exact search at the tested capacity; it does not measure semantic quality on 400 real documents.

Offline replay used the actual committed fixture vectors and captured development queries, with branch budgets 5/10/20/30 and four structural/generated keyword-weight combinations. All 48 configurations retained full support within five fused results after original source labels were included; these are repeated views of ten supported questions and one ambiguous question, not hundreds of independent examples. The 39 baseline replay responses matched the original API retrieval responses exactly. No new model calls or gold-derived requests were made. These saturated results do not justify narrowing the general candidate budget. They do identify the table rank effect above. Keep current chunks, reranker/model sizes and field-weight defaults until a broader corpus supplies meaningful failures.

## Verification and follow-up

| Check | Result |
| --- | --- |
| Rust storage, ingestion, retrieval, answer and deployment checks | 90 passed |
| Python fixture/scorer checks | 36 passed |
| Python worker, answer, scheduler and transport checks | 22 passed |
| Linux formatting and Clippy with warnings denied | Passed |
| Base application and T10 Compose configuration | Passed |
| Original dataset hashes/source contracts | Passed; no fixture or label regeneration |
| Six configurations, 13 questions, two cache passes | 156/156 HTTP successes; 154/156 correct outcomes |
| Source review | 118 supported outputs mapped to 14 reviewed distinct proof signatures |

The two incorrect outcomes are the retained one-primary table false negatives. Source review checked complete cited source context and question constraints, not merely whether a quote occurs. An initial Python verification command named a nonexistent transport module; the 18 worker checks passed, then the corrected four transport checks passed. There are no unresolved automated-test failures.

The archive includes every attempted configuration, source/proof review, image/source/model identities, queue/startup measurements and cold/warm numerators/denominators. The later API build adds explicit structural keyword weights for the corrected plain comparison; processor/model prompts and artifacts remain unchanged. Image-specific source manifests distinguish the two API builds. Historical working-tree hashes must not be mistaken for a running image's source identity.

Raw traces remain in ignored `data/t10/20261014/`; the isolated T10 databases/caches and model files are retained. All three T10 services were stopped after verification. T07/T09 data is untouched. No holdout question was sent to a model. Reproduction commands are in [the evaluation guide](../../evals/README.md).

The next useful work is an independent corpus with realistic distractors, questions requiring several distant passages, conflicting/ambiguous records, harder tables/OCR and explicit quality/latency targets. Compare the general and reduced-context settings there before changing defaults. Keep the existing holdout separate. Optional generated context should have to show a final retrieval/answer benefit that pays for its measured ingestion cost.
