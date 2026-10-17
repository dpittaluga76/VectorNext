# Benchmark v2: protocol 1

**Delegated review amendment, 2026-10-17:** the user instructed the implementation
assistant to perform the remaining candidate screening/family check. The
[v1.7 policy](internal-custody-v1.7.md) and [results](../../docs/reports/t39-internal-review-v1.7.md)
record internal source review of all 60 candidates, their exposure, four confirmed
company overlaps and nine development exclusions. Current primary counts are 92
development and 55 exposed candidates. The 147 primary total is below target; the
independent-review and blind-holdout requirements were not met. Comprehensive
lineage remains uncertified. The older original holdout stays unused.

This amendment permits an honestly labelled internal harness pilot; it does not
fabricate an independent receipt or bypass the old runner's freeze. Final runtime,
typed scorer, coordinate proofs, control scheduling and input hashes still need a
separate committed successor freeze. Keep original-label and exposed-candidate
views separate. No strategy-promotion or generalization claim follows. The original
independent-study rules below remain the requirements for such a future claim.

**Gold activation, 2026-10-17:** [v1.6 policy](gold-review-v1.6.md) activates
case 107's Level A definition under the user's explicit waiver of its two-reviewer
requirement. The [v1.5 policy](gold-review-v1.5.md) remains an immutable predecessor.
Its pre-collision development roster is 101 primary / 3 derived / 16 stress, with no
pending gold decisions. Use the [new gold, family/control rosters and custody packet](../../docs/reports/t39-gold-review-v1.6.md).
That activation did not attest independent review or custody, open sealed data, change
sources/questions or authorize execution without the remaining freeze conditions.

**D7 amendment, 2026-10-17:** [scope and closed-book controls](pilot-scope-v1.4.md)
define a harness/diagnostic pilot: TXT prose QA, **PDF text ingestion (clean render)**
and **structured-table QA (JSON)**. The 17 PDF and 52 TXT primary cases are unpaired;
their score difference cannot estimate ingestion loss. Record excluded PDFs 065/079
as stress defects, not parser failures. The [D7 headline/changelog](../../docs/reports/t39-d7-pilot-scope-v1.4.md)
contains the mandatory exact claim limits. Original publisher layouts, scans,
charts and PDF table extraction are outside this pilot's evidence.

Before retrieval runs, freeze and capture one question-only control for every final
primary item per evaluated model. Report all primary items and a view excluding
positive closed-book gold matches, retaining negatives and reporting unknown
controls. Follow D7's strict per-case matching, common-mask comparison, family
interval and private custodian rules. These controls are extra diagnostics, not
production answers or evidence of proven memorization. Runtime integration and
actual captures remain pending. NASA/USGS retains separate historical n=28/n=16
scored views with original gold. A separately frozen original-layout probe of at
most 20 items is triggered only if a decision needs real-document performance;
no extension is selected now. D1–D7 together govern the successor; older protocol
wording below is retained as the original design, not an override of amendments.

**Review amendment, 2026-10-16:** the successor development candidate uses the
[D3 tiers](tiers-v1.1.md), [D4 format/scale contract](typed-facts-v1.1.md) and
[D5 table/metric amendment](table-context-v1.2.md). D5 changes primary success to
typed value/format correctness and reports grounding/joint correctness separately;
the original protocol-1 definition below is retained for traceability. D5 also
predeclares corrected table context as primary and v1 as an ablation. No execution
freeze has been approved. Original packaged protocol bytes remain unchanged.

**D6 amendment, 2026-10-17:** [company/article/paper families](families-v1.3.md)
replace provisional table/report identities. Trace all primary cases and all
exposed development sources with confidence tiers; use family-resampled intervals.
The [custodian protocol](../../docs/reviews/t39-d6-custodian-handoff-v1.3.md) applies
identical D3-D5 source screening to sealed cases and returns only aggregate counts
and colliding development keys, without sealed identifiers/content/per-item hashes.
Collision exclusions affect development families; unknowns remain uncertified.
Freeze reserve strata/seed before a development-only draw, or report shortfalls.
The final gold/scorer/adapter/annotation/family/split commit follows actual
reconciliation and quota checks, not this intermediate review. The older sealed
manifest and record instructions below do not authorize disclosing per-item sealed
hashes or bypassing D6. No final execution approval exists.

