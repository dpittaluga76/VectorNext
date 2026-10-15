# T26 — Automatic field-planning reliability

Implemented, verified and activated on 2026-10-15. Architecture and plan were updated before runtime edits. T25's original failures and all earlier evaluations remain unchanged. [Protocol](../../experiments/t26/protocol.md) · [Type-repair amendment](../../experiments/t26/protocol-amendment-01.md) · [Reproduction](../../experiments/t26/README.md) · [Machine-readable results](t26-planning.json).

## Delivered

The planner defines requested fields without judging whether unseen documents contain the answer. Reported counts are distinct from calculations across records; separate requested counts stay separate fields. Bounded original conversation history resolves follow-up subjects/properties without supplying evidence. Each field's type is selected independently, including general numeric amounts beside integers. Raw nullable values require an explicit request; missing evidence still requires abstention.

`model_worker/planning.py` retains one schema-constrained Gemma operation at temperature 0 / seed 42 with the existing model, queue/deadlines and context/output limits. No extra calls, retries, fallback fields, values, inferred pointers/filters or question rewriting. The schema is unchanged. The worker validates question/history bounds, names, field counts and UTF-8 description limits, and adds `field-planning-v3`, original-input hash and the absence of source evidence to its existing audit. Explicit fields still bypass planning.

Rust now distinguishes clarification, unsupported aggregation and malformed-plan errors within the existing HTTP 400 `invalid_request` envelope. The earlier aggregate guard still rejects recognized calculations before planning. Retrieval defaults, facet limits, extraction, exact JSON materialization, numeric proofs, storage and browser history contracts are unchanged.

## Evidence, including failed attempts

Raw diagnosis with the unchanged T18 processor confirmed that the three T25 failures were semantic planning decisions: the follow-up returned `needs_clarification`, while separate document counts and the PDF count returned `unsupported`. The opening-year plan was ready but unnecessarily nullable. These were not GPU outages or malformed JSON. A diagnostic request made before readiness returned 503; it remains in the logs and was repeated only after explicit readiness verification.

| Run | Result | Interpretation |
| --- | --- | --- |
| Original planner, first frozen 15 cases | 6/15 | All six negative cases passed; six valid questions were declined and three fields were unnecessarily nullable. |
| First repair, `field-planning-v2`, same 15 cases | 15/15 | Fixed those classification/type checks. Exact field names were not scored; count, type, nullability and subject/property terms were. |
| First source-backed run, v2 | 6/8 automated; 7/8 after separately recorded contract review | A mixed exact-JSON question incorrectly planned the amount as integer. The other flag was an overly specific harness expectation for the existing aggregation refusal message. Original scores/responses were retained. |
| Final repair, `field-planning-v3`, 12 separately frozen cases | 12/12 | Mixed numeric/integer fields in different orders, raw null, boolean/string, count/year, contextual references, units/date constraints, aggregation and missing subject. |
| Final source-backed run, fresh TXT/PDF/JSON | 8/8 | Five supported answers, one missing-evidence abstention and two correct HTTP 400 refusals. No supplied fields or inference retries. |
| Final candidate, previously observed regressions | 5/5 | The four T25 diagnostic questions and v2's failing mixed numeric request now plan correctly. Regression evidence only. |

The v2 decimal failure was not hidden or reclassified as a success: `integer` excluded the decimal pointer, the model chose `/unknown`, and Rust withheld the answer when it materialized a non-nullable field as null. The assessment's generated reason also contained a rounded number; that narrative was never promoted to a validated answer. After preserving v2, an architecture/plan amendment and new fixtures preceded the separate v3 type repair. The final prompt was not tuned on the new verification outputs.

The final source-backed answers were Harbor probes **8**, a follow-up director **Inez Flores**, Harbor boats **2** and Cedar gauges **21** from separately cited documents, Nimbus PDF receivers **9**, and exact JSON **`9007199254740995.00000000000009`**, **`0`**, **`null`**. Unknown funding remained insufficient evidence. All source fixtures describe fictional entities and both one-page PDFs were rendered and visually checked.

Median planner HTTP time was 2.75 seconds for the original 15-case baseline, 6.04 seconds for v2 on those cases, and 7.11 seconds for v3's different 12-case set (maximum 10.27 seconds for v3). The longer prompt and successful field outputs cost time; the baseline often emitted only a decline. These are single local runs with warm models, not a controlled throughput or latency benchmark. Planning still consumes one generation operation per ordinary question.

