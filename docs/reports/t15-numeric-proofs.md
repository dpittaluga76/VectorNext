# T15 — Source-exact numeric proof validation

Completed 2026-10-14 against [architecture sections 4 and 7](../architecture.md). This repairs mechanical answer validation; it does not change retrieval or establish a new answer-quality score.

## What changed

Numeric prose proofs now check the number's boundaries at an exact occurrence of the quote in the complete supplied passage. A shortened quote cannot hide a surrounding sign, digit, decimal or thousands separator. The validator accepts exact English three-digit comma grouping and four-digit years after valid English named-month dates. Original quotes, evidence and typed values remain unchanged.

| Source | Submitted quote | Typed value | T14 diagnostic | T15 diagnostic |
| --- | --- | --- | --- | --- |
| `Count: 3,000.` | `3,000` | `3000` | Rejected | Accepted |
| `Count: 3,000.` | `3` | `3` | Accepted incorrectly | Rejected |
| `Date: Feb. 25,1969` | `Feb. 25,1969` | `1969` | Rejected | Accepted |

The same unchanged [probe](../../examples/proof_boundaries.rs) produced the [new raw result](t15-proof-boundaries.json). The [original result](t14-proof-boundaries.json), all T14 scores and source-review exception remain unchanged. The probe is synthetic and performs no retrieval, inference or benchmark scoring.

The new [numeric validator](../../src/answers/numeric.rs) compares exact spellings, including the sign, fraction and exponent. It constructs a second spelling with valid grouping rather than removing arbitrary punctuation or converting through floating point. This preserves integers beyond machine precision and long decimals. The existing exact numeric filter comparator remains unchanged: arithmetic equivalence would be too permissive for this literal-proof contract.

The [answer tests](../../tests/answers.rs) add seven regressions covering accepted grouping, exact preservation/rendering, clipped numeric components, malformed/unsupported separators, precision loss, valid/invalid dates, repeated quote occurrences, Unicode boundaries, unchanged JSON/type behavior, and the full answer pipeline. A valid grouped proof returns its exact typed value; an invalid fragment remains in HTTP 400 `answer_rejected` diagnostics with no top-level answer or formatted result.

## Verification

- **108 Rust checks passed**, including 22 answer tests, storage crash/recovery, ingestion, retrieval, deployment and diagnostic checks. The two ignored subprocess helper entry points are exercised by their parent tests and excluded from this count.
- **90 Python checks passed** for fixture/scorer/protocol integrity, coverage annotations, readable workflows and reliability/client behavior. No Python runtime changes were required.
- Formatting and Clippy with warnings denied passed. An initial Clippy finding requested a simpler boolean expression; it was corrected and lint rerun successfully. Boundary review also retained ordinary punctuation and hyphenated units; final Rust checks passed after those edits.
- The three-case diagnostic now gives **accepted / rejected / accepted** as expected.
- Built `vectornext-app:t15` from current source and exercised its release API liveness in a temporary, network-isolated, read-only container without model services or user storage. `/healthz` returned HTTP 200. This is a packaging/liveness check, not model readiness or a new end-to-end inference run.
- Verified the archived T14 tree and both original manifests; all 10 historical T14 report/capture files are byte-identical. The current data freeze still matches. The old execution manifest intentionally differs at `src/answers.rs`; the new numeric module is an additional runtime file.

Final API image: `sha256:2d0027e158ea388e76deb536d164c324b0a6af46bb2d90973160613b8c0c7159`. No T14 image tag was overwritten, persistent service started, source dataset relabeled, or GPU/model benchmark rerun.

Commands used, from the repository root in PowerShell:

```powershell
docker run --rm --network none -v "${PWD}:/workspace:ro" -v vectornext-t13-build:/target -e CARGO_TARGET_DIR=/target -w /workspace vectornext-core cargo test --locked --offline --all-targets
docker run --rm --network none -v "${PWD}:/workspace:ro" -w /workspace vectornext-core cargo fmt --all --check
docker run --rm --network none -v "${PWD}:/workspace:ro" -v vectornext-t13-lint:/target -e CARGO_TARGET_DIR=/target -w /workspace vectornext-core cargo clippy --locked --offline --all-targets -- -D warnings
docker run --rm --network none -v "${PWD}:/app:ro" -w /app vectornext-evals python -m unittest evals.test_validate evals.test_score evals.independent.test_protocol evals.independent.test_summary evals.coverage.test_coverage deployment.test_workflow deployment.test_reliability
docker run --rm --network none -v "${PWD}:/workspace:ro" -v vectornext-t13-build:/target -e CARGO_TARGET_DIR=/target -w /workspace vectornext-core cargo run --quiet --locked --offline --example proof_boundaries
docker build -f docker/app.Dockerfile -t vectornext-app:t15 .
```

The named build caches predate T15; their names do not select historical source. The bind mount supplies current source. No new dependency or model download is required by the repair. The separately tagged image preserves historical tags; normal Compose users should rebuild the API from current source (`docker compose -f compose.app.yaml build vectornext`) and recreate that service to use the repair.

## Preserved T14 source

Before changing frozen execution files, saved all **272 non-ignored repository files** as their actual working-tree bytes in local `backups/t14-source-before-t15.zip` (3,400,685 bytes). This includes uncommitted T12–T14 work, build inputs, fixtures, manifests and reports. Ignored model weights, databases, downloads, caches and private documents are excluded. The archive contains `snapshot-manifest.json` with a SHA-256 for every file; every archived byte stream and both T14 freezes were verified before and after the repair.

Archive SHA-256: `dc1d839dd53a226cfbee820cfe45aa4e773a9845be13f8d4c211b1c6cadcedca`.

Restore into a **new** directory rather than overwriting current work:

```powershell
Expand-Archive -LiteralPath backups/t14-source-before-t15.zip -DestinationPath ../VectorNext-t14-snapshot
Set-Location ../VectorNext-t14-snapshot
python -m evals.coverage.freeze --kind data
python -m evals.coverage.freeze
```

Provide the already pinned models separately before following the historical reproduction guide. The ignored archive is local, not part of a fresh Git clone; retain or explicitly publish it when sharing historical reproducibility. Current runtime code must not be substituted into T14 or used to refresh its original manifests. No historical source tree was committed as part of T15.

## Limits and next step

The [documented grammar](../answers.md#numeric-prose-support-t15) is deliberately narrow. It does not infer locales, convert comma decimals or units, expand exponent notation, or equate differently spelled decimals. Numeric lists with ambiguous adjacent separators may be rejected. The date exception is for English named-month dates, not arbitrary date formats. Checks inspect supplied evidence, not unseen bytes beyond it. A mechanically valid quote can still answer the wrong question or cite an incorrect source.

Keep structural context and ranked 30/20/5 defaults; `coverage_v1` remains opt-in. T11/T14 are observed regression evidence. A fresh protocol/corpus is required for a new quality claim, and the original six holdout questions remain unused. Next, scope field-specific **candidate retrieval** and clearly worded ambiguity cases: reranking cannot recover evidence absent from its candidate pool.
