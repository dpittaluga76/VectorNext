# Measurement foundation: continuation and review handoff

T39 remains **in progress, awaiting independent benchmark review**. E0.1/E0.2/default migration were verified in the [earlier report](t39-measurement.md). This continuation completes the disk-residue audit, prepares the benchmark proposal, and adds protocol, capture, attribution and statistical tools. It does not claim independently approved labels, completed model comparisons or a new strategy default.

## What is ready

- **Residue audit complete.** A real isolated ingest → replace → remove → compact lifecycle retains both originals, both jobs, all three receipts and both revision reservations. One unreferenced blob is reclaimed. Identical retries return their original outcomes; conflicting reuse and revision resurrection fail. [Full audit and inventories](t39-residue.md).
- **Protocol declared before inference.** Primary correctness requires correct facts and annotated support, or the correct negative outcome. The paired gate uses a 5-point non-inferiority margin, at most a 2-point harmful-answer increase, a 10% absolute harmful-answer upper bound and paired latency checks. Source-family resampling preserves correlated questions. Under the explicit prospective assumptions, 520 sealed questions are needed for the primary margin; this bounded pilot is underpowered for promotion. Ranked-five remains the default. [Protocol](../../evals/measurement/protocol.md).
- **180-question proposal prepared.** It contains unchanged public human questions/labels from SQuAD 2.0 (90), QASPER (30) and TAT-QA (60): 90 TXT, 60 JSON-table and 30 PDF questions. Fifty are unanswerable (27.8%). The proposed family split contains 120 development and 60 sealed candidates, across 168 files. All acquired source bytes and prepared files are hashed. This is a proposal, not an execution freeze or semantic approval.
- **Oracle and same-candidate comparison tools.** The capture tool holds a complete model lease, checks the normal token budget, retains exact raw inputs/replies and never retries. The optional Rust `measurement` feature reuses source materialization and validation to observe one captured candidate with enforcement enabled/disabled. The disabled output is untrusted diagnostics; no HTTP bypass or production validator toggle exists. Gold-field and gold-evidence interventions remain separate. The attribution tool allows multiple causes and distinguishes unadjudicated gold-matching rejections from proven false rejections.
- **Durable benchmark capture.** The runner pins approved package/protocol/code/runtime identities, checks isolated container labels and document revisions, rotates strategies by source family, retains ingestion/submission failures and reconciles existing job IDs after interrupted POSTs. It never resends an uncertain measured question. Actual ingestion, the final reviewed semantic scorer and runtime execution freeze remain pending.

## Independent review and limitations

The user designated **Daniel Pittaluga / Architect** as reviewer and sealed custodian. That names a role; it is not approval. [Concrete review instructions](../../evals/measurement/REVIEW.md) explain the required source-family, scope, type, proof, PDF and custody checks. The local reviewer archive is `tmp/t39-review-handoff/reviewer-package.zip`; its manifest and archive identities are in [verification metadata](t39-continuation.json). No message or file was sent to anyone.

Sealed questions/labels and rendered sealed pages were not inspected by the implementation agent. Automated preparation and hashing processed their bytes; the package still resides in the local workspace, so custody transfer is pending. A `sealed` folder and hashes alone do not protect a holdout. The original repository holdout remains untouched.

TAT-QA table IDs are provisional families and need report/company grouping. The 29 PDF files are controlled single-column typesetting, not publisher PDFs or a layout/OCR benchmark. Development has 37/120 negatives and sealed has 13/60; review should confirm or rebalance whole families before freezing. Source annotations are not automatically complete typed-field/proof labels for this app. Fresh independently approved NASA/USGS adaptations or explicit acceptance of the narrower new-source coverage remain unresolved. Existing NASA/USGS results stay in a separate continuity track. Public benchmark content may have appeared in model pretraining.

The first PDF preparation failed its text round-trip check because a bundled font lacked a source character. That partial package is retained. The corrected preparation uses an explicit Unicode font and records its hash; all 29 PDFs pass text round-trip checks. All 19 development pages were rendered and visually inspected without clipping or missing glyphs. The 10 sealed pages require the independent reviewer's visual check. No labels were regenerated and no model was tuned on these results.

## Verification and runtime

| Check | Result |
| --- | --- |
| Full offline Rust suite with `measurement` enabled | 180 main-suite tests passed; two intentional helper/benchmark ignores, plus a passing spawned child check |
| Rust formatting and Clippy | Passed; Clippy also passed with production/default features |
| Exact-value CLI observation | The wrapped RPC candidate preserves `9007199254740993.123456789` exactly in both diagnostic branches |
| Measurement/review/runner tests | 24 passed on the host and in a network-disabled Docker container |
| Existing workflow tests | 27 passed |
| Build-cache manifest compatibility | Offline `cargo fetch --locked` passed with only the manifest, lockfile and dummy library present |
| Proposal preparation | 180 cases, 50 negatives, family-disjoint proposed split, pinned source hashes and 29 PDF text round trips |
| New GPU benchmark/oracle requests | **0**; independently approved labels/freeze are not available yet |

Verification caught a report-field type error, source-reference omissions in synthetic validator fixtures, and the Docker dependency-cache step's missing example path; each was corrected before its passing check. The example now declares an explicit path and a required feature, preserving the manifest-only Docker fetch stage. These failures are not counted as passing checks. Standard-library tests use synthetic fixtures and transport stubs, not semantic-quality evidence.

The direct Python client's omitted-mode helper/fallback now also uses NuExtract, matching its already-updated CLI argument default. Normal CLI invocation and the active server already used NuExtract. This continuation did not rebuild/restart the application or change model prompts, retrieval, storage behavior, UI contracts or data. The earlier three `:t39` services remain healthy. New Rust evaluation helpers are disabled in production. Only one verification container was used at a time; both task verification containers were removed afterward. Prior images, backups, models, unrelated workloads and the normal library remain untouched.

## Completion gate

Daniel must complete the case-level review and sealed custody transfer. Then finalize the reviewed semantic scorer, ingest the isolated corpus once, freeze identities, and run development strategy/oracle comparisons with all failures retained. Report an inconclusive default decision where prospective adequacy fails; do not claim a statistically established replacement strategy. A sealed confirmation, if appropriate under the protocol, remains with the custodian and must not be used for tuning. T39 cannot be marked complete before those required outcomes are recorded.
