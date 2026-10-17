# D7 — Narrow pilot accepted; TXT/PDF ingestion gap is not estimable

2026-10-17. **Purpose: validate the benchmark harness (scorers, adapters and splits)
and provide bounded source-grounded strategy diagnostics; results are provisional
for decisions about real documents.** This is a source audit and pre-registration,
not a model evaluation or final execution freeze.

- Not evidence of performance on original publisher layouts, scanned pages, charts or PDF tables.
- Not evidence of table-extraction performance, only of reading from supplied structured cells.
- Not generalizable to enterprise or domain documents beyond Wikipedia text, arXiv-style papers and financial-report tables.
- Not a measurement of the NASA/USGS track if that stays separate, and not comparable with it unless you state how.

## Verified coverage and pairing

The [offline audit](t39-d7-pilot-audit-v1.4.json) checked the unchanged 116 development
package members and reconciled all 120 requests/source hashes against the D4 gold,
D3 exclusions and D6 family ledger. Sealed files were not opened.

| Current track | Development | Provisional primary | Primary positive / negative |
| --- | ---: | ---: | ---: |
| TXT prose QA | 64 | 52 | 33 / 19 |
| PDF text ingestion (clean render) | 19 | 17 | 10 / 7 |
| structured-table QA (JSON) | 37 | 33 | 33 / 0 |
| Total | 120 | 102 | 76 / 26 |

Primary prose is 69/102 (67.6%): 54 SQuAD items and 15 QASPER items. All 17 primary
PDF cases are SQuAD paragraphs rendered as clean one-column PDFs, not publisher
pages. The 33 primary table cases use supplied JSON cells plus D5 structural context.
The previous source review performed round-trip and visual checks; this D7 audit
verifies their retained identities, not a fresh rendering or parser run.

| Pairing check | All development TXT/PDF | Primary TXT/PDF |
| --- | ---: | ---: |
| Identical source-text SHA-256 | 0 | 0 |
| Same text after D4 NFC/ASCII-whitespace/NBSP normalization | 0 | 0 |
| Identical question | 0 | 0 |
| Same question and normalized paragraph | 0 | 0 |

**Per-system paired ingestion gap: not estimable, n=0.** Any 17-versus-52 accuracy
difference mixes format, source and item difficulty. D6's seven shared article
families across TXT/PDF do not provide matched paragraphs/questions. No twins were
created. If genuine pairs are separately approved later, compare the same question,
gold, paragraph, runtime and strategy, recording parsing/chunking changes. Small
losses on clean renders would be expected and would not establish real-layout fidelity.

### The two excluded PDFs

| Case | Original label | Current tier / reason | Source finding |
| --- | --- | --- | --- |
| 065 — “Who has elected the President of Warsaw since 1990?” | Supported | Stress / scope or period ambiguous | The source changes from City council since 1990 to citizens since 2002; a single timeless actor is incomplete. |
| 079 — “In what year did the second wave of the plague hit the Netherlands?” | Insufficient evidence | Stress / premise or entity ambiguous | The source offers a hypothesis and possible geographic reach; the question assumes a definite arrival. |

Neither was excluded for a PDF parser failure, and neither is in the derived tier.
PDF share is 19/120 (15.8%) before exclusions and 17/102 (16.7%) in provisional
primary. D6 collision resolution can change these figures; report the final losses
by track and label. Cases 010/034/047/053/071/107 remain unresolved gold decisions.

## Closed-book controls added to the run plan

The [v1.4 contract](../../evals/measurement/pilot-scope-v1.4.md) predeclares one
question-only call for every final primary item per model, before retrieval runs.
At current counts that is 102 extra controls per evaluated model. The primary
strategy comparison remains NuExtract; any Gemma oracle comparison needs its own
mask. The generic prompt/schema carry no sources, history, titles, gold field names,
types, values or aliases. Native model-template/payload identity is also required
in the final freeze. The application and its two-call validation are unchanged.

Report full primary accuracy and accuracy excluding **positive closed-book gold
matches**, with n and track/source/family composition. These are conservative
string matches, not proof of pretraining contamination. Hidden table spelling and
unlisted valid variants can produce false nonmatches. Source-negative questions
have no world-answer gold: report answer/abstain/error counts, never treat their
abstentions as solved memory cases, and keep all negatives in the adjusted view.
Missing/failed/malformed controls block the adjusted headline rather than becoming
nonmatches. Use the same mask for every retrieval strategy; cross-model comparisons
also require a common mask. Apply the same private control protocol on the sealed
side, returning only aggregates alongside D6's separate receipt.

[Offline helpers](../../evals/measurement/pilot_controls.py) test this matching and
denominator policy and prepare a 102-case **candidate** control roster with hashes.
They do not run inference. Final runner/native-template integration, model/capture
identity validation, family intervals and actual control captures remain pending.
No closed-book or adjusted accuracy is claimed yet.

## Historical tracks and extension trigger

NASA/USGS stays outside primary. Its historical scored views remain
[n=28](t11-independent.md) and [n=16](t14-evidence-coverage.md) distinct questions,
with original frozen gold, scorers and repeated-request counts reported separately.
No original question is re-audited, no fresh NASA/USGS extension is selected, and no
pooled or direct cross-version comparison is claimed. Future extensions must verify
family overlap under D6; current cross-track separation is unverified.

If the decision requires real-document performance, the next separately scoped
step is **at most 20 original-layout PDF probe items**, preferably QASPER paper
versions with existing questions/gold. Verify availability, evidence alignment and
license/redistribution rights first; preserve family/split membership, source audit
and freeze rules. Do not assume TAT-QA original PDFs are recoverable. No acquisition
is authorized by this pre-registration itself. Report counts and failure categories,
not reliable system rankings, and keep the probe outside primary. It is unnecessary
for the current harness-validation purpose.

## Changelog from D6

- Adopted the current track names and narrower purpose; prior artifacts retain
  their historical wording and scores.
- Established no paired TXT/PDF comparison exists; recorded 065/079 exclusions.
- Added the closed-book instruction/schema, strict offline matcher, denominator
  rules and custodian supplement. No output-dependent tuning or label changes.
- Kept NASA/USGS historical scoring separate and pre-registered the real-layout trigger.
- Retained all D1–D6 source, gold, adapter, family and review hashes. This candidate
  does not resolve gold/custody gates or approve execution.

Mandatory limitations, unchanged from the headline:

- Not evidence of performance on original publisher layouts, scanned pages, charts or PDF tables.
- Not evidence of table-extraction performance, only of reading from supplied structured cells.
- Not generalizable to enterprise or domain documents beyond Wikipedia text, arXiv-style papers and financial-report tables.
- Not a measurement of the NASA/USGS track if that stays separate, and not comparable with it unless you state how.

## Reproduction and verification

```powershell
python -m evals.measurement.pilot_controls --audit tmp/t39-internal-review/source-audit.json --proposal tmp/t39-v2-review-proposal-v2 --output tmp/t39-d7-new-audit.json
python -m unittest discover -s evals/measurement -t . -p 'test_*.py'
```

The audit requires the retained ignored development input; output must be new.
**104 measurement tests pass**, including 16 new pairing/control checks. Synthetic
tests cover exact strings/large integers, scale/TeX near-misses, complete two-code
answers, malformed/duplicate output fields, negatives, missing captures, pending
gold, changed source identities and sealed-input rejection. No GPU calls, containers,
new sources or PDF regeneration were needed. [Verification](t39-d7-verification-v1.4.json)
and [review manifest](t39-d7-review-manifest-v1.4.json) bind the new artifacts;
they are not an execution freeze. T39 remains active.
