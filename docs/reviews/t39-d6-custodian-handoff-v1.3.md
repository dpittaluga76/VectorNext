# T39 D6: private custodian check

Prepared 2026-10-17 for **Daniel Pittaluga / Architect**. This handoff does not
attest custody transfer or completed review. No sealed material was opened to
prepare it.

Use the [development-family input](t39-d6-custodian-input-v1.3.json) and
[receipt template](t39-d6-custodian-receipt-template-v1.3.json). The template is
deliberately incomplete (`null` means unanswered, never zero). Its handoff hash is
`7d163b5b13117cf89110a05807c5b42741a8c020bd490600f055036efa58204c`.
The [policy](../../evals/measurement/families-v1.3.md) and
[development findings](../reports/t39-d6-families-v1.3.md) define the rules.

## Work privately

1. Trace all 60 sealed candidates, using their source material and public primary
   sources. Use company/filer families across years, documented parent/subsidiary
   and rename/successor relationships, article identities across formats and paper
   identities across versions. Log evidence, method, confidence A/B/C/U and any
   unresolved relationships in a **private** audit. Candidate/unknown is not an
   independent family. Check all 69 keys in the development exposure input,
   including derived/stress and candidate keys; the input covers all 120 exposed
   development cases, not only the 102 provisional primary cases.
2. Apply the identical D3 ordered taxonomy to every sealed candidate. Privately
   complete D4 fact-role/scoring records and alias/collision checks for every case,
   with source-context and coordinate-proof checks for every table under D5. Do
   this from question/source alone before model outputs. Record all applicable
   reasons privately; report exactly one primary reason in the public partition.
   A clean unanswerable is primary; damaged source or ambiguous scope is not.
3. Resolve source-review questions under those predeclared rules, or keep the
   receipt incomplete. The D3 waiver of two independent reviewers does not waive
   this same-rules screening. No evidence is supplied that this handoff itself
   completes independent review or resolves the separate case-107 gate.
4. Compare against every exposed development family. A matching renamed/parent
   family must map back to its **development key**. If one relationship joins
   several development keys, report all involved keys. Keep sealed material in
   custody. The development tool will move colliding development cases to
   diagnostics while preserving their original tiers/labels.

## Public receipt fields

Copy the template to a new file and complete only its existing fields. No free-text
notes, sealed IDs, questions, content, answers, titles, aliases or per-item hashes
are permitted. Keep the private source audit separately; do not attach it here.

| Field | Meaning |
| --- | --- |
| `candidate_count`, `candidate_by_format` | Account for all 60 candidates, including excluded items. JSON denotes the table format in this proposal. |
| `confidence_counts` | A/B established source identity, C candidate and U unknown; all four counts sum to 60. |
| `d3_counts` | Primary plus the six ordered D3 reasons, totaling 60. `requires_derivation` is a separate skill tier, not an ambiguity label. |
| `d4_records_checked`, `d5_tables_checked` | Must equal all candidates and all JSON/table candidates respectively; checking just retained items is insufficient. |
| `primary_by_format_label` | Counts after the same defect screening; `supported` versus clean `negative`. Do not assume 60 primary. These are provisional until provenance and remaining gates are resolved. |
| `established_primary_family_count` | Number of distinct established A/B families among the screened primary cases. No family names or sealed identifiers. |
| `colliding_development_families` | Unique keys from the development input only. Include collisions with any exposed tier, even if no primary development item uses that key. |
| `colliding_sealed_cases`, `colliding_sealed_families` | Aggregate established sealed cases/families with at least one development collision; count each sealed case/family once. Never add per-family sealed counts. |
| `unresolved_development_families` | Input keys whose alias/control/republication checks remain unresolved; these cannot be certified. |
| Attestations | Set source-only screening, completed lineage review and retained private audit to true only after doing them. `model_outputs_used` must be false. Completed tracing can honestly leave C/U cases; it must report them. |

The validator checks permitted fields, identities, counts and declared completion.
It does **not** prove that private screening occurred. Unknown sealed provenance
prevents a whole-split separation claim, even if there are no known collisions.

## Validate the aggregate result

From the repository root, replacing `RECEIPT.json` with the aggregate receipt's
path and using a new output file:

```powershell
python -m evals.measurement.families check-receipt --ledger docs/reports/t39-d6-family-ledger-v1.3.json --handoff docs/reviews/t39-d6-custodian-input-v1.3.json --receipt RECEIPT.json --output tmp/t39-d6-reconciliation.json
```

This command reads no sealed directory and changes no source, gold or split file.
It creates a development-only exclusion overlay, quota counts and scoped claim.
Review the resulting losses by format/label and family clusters. A missing reserve
means reporting shortfalls; no handpicked replacement is permitted. A successful
receipt check still does not authorize inference: D7, pending gold, successor
integration, whole-benchmark quotas and the final committed execution freeze remain.
