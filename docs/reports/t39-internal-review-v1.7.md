# T39 delegated source screening and family reconciliation

Date: 2026-10-17. **Internal source review, not independent approval or a blind
holdout. No candidate-model inference.**

The user delegated the outstanding candidate screening and family check to the
implementation assistant: “you will have to do that part”. The assistant reviewed
all 60 T39 candidates under the existing D1–D5 rules and checked their source
identities against all 120 exposed development cases. All 60 candidates are now
exposed to the implementation assistant. The older original holdout was untouched.

This completes the delegated source-screening pass and known-identity collision
check. It does **not** certify comprehensive corporate control, successor or
republication relationships. Those unknowns are recorded rather than inferred
from a lack of name matches. T39 remains active; this receipt is not an execution
freeze or evidence for a retrieval-default change.

## Resulting roster

| View | Development | Exposed candidates | Combined inventory |
| --- | ---: | ---: | ---: |
| Original questions, preserved | 120 | 60 | 180 |
| Primary direct extraction / clean negatives | 92 | 55 | 147 |
| Derived / inference | 3 | 2 | 5 |
| Stress / adjudication | 16 | 3 | 19 |
| Known-family collision diagnostics | 9 | 0 | 9 |
| Primary positive / negative | 66 / 26 | 43 / 12 | 109 / 38 |

Combined counts are an inventory, not permission to pool results or claim a
generalization estimate. Report development and exposed candidates separately.
Original-label views remain separate from reviewed-label views.

| Primary track | Development positive / negative | Candidate positive / negative | Total |
| --- | ---: | ---: | ---: |
| TXT prose QA | 32 / 19 | 15 / 8 | 74 |
| PDF text ingestion (clean render) | 10 / 7 | 5 / 4 | 26 |
| Structured-table QA (JSON) | 24 / 0 | 23 / 0 | 47 |

Primary negatives are 26/92 in development and 12/55 among candidates; together
38/147 (25.9%). There are **zero blind questions after this internal review**.
The 147 primary questions miss the predeclared minimum of 150. No frozen reserve
exists, so no replacements were drawn. The original 180-question package is intact.
The independent-review, blind-split and primary-size acceptance criteria have not
passed. The bounded pilot also remains too small for its predeclared promotion gate.

## Source review and gold handling

Every positive and negative question received a source-only disposition, source
binding and D4 scoring record. Review used supplied passages and public human
annotations, not candidate-model outputs. Candidate IDs, questions, gold values,
source titles, per-item hashes and detailed notes remain private.

The five non-primary candidates comprise two premise/entity ambiguities, one
unit/format ambiguity and two attribution/inference cases. One original negative
is corrected only in the derived tier; another positive retains a source qualifier
that its original accepted answer omitted. Original labels are preserved alongside
all corrections. Finite aliases are source-derived; unlisted outputs receive no
primary credit. There is no new semantic judge or containment scoring.

All 23 table cases across 20 distinct tables received explicit captions, headers,
body groups, unit scopes and coordinate proofs using the frozen D5 adapter.
Source cells were preserved. Equal-valued cells remain a separate grounding
diagnostic. All 11 candidate PDF cases (10 distinct one-page files) were visually
checked against their supplied prose. No clipping or omitted paragraphs was
observed. The nine primary PDF cases have no matching primary TXT source texts;
their accuracy gap cannot estimate ingestion loss.

The pilot validates the benchmark harness and bounded source-grounded diagnostics.
Its limits remain:

- Not evidence of performance on original publisher layouts, scanned pages, charts or PDF tables.
- Not evidence of table-extraction performance, only of reading from supplied structured cells.
- Not generalizable to enterprise or domain documents beyond Wikipedia text, arXiv-style papers and financial-report tables.
- Not a measurement of the NASA/USGS track; its historical scores and denominators remain separate.

## Family checks and exclusions

The four previously candidate-only development identities are now established by
matching complete tables in issuer-authored annual reports, with PDF hashes and
page references in the [development ledger](t39-internal-review-v1.7/development-family-ledger.json).
Cases 030, 056, 089 and 090 change confidence only; source bytes and gold do not change.
All 101 pre-exclusion primary development source identities are established,
covering 59 families. One non-primary development identity remains candidate-only.

