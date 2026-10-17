# T39 — Table ingestion, budgets and evaluation-worker continuation

2026-10-17. Following the [Level A activation](t39-gold-review-v1.6.md), the nine
oversized corrected rows passed actual Rust ingestion, MiniLM embedding and
reranking checks. A separate token-only replay also passed with the frozen D4
instruction. **Two formatted prompts have only 51 tokens of input headroom**;
actual automatic plans must still undergo the normal budget checks.

| Check | Observed result |
| --- | --- |
| Scope | Two complete development tables containing the nine flagged rows; questions 087, 091 and 092, with no answers generated or scored |
| Ingestion | Both committed in temporary Linux storage, producing 15 and 38 chunks |
| Flagged rows | Three rows split into three chunks each; six rows into five chunks each |
| Embedding | Maximum 245 / 256 tokens, including structural context and special tokens; no truncation |
| Reranking | 15, 20 and 20 actual candidate subtrees; maximum pair lengths 244, 109 and 109 / 512 tokens |
| Source fidelity | All chunk record attributes and assembled full records match their supplied corrected source records |
| Production-template input | 2,508, 2,965 and 2,965 / 3,328 tokens |
| Frozen-format input | 2,820, 3,277 and 3,277 / 3,328 tokens; all intermediate assembly candidates also fit |
| Generation | Zero calls; the Rust probe stops at the extraction boundary, and the format replay calls only template/tokenization endpoints |
| Model | Already-resident pinned NuExtract3; zero activation seconds, explicit lease acquired and released; no model switch |

The [machine-readable pipeline report](t39-table-pipeline-preflight.json) binds
source code, runtime identities and retained captures. The
[formatted budget report](t39-formatted-budget-preflight.json) binds the frozen
instruction, adapter, native-template observations and token counts.

These are operational checks, not retrieval-quality or semantic-accuracy results.
They use a generic explicit string field, not model-planned fields, and do not
cover all 32 tables. Case 092 remains stress. The first probe used the normal
processor's CPU cache; the formatted replay used a fresh temporary cache. Final
evaluation requires isolated caches and a new execution freeze. Neither check
touches the normal database, opens sealed data or changes the running defaults.

## Evaluation worker

`evals.measurement.evaluation_processor` is a separate private processor entry
point for a future frozen evaluation deployment. Its serial workers apply the
same D4 instruction to planning, assessment and extraction before both template
tokenization and generation. They preserve existing temperatures, schemas,
budgets, two-call behavior and `cache_prompt: false`; non-string plans fail rather
than being coerced. Effective prompt/request identities are audited.

The worker also implements D7's question-only control with its own frozen
instruction/schema. It accepts no history, evidence, gold fields or source hints,
uses one call without retries, and retains failures. Raw RPC input/output bytes
are saved; intermediate HTTP observations are explicitly labelled decoded
transport captures. Native template text and candidate content strings are
retained. Worker restarts create new capture directories rather than overwriting
uncertain attempts. Enrichment and prose are disabled only in this evaluation
entry point. Production worker imports, API contracts and Compose defaults are
unchanged.

Twelve synthetic Linux tests cover both supported profiles, native template
options, instruction consistency, actual audit hashes, no silent type coercion,
negative assessment behavior, failed controls, budget rejection, exact strings,
capture failures and isolation from the production processor. The live check
exercised only tokenization, not planning, assessment, extraction or closed-book
generation. Runner/freeze/scorer/coordinate-capture integration remains pending.

## Verification and retained failures

- All **138 measurement tests passed** in an offline processor container with
  current source mounted read-only. Host checks pass 126 tests and skip the Linux
  worker module; the Linux run covers its twelve tests.
- Docker Rust tests passed with `--features measurement`: 180 top-level passes;
  two subprocess helper tests remain ignored in the parent runner and are invoked
  by their parent tests. Formatting and Clippy passed, including the new example.
- Existing dependency future-compatibility notices for `buf_redux` and
  `multipart` remain. No separate frozen HTTP/browser rerun was needed for these isolated tools.
- Failed probe `tmp/t39-table-pipeline-preflight-01` is retained: ingestion and
  reranking succeeded, but token operations rejected its mismatched lease
  priority. The corrected, separate unscored attempt is
  `tmp/t39-table-pipeline-preflight-02`; it does not replace a measured failure.
- Test-development failures are retained in tool output and local logs: stale image tests in
  the first Rust invocation, incomplete synthetic evidence/assessment replies,
  and a missing historical-scorer bind mount. Final checks used current tests and
  complete fixtures. These were harness failures, not model quality observations.
- Only one temporary test container ran at a time; all were removed on exit.
  The three normal services remain healthy. No images, weights, backups or user
  data were deleted.

Reproduce the unscored ingestion probe from the repository root with the normal
processor available and NuExtract already idle:

```powershell
python -m evals.measurement.table_pipeline_preflight --output NEW_CAPTURE_DIRECTORY --run
python -m evals.measurement.table_preflight_report --capture NEW_CAPTURE_DIRECTORY --output NEW_REPORT.json
```

The format replay uses the processor image with current evaluation/model code
mounted read-only, a fresh CPU cache, the existing model files read-only, and the
retained capture read-only:

```sh
python -m evals.measurement.formatted_budget_preflight --capture /input --output /output/NEW_DIRECTORY
```

It requires the internal `llm` service and refuses to switch models. These commands
are explicitly unscored preflights, not the final benchmark runner.
