# Development tiers and exclusion policy v1.1

Declared **2026-10-16, before any T39 benchmark inference**, following Daniel's D3 decisions. This supplements the unchanged [answerability](answerability-v1.1.md) and [numeric](numeric-scoring-v1.1.md) policies. Preserve original questions, original public labels and previous D1/D2 snapshots. The three views below supersede the earlier suggestion to mix comparison questions into a generic stress track.

## One primary reason per item

Each excluded item has exactly one `primary_reason`; secondary tags retain other problems without double-counting its exclusion. Apply the following rules to the question and complete supplied source, never to a model output:

| Primary reason | Exclusion rule (one sentence) | View |
| --- | --- | --- |
| `source_content_unavailable` | Exclude from primary when required source content is unavailable in the supplied package, recording whether it was absent upstream, omitted by adaptation, lost by application parsing, or remains unverified. | Stress/adjudication |
| `question_incomplete` | Exclude from primary when the question omits a necessary referent or requested relation that cannot be uniquely supplied from its unchanged context. | Stress/adjudication |
| `premise_or_entity_ambiguous` | Exclude from primary when answering requires a contested entity mapping, category substitution, or promotion of a qualified source hypothesis into an asserted premise. | Stress/adjudication |
| `unit_or_format_ambiguous` | Exclude from primary when the source and question do not determine the unit, scale or interpretation needed to compare an answer, without guessing a conversion or correcting a suspected typo. | Stress/adjudication |
| `scope_or_period_ambiguous` | Exclude from primary when multiple source-backed populations, components, geographic scopes or periods fit the question, or when the requested period cannot be bound to the source's convention. | Stress/adjudication |
| `requires_derivation` | Move an otherwise source-supported comparison, logical entailment or nonliteral attributed paraphrase into derived/inference when the requested conclusion is not directly stated. | Derived/inference; a skill distinction, not an annotation defect |

For overlapping defects, apply the order in this table: missing required content, incomplete question, contested premise/entity, unit/format, scope/period, then derivation. Record all applicable secondary tags. Do not use derivation to excuse missing evidence. A clean unanswerable question remains eligible for the primary set: absence of the requested fact is not by itself a damaged source or malformed question.

No case is resolved by choosing the reading a model happened to produce. A pre-run resolution needs a recorded source-grounded rule, evidence, reviewer decision and new amendment. After measured outputs exist, report any correction as a separate version and score the original alongside it; do not retroactively change a run's membership.

## Three views and the original baseline

- **Primary — direct extraction and clean negatives:** report the outcome matrix and exact/source-supported correctness. Pending annotation decisions stay visible; provisional membership is not execution approval.
- **Derived/inference:** report supported comparisons, entailments and attributed paraphrases separately, with their required operations and source proofs. A production refusal of an unsupported comparison is a visible capability result; no comparison implementation is added by this policy.
- **Stress/adjudication:** report behaviors, not an accuracy percentage against a single disputed gold value.
- **Original public v1:** retain all 120 original development questions and their unchanged labels as the comparison view, with original counts; no model scores exist for this proposal yet. Historical 16/28-question scores belong to other datasets and remain unchanged.

D1 case **004** is derived/inference (local entailment); **088** is derived/inference (qualified attributed paraphrase); **067** is stress (contested entity/premise). Its original v1 unanswerable label remains intact. Literal D1 cases 074/109 remain primary candidates. This classification does not undo D1's approved meanings or edit its frozen artifact.

The 15 D3 cases divide into 14 stress items and **082** as derived comparison. Together with D1, the development roster is **102 primary candidates, 3 derived/inference, 15 stress**, totaling 120. These are provisional development denominators, not completed evaluations or a classification of the unopened 60 sealed cases. Report per-format, structure, numeric-answer and original-label losses. Recheck whole-benchmark size, family, format and negative quotas only after the remaining reviews and custodian-side classification; do not assume sealed items automatically remain primary.

## Stress behavior rubric

For each case record `yes`, `no`, `not_observable` or `not_applicable`, with the exact captured response as evidence, for:

1. **Recognizes the issue:** names the relevant ambiguous scope/premise, missing referent, uncertain unit or missing content.
2. **States its assumption:** if it answers under one interpretation, explicitly identifies that interpretation before presenting the conditional fact.
3. **Answers under each supported reading:** provides the correct values and proofs for the predeclared readings, where the available evidence supports them; a reading with no source value must be marked unavailable rather than invented.
4. **Avoids unsupported certainty:** does not present a single unqualified value as resolving an ambiguous question, erase a hedge, invent units or fill missing table cells.

Also record clarification/abstention, infrastructure failures and which response surfaces were observable. A generic abstention does not automatically demonstrate recognition of the specific ambiguity. Model-private reasoning is unobservable. Do not treat optional draft prose as a validated factual answer. Keep denominator `n` for each behavior and applicability group; do not combine these dimensions into a quality score or reward a confident unsupported guess. The current application may not express all conditional responses: report that limitation without adding fields, prompts or an LLM judge during measurement.