| Confirmed development family | Development questions moved to diagnostics |
| --- | --- |
| Tencent (`company:hkex-00700`) | 012, 013, 041, 105 |
| Woolworths (`company:au-woolworths-group`) | 030, 048, 049 |
| Sealed Air (`company:sec-1012100`) | 056 |
| Symantec / NortonLifeLock (`company:sec-849399`) | 108 |

These are company-level matches, including different table IDs. The overlay
excludes whole development families across all exposed tiers, without modifying
the candidate split or overwriting the development gold. All nine losses are
positive table questions, reducing development's primary table track from 33 to
24. Its coverage therefore changes materially.

The candidate source identities are established at confidence A for 23 company
table cases and B for 37 upstream article/paper cases. There are no unknown
candidate source identities. **Identity confidence is not lineage certification.**
Broader relationships remain unverified for 18 candidate company cases and 24
non-colliding development company families. Upstream article/paper IDs establish
publication identity, not universal absence of republication. The receipt certifies
zero primary cases as comprehensively family-separated.

A separate scan compared all 120 development and 60 candidate sources: zero exact
document-hash matches, zero 40-token literal prose overlaps, and zero explicit
development-company alias mentions in the supplied candidate passages. These are
bounded checks, not evidence that unmentioned parent companies cannot overlap.
The confirmed financial collisions came from tracing tables to full reports.

After exclusions, development has 55 established primary families (largest cluster
5); candidates have 34 (largest 5). Cluster-size distributions, expressed as
`cluster size: number of families`, are:

- Development: `1:33, 2:14, 3:3, 4:3, 5:2`.
- Exposed candidates: `1:22, 2:6, 3:4, 4:1, 5:1`.

Development format strata have 32 TXT, 9 PDF and 21 table families; these counts
overlap across formats and must not be summed. The ledger and overlay contain
the full development cluster statistics for later family-resampled intervals.

## Artifacts and verification

- [Aggregate receipt](t39-internal-review-v1.7/receipt.json): distinct internal type,
  exposure and uncertainty flags, counts and public development collision keys.
- [Development exclusion overlay](t39-internal-review-v1.7/development-overlay.json):
  nine exclusions, unchanged original labels/tiers and recomputed counts.
- [Policy](../../evals/measurement/internal-custody-v1.7.md) and
  [aggregator](../../evals/measurement/internal_custody.py): create-only outputs,
  fixed public allowlist, exact ledger binding and no model/network calls.
- [Verification](t39-internal-review-v1.7/verification.json) and
  [review manifest](t39-internal-review-v1.7/manifest.json): retained checks and hashes.

The private detailed review and source material are retained outside Git. The
receipt binds the complete private audit by hash. Earlier unfrozen aggregate
working copies were retained privately when correcting an inherited exposure flag;
the current ledger explicitly records all 60 opened candidates. All historical
review freezes and the original proposal remain unchanged.

Synthetic verification covers finite aliases, field mappings, numeric-type and
wrong-value rejection, all table coordinates and source preservation. The public
tests also reject forged independence, erased exposure, omitted known collisions,
changed ledger bindings and reuse of an internal receipt as independent approval.
These checks verify consistency and mechanics; they do not make the internal
semantic review independent.

Reproduce aggregation using the retained private audit and this public ledger:

```powershell
python -m evals.measurement.internal_custody --private-audit PRIVATE_AUDIT_JSON --development-ledger docs/reports/t39-internal-review-v1.7/development-family-ledger.json --receipt NEW_RECEIPT_JSON --overlay NEW_OVERLAY_JSON
python -m unittest evals.measurement.test_internal_custody -v
```

Both outputs must be new paths. The original independent-custodian validator
still rejects this receipt. No old execution freeze was bypassed, no models were
called, and no application data or defaults changed. Remaining T39 work is the
honest internal-pilot successor/runtime integration, a committed execution freeze,
question-only controls, strategy captures, oracle ablations and outcome reporting.
Any unresolved lineage stays an explicit limitation rather than a fabricated pass.
