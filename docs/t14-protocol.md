# T14 — Question-aware evidence coverage, protocol v1

Written before acquisition, labels, implementation and any T14 model queries. T11 is diagnostic development evidence; neither its labels nor its original scores will be changed. The six T01 holdout questions remain unused.

## Hypothesis and fixed candidate

Evaluate an opt-in `coverage_v1` strategy against unchanged ranked five and ranked two. All use structural context, exact hybrid search (30 per branch, 20 fused candidates), the same CPU encoders, local Gemma 4 26B A4B QAT at temperature zero, exact source-value materialization, source validation and the existing input/output token limits.

The candidate uses the current question and latest user turn as its retrieval focus (assistant turns remain in the full answer input, but not retrieval). It reranks the same candidate pool separately for each requested field, placing the field name/description before that focus. Take the best candidate for each field in sorted field-name order, then the second-best for each field, deduplicating chunk keys, capped by the requested primary limit (five in this experiment). Fill to two from the general ranking if necessary. This gives two to five primary candidates; budget and source deduplication can reduce the actual evidence count. Preserve the original general ranking and record all field rankings and selection decisions. No unconditional neighbor expansion for this strategy: headings/table labels already included in source bundles remain available. Field-specific selection may improve source diversity without forcing an irrelevant document into the context. It cannot recover a source missing from the 20-candidate pool and does not establish semantic coverage.

For JSON, the candidate constrains each evidence ID to existing scalar/null pointers of the requested type in that actual record. Raw null remains selectable so Rust can distinguish explicit source null from a missing pointer and abstain for a non-nullable request. Pointer paths, not values or gold labels, may be added to the visible prompt; they count against the token budget. Use bounded enumeration and fail closed on excess, never silently remove source fields. The baseline schemas and messages remain unchanged. No entity-specific code, benchmark values or gold references may reach retrieval or generation.

## New corpus and questions

Eight new public sources: NASA Mariner 4, 6, 9, 10, NEAR Shoemaker and Magellan articles as attributed TXT snapshots, plus original USGS GeoJSON responses for the 2015 Nepal and 2004 Sumatra events. None are T11 sources. This is a small diagnostic TXT/JSON corpus, not a representative benchmark; PDF reliability was exercised separately in T13.

Prepare 16 questions before any model run: single-source facts, distant facts within one document, comparisons across documents, conversation reference resolution, nearby numeric distractors, JSON pointers, raw null/unknown counts, and underspecified/absent facts. Public request files contain only ordinary questions, field descriptions/types and any conversation, never gold values or source locations. Public factual history is not evidence. All sources and all 16 questions remain in denominators even if admission or generation fails.

## Annotation protocol v2

Each field has an explicit set of acceptable source references, frozen before inference. Annotate duplicate occurrences where the source supports the same fact; include contextual identity/unit text, not just a matching number. Exact answer correctness and source-support completeness are separate. Text references retain the original byte interval and expected text; additionally partition that interval into maximal non-whitespace byte runs. A union of source spans must cover every such run. This permits parser boundaries across blank lines only; it never forgives missing letters, digits, units or punctuation. JSON pointers stay exact and revision-scoped. All exact values and every reference are checked against source bytes before freezing. Unknown values and missing pointers are not zero. Semantic entailment remains a human source-review responsibility.

Do not apply v2 retrospectively to T11's published scores. Retain T11's original scorer, freezes and review exceptions. Independently test v2 on synthetic whitespace-gap and missing-content cases.

## Freeze, execution and analysis

Create a data freeze containing this protocol, provenance, source bytes, labels, public requests and scorer before inference. Separately freeze execution code, Compose, model locks and runner after implementation/tests and before the first comparison query. Record actual image IDs, model identities, database generation, all raw responses/errors, selected sources, field rankings, prompt tokens, timings and resource samples. All variants use identical source bytes and runtime images. Do not alter candidate rules, questions, labels, prompts or scorer after seeing results. Any necessary operational repair needs an append-only amendment and preservation of the interrupted attempt.

Six counterbalanced blocks: five-cold, two-cold, coverage-cold, coverage-warm, two-warm, five-warm. Recreate API/CPU services for each block, isolate per-strategy caches, keep the generator loaded. Cold means empty application cache, not cold OS/GPU weights; generation response caching is disabled. Warm repeats the same cases with that strategy's application cache. CPU field reranking cost is included in end-to-end latency. Query order stays fixed; reverse strategy order on the second pass. This reduces, but cannot remove, thermal/order effects.

Report exact status/typed-field outcomes, supported-answer source coverage, context source completeness, HTTP/rejected-draft failures, prompt tokens, median/p95 latency and paired per-case differences. Separate supported, ambiguous and insufficient-evidence cases. Publish all outcomes; no denominator pruning or post-result tuning. Manual review may explain an exception but must not rewrite frozen labels/scores.

The default remains five unless coverage has no per-case exact-outcome or annotated-support regressions in either pass, preserves all negative outcomes, and reduces median end-to-end latency by at least 20% in both passes. Even passing this small diagnostic gate warrants further independent testing, not a general superiority claim. If the gate fails, retain coverage as an explicit experimental option and document its failures. Completion means an honest comparison and architectural decision, not a required improvement.