Declared before new benchmark inference. This is a new evaluation, not a rerun or amendment of historical freezes. NuExtract-only is the current user-selected mode; it is not a promotion claim. Ranked 30/20/5 stays the default unless this protocol supports a change.

## Corpus and custody

Target 180 questions; accept 150–300 after independent review, with 25–30% unanswerable or ambiguous. At least 30% of questions and entire document/source families are sealed. Split before running models; all derivatives of a source stay together. Require at least 20 families in each split. Keep TXT, PDF and JSON represented, with at least 20 cases per format. Tables are a content-structure tag, not a fourth file format; require at least 20 table cases. Record per-format, per-structure and per-source-family counts. Explicitly separate direct extraction from unsupported arithmetic, aggregation, comparison and visual reasoning; stress cases do not enter the primary denominator.

Use unchanged public human questions/annotations from SQuAD 2.0, QASPER and TAT-QA where compatible. A source label is not automatically a valid VectorNext label: review document scope, all acceptable typed values, answerability, evidence spans/pointers, unit/scale, and field definitions. Do not manufacture missing-evidence cases by silently dropping human-annotated evidence. TAT-QA arithmetic and QASPER free-form synthesis need a separate stress track. Retained NASA/USGS questions are continuity results, not new independent evidence; fresh adaptations need independent review. Do not inspect or reuse the original repository holdout.

Preserve dataset version, source URL, terms, source bytes and hashes. Keep acquired label archives outside Git. Never commit unseen labels to the development checkout. A reviewer outside the implementation loop approves the adaptation, resolves disagreements against the original and holds the sealed package. The implementation agent may prepare tools and development candidates, but cannot sign its own review. Public human labels are independent authorship, not evidence that a pretrained model never saw the data.

The reviewer supplies `review.json` identifying reviewer/custodian, source references, exact manifest hash, per-case acceptance and exclusions, capability decisions, source-family split and review date. A sealed manifest exposes only file hashes, counts and custody identity. Hashes establish integrity, not secrecy or proof of independence. The custodian releases sealed requests only after development selection is frozen, scores captured outputs without revealing labels to the implementation loop, and returns the aggregate and paired-case report. Corrections after freezing require a separately versioned amendment and retain original results; no outcome-driven exclusions.

## Execution freeze

Freeze code tree (including uncommitted source bytes), image IDs, model/profile/artifact identities, encoder/reranker identities, protocol, adapters, scorers, corpus, labels and public requests before inference. The run refuses mismatches. Ingest each source once into fresh isolated storage with structural context; all arms share the same committed revisions/chunks/vectors. Failed ingestion remains in every applicable denominator. Never mount normal-library storage in the experiment.

Compare ranked five (30/20/5), ranked two (30/20/2), and `facet_coverage_v1` with its existing 30/20/5 settings. No prompt, model, token-budget, temperature, schema or retrieval tuning. Original questions remain unchanged; automatic planning is primary. Explicit gold field definitions belong only to the separately reported oracle-field ablation. Optional prose is off. Scope is the annotated document set.

One measured attempt per case/arm, sequential, NuExtract-only. Rotate arm order deterministically by source-family hash; retain fixed question order within families. Keep cache policy identical and record actual cache observations; this is resident-model operation, not cold-start or concurrent-load benchmarking. Warm the model once using a separate synthetic request; exclude warmup/loading from request latency but report loading separately. Bind durable request IDs to freeze/case/arm. Reconcile existing jobs after interruption; never resubmit an uncertain/failed measured question into a new success. Preserve failures and timing gaps. No quality score may be inferred from synthetic verification fixtures.

First run development cases, choose at most one candidate strategy, freeze that choice, then have the custodian run/score only that candidate and ranked-five on the sealed split. No holdout-driven prompt, label or strategy changes. Run oracle ablations after measured strategy requests, using only development cases; sealed ablations require a separate later approval and retire their sealed status.

## Outcomes and gate

