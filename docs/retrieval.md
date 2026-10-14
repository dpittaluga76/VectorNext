# T04 retrieval contract

Status: implemented and verified in T04. Design reference: [architecture.md](architecture.md), sections 3, 4, 6, and 7. Verification results are in the [build plan](plan.md) and [diagnostic report](reports/t04-retrieval.md).

## Snapshot and space boundary

`SearchIndex::build` owns an immutable `ReadSnapshot` and one explicit embedding-space ID. It builds our own in-memory keyword postings and dense row references from that snapshot's published chunks in that space. No model runs and no vector data is copied or changed. An index never refreshes itself: build another index from the new snapshot after commits. Old readers keep old results; new indexes exclude replaced/deleted revisions. Recovery rebuilds these disposable indexes from persisted records, without changing storage format 1. Incremental indexing and ANN are deferred until measured need.

Every hit is identified by document ID, revision, and chunk ID. A query vector carries its space ID and must exactly match the index; equal dimensions alone are insufficient. Keyword-only search is also scoped to the selected space, so hybrid candidate sets have the same corpus. Exact cosine uses float64 accumulation over stored float32 vectors and actual norms, including spaces declaring no normalization. Zero/nonfinite/mismatched queries fail. Similarities are clamped to [-1,1] for roundoff; negative and zero scores remain valid candidates. Ties always use the full ascending hit key.

## Keyword index

Evidence, structural context, and generated context have separate postings, lengths, document frequencies, and scores. One chunk is a BM25 document. Tokenizer `nfkd-lower-alnum-v1` decomposes Unicode, removes combining marks, lowercases, and splits on non-alphanumeric characters. Thus Pelé/Pele match, without altering evidence. No stemming, stop words, synonyms, phrase matching, or language-specific segmentation is implied. Query terms are unique, so repeated words do not multiply scores.

For each field, score unique query terms with `idf = ln(1 + (N - df + 0.5)/(df + 0.5))` and `idf * tf*(k1+1)/(tf + k1*(1-b + b*length/average_length))`. `N`, frequencies, and average lengths cover all chunks in this snapshot/space, including empty fields, before filters. Empty fields contribute zero. Defaults: k1=1.2, b=0.75, evidence weight=1, structural weight=1, generated weight=0. Generated text is searchable only when its weight is explicitly enabled; it never becomes independent evidence. Each returned keyword hit explains field/term contributions. Parameters and tokenizer identity are returned with results. These defaults are hypotheses, not tuned quality claims.

The formula uses the positive-IDF BM25 variant. Background: [BM25](https://nlp.stanford.edu/IR-book/html/htmledition/okapi-bm25-a-non-binary-model-1.html).

## Explicit typed filters

Filters are supplied by the caller, not inferred from a question. Document IDs/media types and Boolean all/any/not can combine attribute predicates. Attribute keys are literal; an optional RFC 6901 pointer selects a nested value. `match.year` and `publication.year` are distinct keys. Values never coerce between strings, numbers, booleans, and null. Numeric equality/ranges compare exact decimal magnitudes (including very large integers, exponents, and negative zero), without float conversion. Arrays/objects compare recursively, with numeric equality at leaves. Numeric ranges support inclusive/exclusive bounds and reject reversed/empty bounds.

Missing and explicit null differ. Exists/missing test path presence; equality against a missing path and numeric ranges against missing/non-numeric values are unknown. Negation preserves unknown, preventing an absent value from accidentally matching a negated range. All/any use three-valued logic; only true passes. Empty all is true; empty any is false. Filters are bounded to 32 levels and 1,024 nodes.

Attributes derived from source or deterministic processing are eligible by default. Generated attributes are unknown unless the caller explicitly selects `Any` trust. The trace counts unknown exclusions; no automatic uncertain-attribute filter is created. Filters apply before branch top-k selection. BM25 corpus statistics do not change with filters; this is not a tenant/security isolation boundary.

## Fusion, deduplication, and inspection

Each enabled branch selects its own top-k after filtering. Weighted reciprocal rank fusion scores their union as `dense_weight/(rrf_k+dense_rank) + keyword_weight/(rrf_k+keyword_rank)` for branches containing a hit, using one-based ranks; default rrf_k=60. A chunk present in both branches appears once. Raw cosine and BM25 scales are never added together. Zero-weight/zero-budget branches are disabled. Parameters must be finite, nonnegative where applicable, and bounded; rrf_k must be positive. Background: [RRF paper](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf).

Conservative evidence deduplication then keeps the highest-ranked representative only when document/revision, evidence, representation, source references, block spans, structural context, and attributed values/provenance are identical. Generated-context differences alone do not create new evidence. Suppressed keys remain in the trace. Never collapse across documents or different source locations, and never sum duplicate chunk scores to increase rank. Partial overlap stays intact for later context assembly. Deduplication occurs after branch budgets; duplicate-heavy pools can still reduce unique coverage, which the evaluation records.

Return dense rankings, keyword rankings with explanations, the full fused union, deduplicated candidates, final top results, and suppression mappings. Optional eligibility tracing identifies true/false/unknown filter outcomes. `resolve` returns the original stored chunk and document from this index's snapshot. Stable ranking lets evaluations explain where a source enters or leaves each stage.

T04 tests compare exact search to an independently normalized reference and BM25/RRF to small hand-calculated cases. A deterministic supplied-vector evaluation records source-location coverage across stages, including losses at branch/final limits and filters. It is an algorithm diagnostic on prepared synthetic records; it does not measure embedding quality, parsing, OCR, reranking, or answers. T01 holdout questions stay untouched.
