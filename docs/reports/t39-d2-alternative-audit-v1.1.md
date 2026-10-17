# Systematic development-alternative audit v1.1

Read-only internal audit, 2026-10-16. [Complete findings, alternatives and numeric bindings](t39-d2-alternative-audit-v1.1.json).

- All **120 development cases** considered: **83 originally supported**, **37 originally unanswerable**. All **111 original accepted alternatives** scanned.
- **21 cases flagged** by mechanical heuristics; every flag was triaged against the source. Short spans alone do not establish an error.
- **49 cases with numeric literals**, plus **046** (“one-layer”) and **071** (“one misdemeanor count”): **51 cases** bound to the common precision policy, including dates and incidental identifiers. All 36 numeric TAT-QA cases preserve JSON string types; GBP-only case 082 is nonnumeric.
- Also reviewed all **12 D1 aliases across its four newly answerable cases**; none adds a numeric-answer case. Ambiguous 067 is not silently given a numeric gold.
- **116 development members** rehashed successfully. The original proposal and initial review JSON remain unchanged. No sealed question, label or document was read, and no model ran.

## Method and limitations

The scanner checks source/own-annotation literal containment, subtoken boundaries, shorter alternatives, likely clipped endings, immediately preceding qualifiers and differing numeric tokens. Every original question and answer alternative was read; flagged source contexts and additional semantic-completeness candidates were inspected. Reuse of the earlier all-case screen does not establish exhaustive or independent gold correctness.

All 111 original alternatives occur literally (after boundary whitespace trimming) in both their scoped text and annotated evidence. That is **not** a semantic pass: 031’s effect and 107’s literature survey still match source text. Many valid extractive spans end inside sentences, so that fact is not an automatic rejection. The “about” flag for 053 is an unrelated preposition, not numeric approximation.

The source-adaptation review still has unresolved tables, scope, aliases and definitions. Scanning only the development split is intentional; a custodian must apply equivalent checks to sealed material without exposing it to this implementation review.

## Flag triage

| Case | Source review |
| --- | --- |
| 003 | Quotation marks only; no semantic correction. |
| 011 | Different quantities (535 samples vs four proportions); already pending D3. |
| 014 | Expanded dataset acronym is a D4 alias decision; no new numeric issue. |
| 032 | January 1979 versus 1979 is date granularity, not a different year. Preserve existing aliases pending D4 granularity mapping. |
| 043 | Both alternatives name both codes. Optional code years must be supported but are not the requested two code names; no numeric-value conflict. |
| 044 | Question asks for one factor. Medication cost is a source-backed factor; shorter answer is not inherently clipped. |
| 045 | Leading article only; no semantic correction. |
| 046 | One-layer describes the encoder, not necessarily the whole model; already pending D3. Spelled-out numeric item added manually. |
| 053 | About is a preposition in unrelated occurrences, not an approximation qualifier. Separate manual label-specificity concern below. |
| 054 | 3,209 reviews is the requested size. 553 cars and 49 manufacturers are additional source-backed facts, not conflicting review counts; D4 still resolves TeX delimiters and quantity roles. |
| 059 | Shorter alternative names a supported mechanism, but the full phrase also says other arrangements. Preserve current alternatives; D4 should freeze whether one mechanism suffices rather than treating prefix matching as proof. |
| 060 | Quotation marks only; no semantic correction. |
| 065 | Leading article is harmless; temporal election-scope concern remains pending D3. |
| 072 | Confirmed D2 clipped/underqualified alternatives; amended complete alleged conduct recorded. |
| 081 | Confirmed D2 exact/lower-bound distinction; three tiers recorded. |
| 093 | Downtown is the source-defined local referent; not an unrelated incomplete entity name. |
| 097 | Confirmed D2 loss of almost; directed approximation rule recorded. |
| 103 | Both retain the full 11–13th-century range; the era is supplied by the same source. No new endpoint correction. |
| 104 | Leading article only; no semantic correction. |
| 111 | Method versus packets and incomplete question; already pending D3. |
| 112 | The shorter phrase retains both fault tolerance and efficiency; both refer to the same routing function. No new correction. |

## Numeric policy coverage

All entries use [numeric-scoring-v1.1](../../evals/measurement/numeric-scoring-v1.1.md). Policy coverage is not approval of unresolved gold facts and does not change production type checking. Faithful / imprecise / wrong will be scored after final mappings; imprecise is diagnostic only, not full or fractional primary credit.

