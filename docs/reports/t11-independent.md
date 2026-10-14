# T11: two versus five passages on public sources

Date: 2026-10-14. Status: complete, all 112 requests captured. This report records the frozen [protocol](../t11-protocol.md), its [pre-query parser amendment](../t11-protocol-amendment-01.md), and an independently sourced [NASA/USGS dataset](../../evals/independent/README.md). The original T01/T10 corpus and six unused holdout questions are unchanged. [Machine-readable results](t11-independent.json) include every case, source proof, error, timing and raw-response hash; [source review](t11-source-review.json) records the separate proof inspection.

## Decision

Keep **five primary passages** as the general default. Two is faster, but both paired comparisons lose two previously correct answers: the three-spacecraft mass question and a conversational follow-up about Voyager 2's Uranus encounter. It improves the Galileo orbit question by removing distracting material. Neither configuration is broadly reliable on this corpus; a smaller fixed count does not solve evidence selection.

This is an end-to-end pipeline evaluation, not a standalone LLM accuracy score. Six PDF questions remain in the denominator even though their source documents were not admitted. Missing inputs, retrieval/selection misses, model assessment mistakes and validation failures are identified separately below.

## Corpus and controls

The planned corpus contains 20 public documents totaling 1,879,250 bytes: 16 NASA mission-page TXT snapshots, two original NASA/JPL PDFs and two original USGS GeoJSON responses. There are 28 questions, 47 expected typed fields and 47 source references. Twenty-three cases request supported facts, two expect ambiguity and three expect insufficient evidence. Four questions need three or four different documents.

Source URLs, acquisition times, original/derived hashes and transformations are versioned. All four original PDF pages were visually inspected before annotation. Codex authored the questions and labels before inference. “Independent” means independent of the old synthetic corpus; this is not third-party administration, independent human adjudication, or proof that the model has never seen the public facts.

The same 18 admitted documents, 658 chunks, vectors, runtime images and source revisions are used throughout. Structural context, 30 candidates per branch, 20 reranked candidates, MiniLM models, Gemma 4 26B A4B QAT Q4_0, temperature 0 and seed 42 remain fixed. Only `primary_limit` changes. The model receives the separate public request file, never gold values or source annotations.

Order is **five/cold → two/cold → two/warm → five/warm**. Cold uses a fresh variant processing cache and fresh API/CPU processes with generation weights already loaded. Warm recreates those processes and reuses the same variant's disk cache. No generated-answer cache is used. OS caches and ordinary host activity are uncontrolled. The 112 planned calls repeat the same 28 questions; they are not 112 independent examples.

## Measured outcomes

| Setting | Exact outcomes / planned | Supported answers / 23 | Exact fields / 47 | Median response | Frozen gold context complete / 23 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Five, cold | 16/28 | 12/23 | 22/47 | 22.269 s | 11/23 |
| Two, cold | 15/28 | 11/23 | 20/47 | 11.081 s | 9/23 |
| Two, warm | 15/28 | 11/23 | 20/47 | 11.515 s | 9/23 |
| Five, warm | 16/28 | 12/23 | 22/47 | 21.173 s | 11/23 |

Quality and returned answer/proof objects repeat identically within each passage limit. Each block has 26 HTTP-success responses and two HTTP 400 errors: 104 successful HTTP responses and eight errors across 112 attempts, with 62 exact outcomes across repeated questions. An HTTP success can still be an incorrect abstention or ambiguity decision.

The median falls by **50.2% cold and 45.6% warm**, but that includes failed answers and earlier abstention. On the eight cases where both settings return the exact supported answer with frozen gold citation overlap, medians are 35.499 s versus 20.268 s cold (42.9% lower), and 34.887 s versus 20.380 s warm (41.6% lower). This is a matched descriptive subset, not a new independent benchmark. Frozen citation overlap undercounts some valid alternative source passages, as documented below.

Both configurations pass the real Voyager README template in both cache passes, preserve raw JSON null and zero, reject the unknown numeric station distance, and mark unspecified “Voyager” as ambiguous. Both return HTTP 400 for Maule's missing selected JSON pointer and the instrument-count quote/value mismatch. Those requests remain failures and their elapsed time remains in the latency distribution.

## What failed and why

