# T24 final passage selection protocol

Defined 2026-10-15 before measured retrieval. This agent-authored experiment follows T23's shortlist recovery result; it is not independently adjudicated and does not test answer generation.

## Inputs and freeze

Ten fresh NASA planetary/Sun/Moon facts pages, attributed and transformed to TXT, are in `evals/selection/fixtures`. Freeze source hashes/URLs, public questions and answer-free facets, separate original-text labels and this protocol before ingestion. Twenty positive questions (ten single-topic, ten multi-part) require 37 facts across questions; 22 distinct facts are reused. Four missing-evidence questions refer explicitly to fictional, absent measurements/objects. Repeated facts make questions correlated. Labels include known alternate statements and all occurrences of their literal quotes; source offsets are UTF-8 bytes. Do not rewrite labels, sources or parameters after seeing retrieval outcomes. Freeze runtime code/image/model identities separately before execution. No T11/T14/T23 or original holdout input is used for new inference or scoring.

## Controlled comparison

Both arms use the original question plus its one-to-four frozen facets for candidate retrieval. Each probe uses the current exact dense/BM25 30/30 branches, fusion/deduplication and top-20 limit. Round-robin unique keys across original/facet lists, starting with the original, produces at most 20 reranker inputs. Preserve the same corpus, explicit all-document scope, exact source revisions, MiniLM embeddings, cross-encoder, structural context and 180-token ingestion target. Original question reranks all candidates in both arms. Verify identical raw and selected candidate keys per question across all arms/passes.

- **ranked** takes the first five by original-question reranker score, with ascending full ChunkKey ties (T23 expanded selection).
- **facets** reranks the same candidate passages for each facet alone, without appending the full question. At most four additional batches of 20 pairs are permitted, for a maximum 100 pair evaluations including the general ranking. Visit facets in their public request order. Choose the highest-ranked eligible passage per facet; if its exact key is already selected, record reuse rather than consuming another slot. Skip heading-only passages and passages with substantial span overlap with an existing selection. Then fill remaining slots from the general ranking under the same eligibility/overlap checks. Stop at five; never relax exclusions merely to pad the result.

Substantial overlap means common original non-heading block-span bytes are at least 80% of the smaller passage's total non-heading span bytes, within the same document AND revision. Merge overlapping/adjacent ranges before measuring; ancestor headings do not contribute. Never suppress across documents/revisions, infer contradictory evidence from similarity, or apply a relevance-score threshold as a claim of answerability. Non-finite scores, invalid lengths/budgets or more than four facets fail explicitly. Record all general/facet scores, pair tokens, eligibility/overlap decisions and selection reasons. This is bounded heuristic coverage, not semantic proof.

No API/production selector change, no generated annotations, no neighboring-passage assembly, no PDF/JSON processing or LLM answers. The tested object is a set of primary passages, not the final context or answer.

## Measurement

Fresh Docker database/cache volumes; pinned local model files read-only; networking/GPU disabled, 2 CPUs and 4 GiB per process. Separate synthetic fixture smoke first. Ingest all sources once with failed admissions retained. Run ranked/facets/facets/ranked in fresh processes and separate per-arm caches. First passes start with empty application caches; later passes reuse them. These are not cold OS/model-file cache measurements; shared-host variation is a limitation.

Score original chunk bodies against revision-bound frozen quotes after whitespace normalization, separately for raw candidates, fixed shortlist and final primaries. Macro fact recall and complete positive-question coverage include all failed/missing positive responses as zero. Negative recall is undefined; report hit/error counts without calling retrieval abstention. Literal matching is conservative and can miss valid unenumerated/split support; record post-run exceptions separately without changing scores. Report paired per-question gains/losses, single/multi groups, admitted sources/chunks, repeated-key/score consistency, primary counts, extra pair/inference counts, query embedding/search/general-rerank/facet-rerank/selection/end-to-end median/p95 latency and result-cache effects. Startup, index building and capture serialization are separate from query timing.

Complete the investigation even if results are neutral or worse. Keep production ranked 30/20/5 and coverage_v1 unchanged. Any later promotion needs a separate decision and fresh validation; the observed corpus becomes regression data. Preserve original captures, code/input freezes and all historical artifacts.