| Case | Quantity / rule | Remaining mapping |
| --- | --- | --- |
| 002 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 011 | Unresolved maximum sample count versus number of proportions (D3). | D3 scope plus D4/D5 mappings |
| 012 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 013 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 015 | Accuracy units/granularity unresolved: 30.3% versus 0.3 on different text units (D3). | D3 scope plus D4/D5 mappings |
| 021 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 022 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 023 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 024 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 025 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 027 | Annual channel carriage fee, GBP 30 million; preserve £30m spelling/scale until D4 mappings. | D4 field/alias mapping |
| 028 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 029 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 030 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 032 | Collapse timing; January 1979 and year-only 1979 are existing aliases, with granularity explicit in D4. | D4 field/alias mapping |
| 034 | Batch 2/3 identifiers qualify the baseline; baseline-phase scope is a new review lead, not an approved change. | new baseline-phase review plus D4 |
| 040 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 041 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 043 | Years qualify code identities; requested facts are both code names, not numeric quantities. | D4 field/alias mapping |
| 046 | One-layer is spelled out; encoder versus full architecture scope remains D3-pending. | D3 scope plus D4/D5 mappings |
| 048 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 049 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 054 | Review count 3,209; optional cars 553/manufacturers 49 must retain separate roles; TeX dollars are not currency. | D4 field/alias mapping |
| 055 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 056 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 057 | Siege year 1097; preserve event and source year. | D4 field/alias mapping |
| 061 | Education movement range 1910–1940; both endpoints required. | D4 field/alias mapping |
| 062 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D3 scope plus D4/D5 mappings |
| 064 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D3 scope plus D4/D5 mappings |
| 069 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 071 | One misdemeanor count is part of the offered plea terms; no jail time is a negative condition, not permission to invent a numeric sentence. Punishment/plea-bargain wording is a pending review lead. | new punishment-premise review plus D4 |
| 080 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 081 | Total Blogger user count: faithful 22,880; imprecise over 20,000; wrong bare 20,000. | D4 field/alias mapping; D2 semantic tier approved |
| 086 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 087 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 089 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 090 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 091 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 092 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D3 scope plus D4/D5 mappings |
| 097 | Regional upper extent almost 2,000 m; preserve direction; about is imprecise only. | D4 field/alias mapping; D2 semantic tier approved |
| 098 | Buddhist membership 168,637 as of the source's most recent census; do not claim a present-day count. | D4 field/alias mapping |
| 103 | Embankment in 11–13th century AD; preserve both endpoints and era context. | D4 field/alias mapping |
| 105 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 108 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 113 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 114 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 115 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 116 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 117 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 119 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |
| 120 | Exact original table cell for the question's quantity/year. Preserve string spelling, currency/percent markers, column units and source scale; no implicit numeric conversion. | D4/D5 typed table proof mapping |

## New manual review leads — no automatic changes

These five additional questions need a scope/completeness decision. They were found before inference, separately from the fixed D2 correction list. Existing v1 gold remains intact. See [the answer spaces and source excerpts](../reviews/t39-additional-alternative-review.md).

| Case | Concern |
| --- | --- |
| 010 | **Answer-set completeness:** The source describes administrators sent to Bukhara and artisans/farmers moved to Besh Baliq, Almaliq and Samarqand. The question does not specify a role or ask for only one location. Decide whether either subset is sufficient or a set is required. |
| 034 | **Baseline phase:** The annotated evidence describes always-YES for batches 2/3 and entailment for batch 4. The question does not specify a batch. Decide which baseline/phase is requested before changing the gold. |
| 047 | **Mechanism completeness:** Sparse attention is the method and specialization/confidence the reported benefit. Decide whether the short method-only alternative adequately answers how interpretability improves or needs the explicit mechanism. |
| 053 | **Label specificity:** The paper says labels identify the car model, ignoring its year. Decide whether bare car is a sufficient categorical label or too underspecified; do not confuse model, manufacturer and individual vehicle. |
| 071 | **Question premise:** A plea bargain is the described agreement and no jail time its offered outcome. The question calls this a type of punishment. Decide whether to retain that colloquial reading or flag the wording. |

## Reproduce

```powershell
python -m unittest evals.measurement.test_audit_labels -v
python -m evals.measurement.audit_labels --audit tmp/t39-internal-review/source-audit.json --proposal tmp/t39-v2-review-proposal-v2 --output tmp/t39-internal-review/d2-new-scan.json
```

Output must be new; the tool refuses to overwrite. Private proposal/source-audit files are needed to rerun this scan; tests use synthetic data and do not need them. The published JSON retains the machine scan plus explicit manual triage/bindings. The scanner reads only validated development member paths; it has no inference or correction operation.

## Verification and review freeze

All **30 Python measurement tests passed**, including six scanner tests. Reverified **116 development members**, **19 D2 evidence/answer spans**, the unchanged D1 amendment/policy and original source/label/request hashes. Diff whitespace checks passed. No inference, service changes or sealed-data reads were performed. [Verification record](t39-d2-verification-v1.1.json) · [Frozen review list and artifact hashes](t39-d2-review-freeze-v1.1.json).

The freeze binds the five D2 directions and their current approval states; it is **not an execution freeze**. Case 107 is still pending, and the five newly surfaced leads remain separate. Subsequent decisions need a new amendment rather than silently altering this snapshot.