## Application verification

- **Rust:** 158 top-level checks passed across all targets; two ignored subprocess helpers remain, exercised by parent tests. One additional child test result appears in the logs. Formatting and all-target Clippy with warnings denied passed; existing `buf_redux` / `multipart` future-compatibility notices remain.
- **Python:** 62 worker, planning, scheduler, processor, workflow and reliability checks passed offline. New tests cover invalid bounds, malformed/extra/duplicate fields, transport failures with no retry, original input/audit preservation and keeping untrusted instructions in the data message. They do not establish general prompt-injection immunity. An initial invocation named a nonexistent test module; the corrected run passed and its original log remains.
- **HTTP/OpenAPI:** 71 frozen HTTP compatibility cases, five browser boundary checks and two schema checks passed against an isolated API with a synthetic processor. No endpoint or stable envelope changed.
- **Frontend:** type/build checks, five component tests, ten offline workspace scenarios and two real Axum/docs scenarios passed. The final local-model browser scenario also passed: three automatic requests, real UI-supplied follow-up history, scope reset, exact decimal/zero/null display, citation inspection, IndexedDB reload and unrounded diagnostic export. Screenshot reviewed. A separate captured-response replay passed without additional inference.

Browser harness attempts are retained: the initial null locator matched both value and type; a subsequent run waited for an inspection button inside collapsed details and was explicitly stopped after its three answers completed. A replay initially collided with that run's unused Vite preview port. A replay with bounded waits identified the hidden-button locator, and the final test uses the visible citation. Live tests now skip the redundant preview server and retain raw response attachments. The corrected replay passed in 1.5 seconds; the complete live scenario passed in 59.9 seconds. These were test-selector/startup failures; no production UI changes or model retries were added.

## Retained artifacts and limitations

Original question/case/source hashes live in `experiments/t26/`; raw response bodies, audits, timing, failed attempts, source renders and execution freezes live under ignored `data/t26/`. The committed result file contains compact scored plans and outcome summaries. Neither historical holdouts nor prior scores/manifests/captures were changed. These small agent-authored synthetic checks establish the tested planning and integration behavior, not broad answer quality, semantic completeness or independently administered evaluation.

The exact pre-T26 source is retained in `backups/t25-source-before-t26.zip`, SHA-256 `c1e30c8cc4dc546adbe04397eb5b5a770480e41b55147153825cbe7e81c93395`. The first candidate source is retained in `data/t26/candidate-v1-source.zip`, SHA-256 `7b736906ff91e11676d268d3b02231d3f6b411149108e37f549447644926c6d1`. Archive creation preserved the original working-tree line endings; do not normalize historical freezes.

## Activation and rollback

Normal Compose API/client/admin now use `vectornext-app:t26` (`sha256:6eb40df896cca9ae072e009d04bdaafb631c49057d69b8ce048368028fed491d`), and the processor uses `vectornext-app-processor:t26` (`sha256:e35e7ac30dc120ab1818422faed944ec0fdddc29a33de452f08bc33e142598d8`). The generator remains `vectornext-app-llm:t18`; there were no model downloads or storage-format changes. The final processor image differs from the measured v3 image only by an added deterministic test; the planner module hash matches exactly (`d34aec7b619170c313691f618841b1e08f8b254e5dcc4280f24ea37bb0983a31`). The verified and deployed API binary/UI entry hashes also match.

The normal app had no active job or busy application lane before recreation. After activation all four capabilities were ready at `http://localhost:8088`, and the library response matched its pre-activation bytes exactly. Only API/processor were recreated; the generator, existing documents, volumes and caches were retained. T26's baseline, both candidate API/processor pairs and contract service are stopped; browser containers exited/stopped, and all isolated volumes/captures remain.

The previous T25 API and T18 processor images, plus both measured T26 candidate processor images, remain available. T26 can roll back to the T25 API / T18 processor pair with unchanged T25-compatible storage, after stopping active work; do not downgrade to pre-T21 storage readers without the separate pre-upgrade copy described in T25. Implementation finished without a Git commit or push; the user subsequently authorized README review and publication of these changes. Next proposed work is clearer clarification/ambiguity evaluation, separately scoped and frozen.