- **UTF-8 ingestion panic, repaired before comparison.** Pioneer 10 ended a paragraph with an ellipsis. The original parser sliced a UTF-8 string at `end - 1` while counting source lines, crashing the background worker after two documents. The same calculation existed in forced chunk mapping. Both now count bytes without slicing at a non-character boundary. The new regression fails on the old code and passes after repair. The [interrupted attempt](t11-ingestion-interruption.json), old freeze and original database remain preserved. No answer request preceded the repair; sources, labels, prompts and scoring rules were unchanged.
- **Apollo strict admission rejection.** Conversion recovered the requested sample mass, command-module name and reflector description, but reported 20 low-confidence OCR regions, six uninterpreted pictures and 22 unmapped text regions. Strict ingestion rejected the partial artifact. Its two questions remain unavailable; recovered text was not quietly admitted to improve the score.
- **Perseverance busy admission.** Its upload received HTTP 503 because the processing lane was busy. No job was accepted and no retry was part of this frozen one-attempt run. Its four questions remain unavailable. This is not a measurement of that PDF's parser accuracy.
- **Cross-document selection.** On the Juno/Cassini/Dawn question, Cassini appears at reranked position eight; five primaries select Juno and Dawn, while two select only Juno. On the mass comparison, five reaches Deep Impact, Stardust and New Horizons; two omits New Horizons and abstains. The four-launch and three-launch-pad questions also lack required evidence in both configurations.
- **Conversational selection.** The Uranus follow-up carries its original history, but Neptune passages occupy the first two reranked positions. Five reaches the Uranus encounter date; two has only the Neptune-focused context and correctly abstains given that context. This is an end-to-end miss even though only one source document is needed.
- **Distractor confusion.** Five gives Galileo 5,005 context characters including both 34 Jupiter orbits and 35 encounters of its moons. The model incorrectly treats these as conflicting orbit counts. Two gives 1,422 characters, omits the moon-encounter passage and returns Atlantis/34 correctly. More evidence is not automatically better.
- **Rejected structured/quoted drafts.** Maule's magnitude/depth request selects a missing JSON pointer; the instrument-count request fails the exact quoted-value check. Validation prevents these drafts from becoming supported answers. The error responses omit the rejected drafts and full retrieval audit, limiting diagnosis. Do not infer a specific chosen pointer or instrument count from the error message alone.

The unavailable PDFs are shared by both configurations. The comparison therefore establishes a limited TXT/JSON tradeoff plus PDF admission failures; it does not establish two-versus-five PDF retrieval quality.

## Source review and metric limits

All 46 returned supported answers match their expected typed fields. Their 17 distinct field-proof groups were inspected against the cited originals and surrounding entity/unit context, with every repeated occurrence recorded in the [source-review archive](t11-source-review.json). Generic numeric quotes such as `258.5` were checked against the Pioneer 11 spacecraft-mass row. JSON pointers were resolved within the original `/features/0` record; the stored null is not a missing key, and the raw tsunami flag is not a historical claim that no tsunami occurred. This is Codex's source inspection, not independent human adjudication or an automatic factual-entailment guarantee.

The frozen scorer checks predeclared source locations, not exhaustive factual entailment. Voyager 2's Uranus/Neptune years and the follow-up can be correctly cited from prose while the gold reference points to the timeline table. Pathfinder's Sojourner fact also has another valid passage. These accepted answers retain their raw gold-overlap failures, with source review reported separately. The apparent loss of Pathfinder's gold context with two passages is not a loss of its correct answer or valid citation.

Three other references span `Launch`, a blank-line separator and a date in Juno, Cassini and Dawn. The parser preserves both text blocks, but does not map the intervening blank separator as evidence. Consequently their strict continuous byte-span coverage is false while normalized text fidelity is true. Of the 41 references belonging to admitted documents, 38 pass the frozen location/value check; the remaining three are this annotation/whitespace issue, not demonstrated loss of the facts. The six PDF references are unavailable.

Gold labels and the scorer have not been rewritten after observing these exceptions. The instrument-conflict label also encodes a chosen interpretation: seek clarification for the captured page's two/four statements. A newer dated paragraph may support a different interpretation of “currently”; this limitation is explicit in the dataset guide. No returned instrument answer passed validation in any block.

