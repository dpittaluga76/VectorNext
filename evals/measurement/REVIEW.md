# Review handoff

Daniel Pittaluga / Architect was the originally designated independent reviewer
and custodian. On 2026-10-17 the user delegated the remaining work to the
implementation assistant. No new benchmark inference has run.

## Current successor handoff

D1-D7 and the six gold recommendations are applied, including 107's explicitly
waived Level A definition. The [v1.7 review](../../docs/reports/t39-internal-review-v1.7.md)
now records the assistant's source-only screening of all 60 candidates, with the
same D3-D5 rules and known company-family collision checks. This is internal,
exposed review; the old independent receipt has not been signed or weakened.
No further user-supplied custody receipt is awaited for this internal pilot.

Keep detailed candidate records private. Use the [internal aggregate receipt](../../docs/reports/t39-internal-review-v1.7/receipt.json)
and [development overlay](../../docs/reports/t39-internal-review-v1.7/development-overlay.json).
Four confirmed company collisions exclude nine development cases. Broader lineage
remains uncertified. Primary counts are 92 development and 55 exposed candidates;
derived/stress counts and coverage losses are reported separately. There is no
blind holdout in this pilot and the 147 primary total misses the minimum of 150.
No reserve exists; none was handpicked. The original older holdout remains unused.

Also follow the [D7 scope/control contract](pilot-scope-v1.4.md): **PDF text
ingestion (clean render)** and **structured-table QA (JSON)** are the accepted
limited tracks. TXT/PDF primary cases are unpaired, so their score gap is not an
ingestion-loss estimate. The current purpose is harness/diagnostic validation;
NASA/USGS remains a separate historical scored view. The conditional original-layout
probe is not part of primary. Before retrieval runs, execute the same question-only
controls for each final primary item/model and retain all/adjusted n, negative
behavior and unknowns. Keep candidate controls and masks private. No control
inference has occurred; do not describe the exposed candidates as unseen.

All 101 pre-exclusion primary development source identities are now established.
This is distinct from full lineage separation. The older reviewer/runner commands
below describe the original independent proposal; they cannot execute this internal
successor. Integrate its typed scorer, corrected context, trusted coordinate
captures, controls and final split, then commit their execution freeze. The isolated
format/control worker and actual table-budget checks are already verified. NuExtract
and ranked-five stay the defaults; no claim of non-inferiority is available.

## Original prepared proposal (preserved background)

Daniel's D1 response is recorded in a [partial v1.1 amendment](../../docs/reports/t39-d1-adjudication-v1.1.md) with exact evidence offsets and the [answerability policy](answerability-v1.1.md). Original labels remain unchanged. Subsequent D2-D7 decisions are recorded in the current answer sheet; complete successor review and sealed custody are still pending; this amendment is not a runner acceptance file.

The implementation agent completed an internal review of all 120 development candidates on 2026-10-16. Use the [seven-decision answer sheet](../../docs/reviews/t39-review-decisions.md) to resolve the concrete findings; [screening results](../../docs/reports/t39-development-review.md) distinguish 95 cases without a specific concern from 25 needing attention. This is advisory development review, not independent approval. Preserve the proposal and create a successor for accepted corrections.

Local package: `tmp/t39-v2-review-proposal-v2/`. Its root `manifest.json` has SHA-256 `3e3a1c37fd3a9d3e216eaaebcf0d41dc9adad718f24a9d2fa6c6a77cb33452b1`.

| Proposal | Development | Sealed candidate | Total |
| --- | ---: | ---: | ---: |
| Questions | 120 | 60 | 180 |
| Provisional source families | 73 | 40 | 113 |
| Unanswerable | 37 | 13 | 50 (27.8%) |
| TXT questions | 64 | 26 | 90 |
| JSON table questions | 37 | 23 | 60 |
| PDF questions | 19 | 11 | 30 |

There are 168 document files, including 29 single-page PDFs. The 90 SQuAD, 30 QASPER and 60 TAT-QA questions and labels come from existing human annotations; they have not been semantically approved for this app. The package is deliberately marked `UNAPPROVED_PROPOSAL_NOT_AN_EXECUTION_FREEZE`.

At proposal preparation, the implementation agent had not inspected sealed questions,
labels or rendered pages; construction/hashing processed their bytes. That historical
state was superseded by the delegated v1.7 review of all 60 candidates. The original
package remains unchanged. A directory named `sealed` is not a secure boundary.

## Review before approval

