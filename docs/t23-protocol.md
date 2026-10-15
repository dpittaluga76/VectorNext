# T23 fresh evidence-retrieval protocol

Defined before measured ingestion or retrieval, 2026-10-15. T22 production behavior is fixed. This is an exploratory, agent-authored retrieval comparison, not an independently administered benchmark or an answer-quality test.

## Frozen inputs and scope

Twelve attributed NIST reference pages are captured as UTF-8 TXT in `evals/evidence/fixtures/`. `sources.json` records original URLs, acquisition time, HTML/text hashes and transformations. `requests.json` contains only question IDs, questions and explicit field-focused hints. Separately, `gold.json` contains 19 facts with literal source quotes, UTF-8 offsets and source hashes: 10 single-topic questions, 10 multi-part questions and four deliberately missing-evidence questions. There are 34 positive fact requirements across 20 questions. Hints name requested topics, never answer values, source identifiers or gold spans. They are authored decompositions, not outputs of the production field planner. Repeated facts/questions are correlated.

Freeze the sources, requests, gold and this protocol before inference. Then freeze code, model lockfiles, image ID and runtime settings before the measured run. Tests validate these files; they never regenerate them. Preserve failed attempts and record amendments. Never use historical T11/T14 data or the original six-question holdout to tune this experiment.

## Two arms

- **baseline**: original question embedding, exact dense top 30 plus BM25 top 30, existing RRF and exact-evidence deduplication, first 20 reranker inputs, existing CPU cross-encoder against the original question, first five primary passages.
- **expanded**: the same original query plus each frozen hint (at most four). Each search uses the same 30/30 branch limits and top 20 results. Take unique keys round-robin from the original and hint result lists, starting with the original; stop at 20. Rerank against the unchanged original question and retain five. Record the additional query/embedding work and the complete deduplicated candidate union; this arm has a larger upstream candidate budget, not a free quality improvement.

Use pinned real MiniLM embeddings/cross-encoder, structural ingestion context, target 180 tokens and the normal encoder budget. No generated annotations, LLM calls, invented filters, answer generation, neighboring-passage expansion or production changes. Scope is the entire corpus in both arms. TXT reranker passages use original spans plus ancestor headings, following the production assembly rule. This evaluates primary evidence retrieval, not the full answer pipeline or its final context budget.

## Execution and metrics

Docker/Linux, no network/GPU, 2 CPUs and 4 GiB per process, read-only local model files and a fresh isolated database. Ingest each document once, recording failure without silently omitting it. Separate cache per arm; execute baseline/expanded/expanded/baseline in fresh processes, each on the same immutable database. First arm pass has an empty application result cache; second reuses that arm's cache. These are not cold OS/model-file cache measurements. Model/process startup and index build are separate from per-query latency. Execute the same fixed request order and retain all errors.

Score fact coverage and complete-question coverage at three stages: raw candidate union, the fixed 20 reranker inputs, and five final primary passages. A fact is covered if a frozen support quote appears after whitespace normalization in the original evidence text of a selected chunk from that support's document and source revision. Ancestor headings/generated text cannot satisfy it. Enumerated alternative source quotes may satisfy the same fact. This deliberately conservative literal test can miss valid unenumerated or split-passage support; report this limitation rather than rewrite gold after observing results. Missing and failed positive requests score zero. Missing-evidence cases have undefined recall; report their hit counts/errors separately, without calling returned passages supported or testing abstention.

Report per-question changes, macro fact recall, complete coverage, admission, error counts, candidate counts, embedding/search/rerank and end-to-end median/p95 latency, cache behavior and paired-repeat consistency. Do not infer statistical significance from repeated passes. The experiment is successful as an investigation even if the candidate does not improve retrieval. Keep production defaults; any promotion requires a separate decision and fresh validation.

## Acceptance

Frozen, attributed and isolated inputs; actual offline CPU runs; scorer/fixture and experimental algorithm checks; recorded complete results including errors and adverse changes; unchanged historical captures and production defaults. Record source/code/image identities and reproducible commands in `evals/evidence/README.md`. No GPU quality rerun.