Stage coverage assigns zero to unavailable or HTTP-error responses because their full audit is absent. Differences in those aggregates do not by themselves prove ranking changed. All 26 responses with comparable audits in each cache pair have identical retrieval and reranking fingerprints between limits: 52 paired comparisons in total.

## Runtime interpretation

Hardware is the local RTX 4060 (8,188 MiB reported VRAM), Ryzen 5 7600, approximately 63.1 GiB usable system RAM, and Docker Desktop Linux containers on Windows/WSL 2. Only the generator receives GPU access. The large model uses 22 CPU expert layers; CPU embedding/reranking and the strict PDF adapter are unchanged from T10.

Across the 26 successful HTTP responses in the cold blocks, median prepared extraction size drops from **1,959 to 1,140 tokens**. Successful-response generation audits record 76,217 input / 2,325 output tokens for five, versus 39,284 / 2,167 for two; warm two reproduces its token counts. The two HTTP validation failures in each block consumed additional generation work whose token usage is absent from the error responses. These totals are therefore audited lower bounds, not full billing-style totals. Cached prompt tokens in the returned audits are zero.

Five/cold median inner hybrid-search time is **0.888 ms** at 658 chunks. Cold reranking/preparation is **349 ms**, and evidence assembly plus model tokenization is **669 ms**. For two, reranking falls from **319 ms cold to 1.69 ms warm**, confirming cache reuse; query embedding/token checks fall from 13.5 to 3.14 ms. The slower warm overall median shows why a small local timing change is not a statistically established cache speedup. Generation dominates end-to-end time. Stage timings are nested, and their successful-response medians cannot be added to reconstruct the all-attempt median.

The five/cold run samples 6,310 MiB whole-device VRAM and about 22.89 GiB generation-container memory, including roughly 13.67 GiB mapped/file cache. Those are whole-device/cgroup measurements, not model-only GPU allocations or process RSS. Samples are about 1.36 seconds apart and can miss short peaks; lifetime container peaks can include earlier work. Queue measurements include template/tokenization operations as well as inference. There is one user request at a time, so this is not a concurrency, tail-latency or sustained-load test.

## Reproduction and remaining work

Use the [dataset guide](../../evals/independent/README.md) and a fresh run name. Raw captures remain under ignored `data/t11/20261014-independent-fixed/`; the interrupted attempt is under `data/t11/20261014-independent/`. Application/model operations run in three Docker containers; a standard-library host runner orchestrates and measures them. Source acquisition is separate from offline runtime operation.

Verification completed:

| Check | Result |
| --- | --- |
| Rust storage, retrieval, ingestion, answer and service checks | 91 passed, including the new UTF-8 regression |
| Fixture, scorer, protocol and summary checks | 54 passed offline |
| Worker, answer, scheduler and transport checks | 22 passed with real pinned CPU encoders and mocked generation |
| Formatting, Clippy, Compose and frozen input integrity | Passed |
| Four comparison blocks | All 112 attempts retained, including eight HTTP errors |
| Separate one-source README CLI drill | Ingest, search and answer passed; exact 1977/1979/1980 template |

The 167 software checks are separate from the answer-quality denominator. An initial worker-test invocation used the processor image's system Python and failed because ONNX Runtime lives in its isolated model environment. The corrected offline command passed all 22 checks:

```powershell
docker run --rm --network none -v "${PWD}/models:/models:ro" --entrypoint /opt/model-env/bin/python vectornext-app-processor:t10 -m unittest model_worker.test_worker model_worker.test_answers model_worker.test_scheduler deployment.test_processor_server -q
```

The [README demo record](t11-readme-demo.json) captures an additional CLI drill in a fresh one-document database after all timed blocks completed. It used the packaged NASA TXT and public request, default five passages, and returned `Voyager 1 | Launch: 1977 | Jupiter: 1979 | Saturn: 1980`. This drill is outside the benchmark counts. Its captures are under `data/t11/readme-voyager-20261014/`. All three T11 services are stopped; databases, caches, raw captures and the original interrupted attempt are retained. Other projects and prior evaluation volumes were not changed.

The follow-up plan separates operational reliability from quality work: visible coordinator failure/recovery, actionable PDF diagnostics and bounded busy retries first; then question-aware evidence coverage and structured pointer selection, evaluated on new frozen data. T11 becomes retained regression evidence. The original six T01 holdout questions remain unused.