1. Copy the complete proposal and source acquisition records to reviewer-controlled storage. Keep the manifest and all original files unchanged. Create a separately versioned successor for corrections; do not edit the proposal in place. Retain the original failed PDF-rendering attempt as a preparation failure, not a model result.
2. Inspect the original annotation alongside each proposed request, its complete scoped document, acceptable answers and support. Confirm unanswerable questions remain unanswerable within that exact scope. Review each PDF visually. Do not use either tested model to generate or adjudicate gold labels.
3. Supply the intended typed fields, acceptable exact value/type alternatives and complete alternative proof sets. Preserve null/zero/missing distinctions, source scale and units. For automatic planning, record the permitted mapping from returned field names to intended facts; an extra requested fact is not silently ignored. Do not insert gold answer values into field descriptions.
4. Confirm capability and source-family assignments. TAT-QA exposes table IDs, not reliable report/company-family IDs; group related reports/tables before splitting. Exclude unsupported arithmetic, counting, comparisons or visual reasoning from the primary track and retain them as explicitly labelled stress cases. A matching source string alone is not semantic adjudication.
5. D7 accepts **PDF text ingestion (clean render)** and **structured-table QA (JSON)**. The original proposal's 29 clean-render PDFs include 19 development PDFs; only 17 development PDFs remain provisional primary. Do not infer anything about the unopened sealed PDF dispositions. The [D7 report](../../docs/reports/t39-d7-pilot-scope-v1.4.md) defines exact limits, no matched TXT/PDF pairs and the conditional original-layout probe. NASA/USGS historical scores remain separate; no fresh extension joins this pilot.
6. After corrections/exclusions, retain 150–300 primary questions, 25–30% negative/ambiguous, at least 30% sealed by complete source family, at least 20 families in each split, at least 20 cases per file format and at least 20 table cases. Do not move cases after seeing model results. The proposed split has 30.8% negatives in development and 21.7% in sealed; overall is 27.8%. Report that imbalance or rebalance by whole families **before** freezing.
7. Complete `review.json` using the supplied template. It must account for every request, including exclusions, and identify the exact successor manifest hash. Approve only after field/value/proof definitions and PDF/family checks are complete. Transfer sealed custody outside the implementation workspace, then record that transfer. Keep sealed labels out of chat, Git, model prompts and development scoring.

The code can check attestation fields, counts, hashes and disjoint families; it cannot verify that the human review actually happened or that the reviewer is independent. Do not set approval booleans just to get past the gate.

## Review record

The completed record is separate from the manifest it approves. Required root fields:

```json
{
  "approved": false,
  "independent_of_implementation": false,
  "reviewer": "Daniel Pittaluga / Architect",
  "custodian": "Daniel Pittaluga / Architect",
  "date": null,
  "package_manifest_sha256": null,
  "custody_transferred": false,
  "unresolved": [],
  "cases": []
}
```

Each case needs `case_id`, `accepted`, `capability`, `split`, `family`, `format`, `structure`, `expected`, `gold_fields`, `answer_variants`, `support_sets`, and explicit `exact_values_reviewed`, `support_reviewed`, `scope_reviewed`, `pdf_visually_reviewed`. Use `capability: direct_extraction` for the primary track. Encode exact gold literals as text with their kind; do not round source decimals through spreadsheet or JavaScript numbers. Include exclusion reasons and reviewer notes. Final semantic field mappings and support schema must be frozen with their scorer before inference.

Run this on the custodian's machine; it reads the review and hashes the complete package, including sealed files:

```powershell
python -m evals.measurement.review PATH_TO_APPROVED_PACKAGE PATH_TO_REVIEW_JSON
```

Retain the JSON acceptance output with its review and manifest hashes. For the corrected successor, return only the development package and D6-approved aggregate receipt/custody confirmation. Do not return sealed per-item records or hashes. The original reviewer acceptance alone does not satisfy D6.

## Execution handoff

After approval, freeze the final scorer/field mapping and execution record. The runner requires reviewed public-request/protocol hashes, current code hashes, the three actual image/container IDs, isolated ingestion bindings and a separate synthetic warmup capture hash. Use isolated containers labelled `vectornext.measurement=T39`; normal data/cache volumes are refused. Ingest each document once with structural context and retain every failure. `bindings` maps document filenames to `{state: committed, document_id, revision}` or a retained failed-ingestion record. Validate MiniLM/reranker identities and generator profile/artifact against the image's pinned configuration, and save that preflight with the freeze.