For **064**, source-supported conditional facts are **0.6 years for the year ended January 31, 2020**, and **0.8 years for the year ended February 1, 2019**; the supplied VMware source does not establish that the first column is called fiscal 2019, so do not import a retailer convention.

For **092**, the conditional facts are **98,725 tonnes CO2e for FY18 UK & Ireland**, and **143,354 tonnes CO2e for FY18 full Group including the US**; cite the gross-emissions row, year headers and geographic footnotes, not the equal-valued net-emissions row.

For **015**, retain the literal `0.3` with its unit uncertainty; do not invent a ratio, percent, percentage-point interpretation or typographical repair. For **111**, distinguish message blocks/packets from store-and-forward delivery and request the missing relation rather than picking one fact as uniquely requested.

## Source-loss diagnosis and repair

Compare retained raw public source records, adapter output and (when run) application-extracted text as separate boundaries. Original publisher image/PDF contents are not established merely by their caption. Mark referenced but unacquired image payloads as an acquisition limitation, not proof that a paper has no table or that VectorNext's parser dropped it.

For QASPER 017/099 the retained raw records include table image filenames and captions but not cell payloads. Verify all supplied title/abstract/sections/paragraphs/captions survive adaptation. A source acquisition and reviewed transcription could restore cells in a new source version; do not silently regenerate the original fixtures or fabricate negatives by excluding known evidence. Restoring cells does not automatically resolve 017's unspecified ROUGE variant/dataset or 099's requested feature granularity.

For TAT-QA, compare every original cell and paragraph before diagnosing a missing table. Preserved cells with incomplete per-row header propagation are an adapter/context problem (D5), not absent raw content. No application ingestion has run for this proposal, so application-stage loss is not yet measured. Re-entry to primary requires successful source repair and an unambiguous question/label rule frozen before any measured model output.

## Replacement procedure — frozen before any reserve inspection

**Current action: no replacements.** Keep the smaller roster and report its changed composition. No eligible, provenance-verified reserve registry has been frozen, and no replacement candidate is opened or drawn in this work.

If replacements are later needed, use this procedure without choosing cleaner-looking questions:

1. A custodian creates a hashed reserve registry from a declared pinned public split, excluding every already inspected case and all families assigned to sealed evaluation or the original holdout; unresolved report-family identities are ineligible.
2. Each registry row has a stable case/source/family ID, original public answerability, format, prose/table structure and question type, determined before quality screening. Question types are numeric amount/count, date/period, entity/location, definition/category, reason/mechanism and other; no quality or model-performance field is allowed in selection.
3. Match a replacement to the excluded item's **original** answerable/unanswerable class, format, structure and question type; also retain source-dataset matching so a hard scientific question is not replaced by an easier unrelated source class. Do not relax an empty stratum.
4. Freeze the registry hash, stratum assignments and seed **`t39-d3-reserve-20261016-v1`** before showing any candidate source/question to the implementation review. The draw is a deterministic seeded permutation: sort eligible rows by SHA-256 of UTF-8 `seed + "\n" + stratum_id + "\n" + case_id`; break hash ties by case ID. Define `stratum_id` as compact JSON of `[source, original_answerability, format, structure, question_type]` in that order.
5. Process excluded case IDs in lexicographic order, taking the next unused ranked candidate in its stratum; apply the same complete defect checklist, record every draw, rejection and reason, and move only to the next candidate when that checklist excludes it. Do not choose among candidates based on perceived ease.
6. Keep the original source-family split binding, include source/label provenance, and freeze all final memberships/proofs before inference. If the pool is missing, exhausted or cannot meet a stratum, retain the smaller primary set and disclose the deficit. Quota failures prevent a compliant execution freeze; do not conceal them with handpicked additions.

The seed is not a quality guarantee, and public labels do not prove absence of model pretraining exposure. No sampler has run and no reserve membership is approved by this document.

## Review provenance and twins

Daniel explicitly waived the requested two-reviewer D3 blind screening pass in chat on 2026-10-16 (“let's skip that”). Preserve that waiver: this is internal, non-blind review informed by prior source/label inspection, with **no T39 benchmark model outputs**. Do not sign an independent-review attestation or imply that a blind pass occurred. The waiver does not itself transfer sealed custody, approve remaining D4–D7 mappings, or settle the separately requested 107 gold-replacement reviews.

Disambiguated twins are permitted only as newly versioned IDs with original-parent links, source-grounded wording and separate reporting; they must stay in the same source family and never inflate the independent sample count. No twins are created or added to the current denominators. Potential twins for 064 can name an exact year-end date; 092 can name a geographic scope. Freeze any such subset before model outputs.
