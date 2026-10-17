# T39 review — decisions for Daniel

Prepared for **Daniel Pittaluga / Architect**, 2026-10-16.

The initial review screened all **120 development questions** against supplied
sources/public human annotations: 95 had no case-specific concern and 25 raised
review decisions. Those decisions have since been resolved. The subsequent
[user-delegated v1.7 review](../reports/t39-internal-review-v1.7.md) also screened all
60 proposed sealed candidates; they are now exposed to the implementation assistant.

**D1-D7 and all six gold decisions are applied.** Case 107's two-reviewer condition
was waived explicitly; v1.6 activates Level A. The four remaining primary source
identities are now established, and v1.7 records candidate screening and confirmed
company collisions. No independent-review attestation is claimed. There is no
outstanding gold-decision question or request for a user-provided custody receipt.
Broader lineage and final runtime/execution integration remain limitations/work.

This is my internal review, not a claim of independent approval. Your answers resolve the listed development decisions; they do not attest that unseen labels were reviewed or that sealed custody has been transferred. The original proposal remains unchanged.

## D1 — Recorded: four qualified amendments, one ambiguous case

Daniel rejected a batch approval and supplied individual decisions on 2026-10-16. The subsequent checks used the exact scoped source documents. [v1.1 decisions, evidence and changelog](../reports/t39-d1-adjudication-v1.1.md) · [Exact offsets and aliases](../reports/t39-d1-adjudication-v1.1.json).

| Case | Recorded action | Source check / scoring rule |
| --- | --- | --- |
| 109 | Approve | Connection-time charging is explicit. |
| 074 | Approve after feature-set check | TF-IDF is the classifier representation; joined bigrams are preprocessing. LDA is for the separate visualization task. |
| 088 | Approve with attribution rule | Richard Lindzen criticizes understated uncertainty. This is a qualified attributed paraphrase, not a verbatim statement or a scientific truth claim. Houghton is not attributed the same claim. |
| 004 | Approve as inference-required | MSP is the gold span; the eligibility alternatives entail non-exclusive UK citizenship. Report separately from literal extraction. |
| 067 | Ambiguous; do not flip to answerable | Keep the original unanswerable label in the public/strict view; exclude from reviewed binary scoring. A lenient Warsaw interpretation is only a separate diagnostic. |

**Recorded answer:** Daniel's revised case-by-case recommendation; conditions checked against source text. Original labels remain unchanged. The v1.1 amendment records these decisions separately and does not approve the entire benchmark. Literal-extraction and inference/attribution-allowed results must be reported separately.

The original internal review covered both label directions before any model run. It and Daniel's later adjudication are not two independent blinded reviews. The original annotators' reasons remain unknown. Full-document answerability and eventual retrieved-context sufficiency will be scored separately.

## D2 — Recorded: alternatives corrected; Level A activated under user waiver

Daniel approved all five directions with precision, allegation and review conditions on 2026-10-16. [v1.1 changelog and source excerpts](../reports/t39-d2-adjudication-v1.1.md) · [Offsets and decisions](../reports/t39-d2-adjudication-v1.1.json) · [Systematic audit](../reports/t39-d2-alternative-audit-v1.1.md).

| Case | Recorded action | Source condition / scoring rule |
| --- | --- | --- |
| 031 | Remove the reversed alternative | The source lists production/distribution/price disruptions as causes and reduced productivity as an effect. The question asks for one cause; do not narrow the full cause set. |
| 072 | Replace clipped/underqualified alternatives with a complete span | Include allegedly, Lebanon, New Hampshire city councilors and the threat wording. Exact offsets recorded. |
| 081 | Remove bare 20,000; add three tiers | Same described Blogger dataset, no separate dated snapshot stated. Faithful 22,880; qualified over 20,000 imprecise only; bare 20,000 wrong. |
| 097 | Preserve directed approximation | Regional upper extent, not average or individual peak. Almost/nearly/just under is faithful; about is imprecise only; bare 2,000 m wrong. |
| 107 | Activate Level A under explicit reviewer waiver | Authors' own general definition; Level B/C are narrower. Source-only finite alternatives and exact proof spans are active in v1.6. No semantic-judge primary credit. |

