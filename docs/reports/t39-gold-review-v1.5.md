# Accepted gold recommendations — v1.5 successor

2026-10-17. The user accepted the six source-backed recommendations with
`recommendationa accepted`. This records that adjudication and applies the four
answer changes plus one tier change. Case 107's replacement direction is accepted;
its separately stated two-independent-review activation condition remains open.
This is not an independent-review attestation or execution freeze.

| Case | Applied decision | Status |
| --- | --- | --- |
| 010 | Require Bukhara, Besh Baliq, Almaliq and Samarqand as a complete unordered set; reject partial/duplicate/extra candidates | Applied |
| 034 | Retain always-YES baseline, qualified as batches 2 and 3; reject entailment as an alternative | Applied |
| 047 | Retain specialization/higher confidence; remove method-only sparse attention alternative | Applied |
| 053 | Labels are car models, without model year; replace bare car/the car | Applied |
| 071 | Premise-ambiguous question about a plea agreement; move to stress without rewriting the question or original supported label | Applied |
| 107 | Replace related-work catalogue with the authors' Level A definition, preserving profanity OR targeted offense, including veiled/direct forms | Direction accepted; not activated pending the two reviews |

The [adjudication record](t39-gold-review-v1.5/adjudication.json) contains each exact
question, source hash, verbatim evidence with UTF-8 offsets, and before/after scoring
records. The [policy](../../evals/measurement/gold-review-v1.5.md) specifies finite
aliases/separators, proof requirements and 107's remaining condition. Source bytes,
questions, public annotations and all prior D1–D7 artifacts are unchanged. These
are label/scope changes, not model improvements; preserve original-label scoring.

## Current candidate and denominators

| View / track | Prior D7 | Current successor |
| --- | ---: | ---: |
| Primary | 102 | 101 |
| Derived/inference | 3 | 3 |
| Stress/adjudication | 15 | 16 |
| Primary positive / negative | 76 / 26 | 75 / 26 |
| TXT prose QA | 52 | 51 |
| PDF text ingestion (clean render) | 17 | 17 |
| structured-table QA (JSON) | 33 | 33 |

The current primary roster still includes pending case 107, which the scorer leaves
unscored until its activation condition is satisfied. Its old gold is retained in
the candidate rather than silently activating the proposed replacement. There are
100 currently scorable primary records, not 101 completed/verified evaluations.
No replacements or question twins were selected.

The [new gold](t39-gold-review-v1.5/gold.json) uses the existing D4/D5 scorers. The
[tier overlay](t39-gold-review-v1.5/tiers.json) preserves every original exclusion
and adds 071. All 120 cases remain exposed development sources for family checks.

The [family ledger](t39-gold-review-v1.5/family-ledger.json) now has 97 established
primary identities in 57 families, four candidate identities and largest cluster
five. Primary family-size distribution: 34 singletons, 14 pairs, three triples,
four groups of four and two groups of five. Moving 071 removes one primary item
from its existing Civil Disobedience family; it does not remove that exposed
family or relax the custodian collision check. Sealed separation remains pending.

The [updated control roster](t39-gold-review-v1.5/pilot-audit.json) contains 101
candidate question-only controls per model, with 107 still unresolved. There are
still zero matched TXT/PDF questions/paragraphs. Clean prose accounts for 68/101
(67.3%); 53 primary SQuAD cases, 15 QASPER cases and 33 TAT-QA cases remain. PDF
exclusions 065/079 are unchanged. D7's scope and scoring policies remain in force.

## Custodian handoff and remaining work

Use the **new** [custodian input](t39-gold-review-v1.5/custodian-input.json) and
[blank receipt template](t39-gold-review-v1.5/custodian-receipt-template.json), with
the existing [private procedure](../reviews/t39-d6-custodian-handoff-v1.3.md) and
[D7 aggregate-only control supplement](../../evals/measurement/pilot-scope-v1.4.md#custodian-supplement).
The D6 wire schema is unchanged; content, policy and ledger hashes are new. Old
receipts cannot reconcile against this packet. No actual receipt is claimed or sent.

Once the custodian has completed a separate receipt file, validate it with the
new ledger and packet (the blank template intentionally fails validation):

```powershell
python -m evals.measurement.families check-receipt --ledger docs/reports/t39-gold-review-v1.5/family-ledger.json --handoff docs/reports/t39-gold-review-v1.5/custodian-input.json --receipt PATH_TO_COMPLETED_RECEIPT --output tmp/t39-v1.5-new-reconciliation.json
```

Remaining gates: case 107's independent activation reviews; four candidate primary
family identities (030/056/089/090); actual custodian source screening, collisions
and quota reconciliation; runtime prompt/scorer/native-template/control integration;
actual ingestion/budget checks for nine oversized table rows; final committed
execution freeze. Default models and retrieval settings are unchanged. No inference,
sealed reads, downloads, service changes or commits were performed for this amendment.

## Verification

**117 offline measurement tests pass**, including 13 new checks covering every
accepted string, all destination orders, incomplete/extra sets, qualified baseline,
method-only failures, car-label specificity, stress exclusion, inactive 107,
closed-book matching and custodian hash separation. Value correctness and grounding
remain separate: a full answer with incomplete/wrong proof does not gain joint credit.

Reverified 116 original development members and 90 earlier frozen artifact entries.
All 114 unaffected case records are unchanged; all 120 questions/source hashes and
original labels are unchanged. Updated packet/ledger/gold/control hashes agree.

The [four-role collision scan](t39-gold-review-v1.5/collision-audit.json) found two
additional Samarqand occurrences and nine car-model/model occurrences outside the
approved spans. These are location-review flags, not automatic gold or alternative
proofs. In particular, a generic `model` elsewhere in the paper cannot ground the
car-label answer; value-only scoring still reports grounding separately under D5.
Other cases/tables retain their earlier collision scans. No model outputs informed
these alternatives or flags.

```powershell
python -m evals.measurement.build_gold_review --audit tmp/t39-internal-review/source-audit.json --proposal tmp/t39-v2-review-proposal-v2 --output tmp/t39-gold-review-reproduction
python -m unittest discover -s evals/measurement -t . -p 'test_*.py'
```

The builder requires the retained ignored development proposal, validates prior
hashes and creates only a new output directory. Tests read fixed public review
artifacts and synthetic captures; they never regenerate sources or run models.
[Verification record](t39-gold-review-v1.5/verification.json) ·
[Review artifact hashes](t39-gold-review-v1.5/manifest.json).

## Scope limits, unchanged

Purpose: validate the benchmark harness (scorers, adapters and splits) and provide
bounded source-grounded strategy diagnostics; results are provisional for decisions
about real documents.

- Not evidence of performance on original publisher layouts, scanned pages, charts or PDF tables.
- Not evidence of table-extraction performance, only of reading from supplied structured cells.
- Not generalizable to enterprise or domain documents beyond Wikipedia text, arXiv-style papers and financial-report tables.
- Not a measurement of the NASA/USGS track if that stays separate, and not comparable with it unless you state how.

NASA/USGS retains its separate historical frozen scored views; no fresh extension
or real-layout probe was selected by accepting these gold recommendations.