Primary success is source-supported exact factual correctness, or the correct annotated negative category. Report answer values, evidence support and mechanical validation separately. System errors, missing captures and ingestion failures remain primary failures. Harmful answers are supported-but-incorrect answers, including supported answers to negative cases. Report answered-correct/wrong, abstained-correct/missed/wrong, errors and unscorable cases; rejected-gold drafts remain diagnostic until an independent proof review establishes a false rejection.

Predeclare a **5 percentage-point non-inferiority margin** on primary success and a **2 percentage-point maximum harmful-answer increase**. Also require a one-sided 95% Wilson upper bound of at most **10%** on the candidate's absolute harmful-answer rate. These are decision thresholds, not product guarantees. Evaluate the one selected candidate versus ranked-five on sealed cases; development comparisons cannot promote a default.

Use paired question differences with 10,000 source-family bootstrap resamples (seed 3905), preserving all questions of each sampled family and weighting the point estimate by questions. Report two-sided 95% descriptive intervals and one-sided 95% gate bounds. Require at least 20 families per evaluated split. Bootstrap intervals from a small/degenerate sample do not establish equivalence; require the prospective adequacy condition below as well. Wilson outcome intervals are descriptive and do not replace clustered paired comparisons.

For a latency-motivated change, require at least 10% lower median end-to-end latency both across all planned requests and across requests successful in both arms; report p95, stages, tokens and failures. A missing latency or failed paired denominator cannot help this gate. If multiple development candidates qualify descriptively, choose higher primary success, then lower harmful-answer rate, then lower paired-success median, then ranked-two as a deterministic final tie-break. If neither qualifies, retain ranked-five and report the result without opening the sealed labels unnecessarily.

Prospective adequacy assumes 15% paired discordance, a design effect of 1.4 for source-family clustering, one-sided alpha .05 and power .80 at zero true difference. The approximation `(1.644854 + 0.841621)^2 * .15 * 1.4 / .05^2` requires **520 sealed questions** for the primary margin alone. The bounded 150–300-question study therefore cannot establish the desired non-inferiority with this planning assumption. It is a measurement/diagnostic pilot: **retain ranked-five; a formal promotion is inconclusive**. Report observed intervals without claiming absence of regressions proves equivalence. A larger independently frozen study is a separate decision, not an automatic expansion of T39. Harmful-answer gates may require still more data.

## Oracle evidence and validator comparison

For every development case, preserve the baseline plan, candidates, selected evidence, assessment and extraction when available. Run gold evidence with the captured automatic fields, then (where different or planning failed) gold evidence with independently approved gold fields, separately for NuExtract and Gemma. Run one GPU model at a time under the supervisor lease. Do not feed gold values as requested fields or rejected answers as evidence. Use the normal 3,328-token evidence budget and two-call operation; too-large gold evidence is an explicit oracle-budget failure, not truncation. The reviewer specifies minimal sufficient gold passages before results.

For each captured candidate, materialize JSON values in Rust exactly once. Compare the same materialized candidate with mechanical validation enabled and with its result observed but not enforced. Disabled validation output is an untrusted diagnostic, never an application answer. Missing/invalid JSON pointers cannot be scored as values. Retain source-null handling separately from generic validator rejection. Independent semantic/proof review distinguishes a validator false rejection from a gold-valued candidate with bad proof, and a false acceptance from semantically wrong but mechanically supported selection.

Attribute observations to ingestion, planning, candidate retrieval, final selection, assessment, extraction, mechanical validation and infrastructure; allow multiple/unknown causes. Recovery under an oracle intervention is evidence of sensitivity, not proof of a unique root cause. Publish case-level flags and numerator/denominator for each attribution.

## Residue audit

Use real ingestion lifecycle with a synthetic CPU encoder in isolated Linux storage. Inventory paths, sizes and SHA-256 after initial ingest, replacement, removal and compaction. Verify both original byte streams, unchanged historical jobs, retry receipt equality/conflicting-ID rejection, no searchable document after removal, and retained revision reservations. Include a deliberately unreferenced blob to establish the GC contrast. Explain that `preserve-history-v1` keeps historical originals and receipts, while obsolete journal payloads and unreferenced blobs can be reclaimed. Answer-job/browser evidence and external backups are separate retention domains. This audit needs no GPU or user data.