The [numeric policy](../../evals/measurement/numeric-scoring-v1.1.md) is bound to all **51 numeric development cases** (49 with numeric literals, two with spelled-out numbers). Imprecise answers are reported separately with no full or fractional primary credit. D4 type/format rules are recorded below; final D5 context/proof integration remains pending. The scanner covered all **111 original accepted alternatives**, plus manual checks of the **12 D1 aliases**. It does not approve the benchmark or change application validation.

D1 answerability changes and D2 tightening/replacement effects have separate scoring views. The unchanged v1 labels are preserved; no benchmark captures exist to score yet. The [five-case review freeze](../reports/t39-d2-review-freeze-v1.1.json) fixes this correction list before inference. New leads are not automatically applied.

**Current D2 follow-up:** the user accepted the six recommendations after seeing exact passages. The [v1.5 amendment](../reports/t39-gold-review-v1.5.md) applies 010/034/047/053 and moves 071 to stress. The user later waived the two-reviewer condition; [v1.6](../reports/t39-gold-review-v1.6.md) activates case 107's Level A definition. The original review packets stay frozen. The later delegated v1.7 review exposed all 60 candidate cases.

## D3 — Recorded: typed exclusions, separate derived tier, no replacements

Daniel approved separation with a dated taxonomy, source-loss checks, predeclared replacement procedure and three score views. He subsequently waived the requested two-reviewer blind screening pass (“let's skip that”). This remains internal, non-blind review. [Source excerpts, per-item findings and denominators](../reports/t39-d3-tiers-v1.1.md) · [Exclusion and reserve policy](../../evals/measurement/tiers-v1.1.md).

| Primary reason | D3 cases | Handling |
| --- | --- | --- |
| Scope/period ambiguity | 011, 046, 062, 064, 065, 092 | Stress; conditional scope-specific facts |
| Unit/format ambiguity | 015 | Stress; never convert bare 0.3 into 30% |
| Incomplete question / unbound referent | 073, 111 | Stress; identify missing referent/relation |
| Required source content unavailable | 017, 099 | Stress; referenced table images were not acquired, while all supplied text/captions survived adaptation |
| Premise/entity/category ambiguity | 076, 079, 110 | Stress; do not silently substitute a category, assert a hypothesis or conflate part and whole |
| Supported comparison | 082 | Derived; GBP has the highest common-currency exchange rate in both listed years |

D1 follows the same taxonomy: 004 and 088 are derived/inference; 067 is stress. The provisional **development** views are **102 primary (76 answerable, 26 negative), 3 derived/inference, 15 stress**, with original v1 **n=120** kept separately. No scores exist yet. Stress reports recognition, stated assumptions, conditional supported answers and unsupported certainty separately, without single-gold accuracy. No replacements or disambiguated twins were created.

All 19 development QASPER documents and 32 TAT-QA documents were checked against retained raw supplied text/cells, and all 62 SQuAD question contexts matched their source. The 017/099 table cells are absent from the retained raw package, not lost by this TXT adapter; the original image payloads remain uninspected. D5’s per-row context problem remains separate. For 064, cite the actual year-end dates; the supplied VMware source does not establish a fiscal-2019 name for January 2020.

**Remaining after subsequent D7 recording:** custodian reconciliation, final source-family/typed-proof approval and custodian-side sealed checks. The waiver does not claim independent validation or change sealed custody. No model output was used to select these exclusions. [Frozen D3 review artifacts](../reports/t39-d3-review-freeze-v1.1.json).

## D4 — Recorded: format contract, typed facts and source proofs

Daniel approved the direction with per-case scale/format rules, a frozen output instruction, minimal normalization, collision checks and separate sensitivity review on 2026-10-16. [Implementation, findings and limitations](../reports/t39-d4-typed-facts-v1.1.md) · [Scoring contract](../../evals/measurement/typed-facts-v1.1.md).

D4 originally required the source string and correct source proof jointly; D5 below supersedes that primary definition while preserving the frozen D4 scorer. Exact scale conversions are derived-only; approximate conversions are diagnostics. NFC and whitespace are the entire global floor. All other aliases, field mappings and two-code separators/order rules are explicit per-case lists. Unlisted answers fail primary and enter a separate human-review queue. The oracle gets names/types/locations, no gold values; only identical-evidence comparisons measure field-planning cost.

The integrated candidate applies D1–D3 and preserves the 102/3/15 roster, six unresolved gold decisions and original v1. All 37 table cases were checked: three equal-value wrong-cell traps are excluded from accepted proofs. The scorer's synthetic tests pass; no inference occurred. Pure prompt/oracle helpers still require evaluation-runtime integration. Final source context/families, mappings and remaining decisions must precede the single execution freeze.

**Recorded answer:** approved with amendments, implemented as a hash-bound review candidate; not final benchmark approval. [Candidate gold and lists](../reports/t39-d4-gold-candidate-v1.1.json) · [Collision audit](../reports/t39-d4-collision-audit-v1.1.json).

## D5 — Recorded: annotated context, separate coordinate proofs

The adapter repeats only the first table row as `headers`. In several tables, the actual years, units or group headings are in later rows. For example, case **012** repeats the title “2.1 Office Buildings” while the years are in row 2. All rows remain in the document, but a retrieved value row can lack the context needed to choose the right year.

Three cases also have duplicate matching values under different meanings. I identified the relevant cells: **002** needs the opening balance, not the previous closing balance; **080** needs basic EPS, not diluted EPS; **092** must not cite net emissions as proof of gross emissions, even when their values match.

**Recorded answer:** approved with amendments on 2026-10-16. Structural interpretation itself can be wrong: explicit source-only annotations now cover all 32 tables, with caption/header/group classifications, finite scopes, span tags and cell/row/column unit scopes. No heuristic chooses headers or inherits units. Original cells and narratives are preserved; the structured sidecar keeps original strings and references, and a fixed renderer joins them only for presentation.

Header repair and coordinate proof identity are separate. Typed value/format correctness is primary; grounding and joint correctness are diagnostics, including correct-answer/wrong-evidence. Production validation is unchanged. 002/080 remain primary, 082 derived and 092 stress. No D3 item re-enters primary. Corrected context is predeclared primary and v1 an ablation; report retrieval/complete-proof recall separately because indexed row text changes. Planning still sees the original question/history, not the table context.

**Verification:** 71 measurement tests pass. The all-table scan found 19 multi-header tables, 10 with interior headings and the three equal-value traps. A CPU tokenizer check found nine corrected rows above the 256-token whole-record budget; actual subtree ingestion/retrieval and answer-budget checks remain pending. No inference or sealed access occurred. [D5 report and remaining limits](../reports/t39-d5-table-context-v1.2.md) · [All-table context diff](../reports/t39-d5-table-diff-v1.2.md) · [Dated policy](../../evals/measurement/table-context-v1.2.md).

## D6 — Recorded: company families, all-format tracing and private custodian check

**Recorded answer:** approved with five amendments on 2026-10-17. Financial families span the company/filer across reports and years, with secondary company-year keys and explicit parent/rename rules. Article/paper identities unify TXT/PDF derivatives. Provenance uses A/B established, C candidate and U unknown tiers; missing name matches never prove separation.

All **102 primary cases** now have trace records: **98 established identities in 57 families**, with four candidate-only cases (**030/056/089/090**). The full ledger covers all 120 exposed cases, including derived/stress. The largest primary cluster has five cases. [Trace, per-format counts and limitations](../reports/t39-d6-families-v1.3.md) · [Dated policy](../../evals/measurement/families-v1.3.md).

The [custodian handoff](t39-d6-custodian-handoff-v1.3.md) requires the same D3 defects, D4 scoring records and D5 table/proof screening privately for every sealed candidate. Return only aggregate counts and affected development keys; no sealed identities, content, aliases or per-item hashes. Whole colliding development families move to diagnostics, preserving original tiers; unknown provenance remains uncertified. No sealed items move into development. At the D6 freeze the 60 candidates were unopened. The later v1.7 internal review classified them and removed confirmed collisions; broader lineage remains uncertified.

Reserve size bands, additional matching strata and a new seed are predeclared; no reserve or replacement was selected. Report smaller denominators and coverage losses if a verified development-only reserve cannot fill a stratum. Family-bootstrap and receipt/privacy tests pass as part of **88 measurement tests**. The review candidate is hash-bound, not a final execution freeze. The final freeze follows source decisions, D5, all-format tracing, custodian reconciliation, any deterministic reserve and recomputed quotas.

## D7 — Recorded: narrow pilot, unpaired formats and question-only controls

**Decision (2026-10-17): accepted with amendments.** Use **PDF text ingestion (clean render)** and **structured-table QA (JSON)** in current reporting. The pilot validates the benchmark harness and bounded strategy diagnostics; it cannot support broad PDF or enterprise-document claims. The [D7 report and changelog](../reports/t39-d7-pilot-scope-v1.4.md) repeat the exact limitations and record the [scope/control contract](../../evals/measurement/pilot-scope-v1.4.md).

**Source check:** zero exact or normalized TXT/PDF paragraph pairs and zero repeated questions across all 120 development cases. The 17-versus-52 primary gap is confounded and cannot estimate ingestion loss. PDFs 065 (scope/period) and 079 (premise/entity) are stress exclusions, not parser failures; 19 development PDFs become 17 primary. 69/102 primary cases are clean prose.

**Run-plan amendment:** one closed-book question-only control for every final primary item/model before retrieval runs; freeze instruction/schema and finite per-case matching. Report all/adjusted primary views, keeping negatives and exposing unknown controls. A gold match is not proven memorization; nonmatching is not proof of clean data. The custodian uses the same private controls with aggregate output only. NASA/USGS keeps historical n=28/n=16 scored views with unchanged gold, outside this primary. No fresh extension joins the pilot. If a decision needs real-document performance, separately scope a maximum-20-item original-layout probe with source alignment, rights checks, family/split preservation and its own freeze.

**Verification:** 104 offline measurement tests pass; 116 development members verified. No inference, sealed access, source regeneration or service changes. At the D7 freeze, runtime control integration, six gold decisions and actual custody reconciliation remained pending. The later [v1.5 gold acceptance](../reports/t39-gold-review-v1.5.md) updates those decisions and the roster; execution approval remains pending.

## Accepted six-case follow-up — 2026-10-17

The user's `recommendationa accepted` records acceptance of the six recommendations
shown with exact source passages. Four gold changes and the 071 stress exclusion
are applied in [v1.5](../reports/t39-gold-review-v1.5.md). The user's subsequent
explicit waiver activates 107's Level A definition in [v1.6](../reports/t39-gold-review-v1.6.md). At the v1.6 freeze the
roster was **101 primary, 3 derived, 16 stress**; 75 primary positive and 26 negative.
Original questions/labels and all prior review hashes remain unchanged. Use the
[new custodian packet](../reports/t39-gold-review-v1.6/custodian-input.json), not the
older packet's hash for historical v1.6 reproduction. At that freeze 126 offline measurement tests passed; no answer inference or candidate access had occurred yet.

## Current continuation

The accepted source decisions are preserved in versioned artifacts. Delegated
internal review leaves 92 development and 55 exposed-candidate primary questions,
with derived/stress/collision diagnostics separate. See the [v1.7 receipt and limits](../reports/t39-internal-review-v1.7.md).
The original proposal, historical results and older unused holdout remain intact.
Finish successor/runtime integration and its committed freeze before any measured
requests. NuExtract and ranked-five remain the defaults; review has not changed
the application or run model evaluations.

[Review summary and verification](../reports/t39-development-review.md) · [All 120 case dispositions](../reports/t39-development-review.json) · [Full review/custody procedure](../../evals/measurement/REVIEW.md)