`run_benchmark.py` consumes a version-1 execution JSON containing `model: nuextract`, `split: development`, `arms: [five, two, facet]`, `package_manifest`, `review_acceptance`, `review_acceptance_sha256`, `protocol`, `requests`, `files`, `code_files`, `containers`, `bindings` and `warmup_capture_sha256`. File paths are relative to the approved package; code paths are relative to the repository. `containers` has `api`, `processor`, `llm`, each with its full Docker `id` and immutable `image` ID. The actual corpus/library must match all committed bindings before every request. The runner does not create an execution freeze or silently fill missing prerequisites.

```powershell
python -m evals.measurement.run_benchmark --package APPROVED_DEV_PACKAGE --freeze EXECUTION_JSON --api http://127.0.0.1:18088 --output NEW_CAPTURE_DIR
```

Repeating this exact command reconciles already-started jobs by ID and skips completed captures; it does not resend uncertain questions. Preserve the output directory and freeze. A missing job after an uncertain POST requires investigation, not a new ID. No automatic repair retry or failure exclusion is allowed. Corpus ingestion, live runtime verification and final scorer integration remain pending until reviewed labels are available.

Run gold-evidence/gold-field ablations on development cases only, separately for NuExtract and Gemma. The oracle approval file binds each exact `AnswerInput` SHA-256 to its case ID, names the reviewer/date and specifies `split: development`. Prepare inputs from approved source evidence with actual revision/source references; no model-generated evidence or gold-valued field descriptions.

```powershell
python -m evals.measurement.oracle --input INPUT_JSON --approval ORACLE_APPROVAL_JSON --case-id CASE_ID --model nuextract --processor http://127.0.0.1:18090 --output NEW_ORACLE_CAPTURE
```

The oracle capture includes exact input, model lease/identity, token check, raw answer RPC and failures. A new invocation must not repeat an already attempted case/model/variant. A failed/uncertain attempt is retained; reconcile owned backend state before later work. Use one GPU backend and a dedicated evaluation supervisor; restore the normal NuExtract service after evaluation. The normal library can remain browsable while generation is unavailable.

To compare the same captured candidate with validation enabled/disabled, in the offline core image with current source:

```sh
cargo run --locked --offline --features measurement --example measurement_candidate -- INPUT_JSON ANSWER_RESPONSE_JSON NEW_DIAGNOSTIC_JSON
```

The Rust helper shares exact source materialization and the normal validator. Its disabled arm is explicitly untrusted; it is not an answer API. Feed independently adjudicated per-case observations to `attribution.attribute`; missing observations remain unknown. Then supply complete paired per-case outcome/latency rows to `gate.py`. Do not infer false rejection from correct values alone, or semantic correctness from mechanical support.

```powershell
python -m evals.measurement.gate SCORED_ROWS_JSON --candidate two --output NEW_GATE_JSON
```

The predeclared 520-sealed-question adequacy requirement exceeds this bounded pilot. T39 therefore cannot claim statistical non-inferiority or promote a new default; ranked-five remains while findings and intervals are reported. A larger study requires a separate decision. The custodian need not reveal sealed labels merely to confirm a known underpowered promotion claim.

D2 directions are recorded in the [v1.1 changelog](../../docs/reports/t39-d2-adjudication-v1.1.md). The [historical review request for 107](../../docs/reviews/t39-case-107-independent-review.md) was explicitly waived; [v1.6](../../docs/reports/t39-gold-review-v1.6.md) activates Level A. The additional scan leads were resolved in v1.5. The partial review freeze is not an execution approval and does not transfer sealed custody.

D3 separation and the user’s two-reviewer screening waiver are recorded in the [tier amendment](../../docs/reports/t39-d3-tiers-v1.1.md). Follow the [dated taxonomy/reserve rules](tiers-v1.1.md); do not attest a blind pass that was waived. Sealed custody and final adaptation approval remain distinct from the explicitly waived development-review requirements. Existing verifier gates have not been bypassed by the partial tier amendment.

## D4 typed-fact candidate

[The D4 report](../../docs/reports/t39-d4-typed-facts-v1.1.md) incorporates D1–D3 with a [format instruction](answer-format-v1.1.txt), [scorer](typed_facts.py), per-case alternatives, exact proofs and primary/derived/stress views. Run `python -m unittest evals.measurement.test_typed_facts` for synthetic checks. The [contract](typed-facts-v1.1.md) separates source strings, exact conversions and imprecision. D5–D7 decisions are recorded; unresolved gold, custodian reconciliation, final mappings and runtime format/proof/control integration remain pending. Do not use the current runner/oracle commands with this stricter scorer until their actual prompts and captured coordinates satisfy the contract. The candidate is not execution approval.
