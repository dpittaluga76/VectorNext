# Interpretation, verification and operational handoff

The authorized internal pilot is complete. **Keep NuExtract and ranked 30/20/5.**
Neither smaller evidence strategy qualified under the frozen checks, and this
exposed, undersized pilot cannot establish independent non-inferiority or promote
a strategy. The result is useful primarily as a measurement-harness and failure
diagnostic. It is not a clean general-purpose answer-accuracy estimate.

## What the strict score measures

The unchanged benchmark requires string-valued facts, a finite list of field
mappings and finite source-derived answer variants. Production accepts other
exact types and ordinary automatic field names. The evaluation worker adds the
frozen format instruction but does not coerce a model's numeric plan to strings.
Consequently, format and planning-contract failures dominate many cases.

| Ranked-five primary failure diagnostic | Development (92) | Exposed candidates (55) |
| --- | ---: | ---: |
| Plan violates benchmark string-field requirement | 19 | 23 |
| Planner reports unsupported calculation | 19 | 11 |
| Deterministic pre-inference aggregation guard | 0 | 1 |
| Original ingestion admission failure | 2 | 0 |
| Supported response has an unlisted field mapping | 20 | 8 |
| Matched mapping, nonmatching/unlisted value | 5 | 2 |

The first four rows exhaust the frozen `system_error` buckets (40 and 35).
They are not 75 backend outages. The `answered_wrong` bucket also includes
unlisted field names, so it is not a count of independently adjudicated false
claims. These categories remain failures under the frozen primary score;
neither coercion nor retrospective alias additions earns new credit.

Ranked-five has **4 strict supported answers and 13 correct abstentions** on
development, and **0 strict supported answers and 6 correct abstentions** on
exposed candidates. Therefore its 17/92 and 6/55 totals must not be described as
17 and 6 correctly extracted facts. Twenty-five development and ten candidate
primary cases enter the unreviewed sensitivity queue. No sensitivity accuracy
number is claimed without the predeclared review.

The original-label view is separate: five/two/facet score **31/111, 30/111 and
31/111** on the same retained development captures; candidates score **12/60**.
This uses original listed strings/status with the minimal normalization floor,
not the original datasets' native metrics. Nine excluded development cases were
not executed. Original 120-case labels and every prior review remain intact.

The original table representation and corrected representation both score
**17/92** in the full development roster; non-table captures are reused. Their
24 primary table cases score **0/24** under this contract, so this run does not
establish that table-context repair improves or worsens answering. The ablation
changes retrieval input as well as generation context; it is not a pure renderer
comparison.

## Timing without faster-failure claims

| Development ranked-five observation | Median | p95 | Recorded n |
| --- | ---: | ---: | ---: |
| All planned tiers, observed request wall time | 3.563 s | 8.625 s | 109/111 |
| Strict supported correct answers only | 7.102 s | 8.641 s | 4 |
| Primary error bucket, excluding missing ingestion timing | 1.547 s | 2.156 s | 38 |
| Attempt queue | 0.107 s | 0.200 s | 109 |
| Planning call | 1.258 s | 1.487 s | 109 |
| Query embedding/token checks | 0.003 s | 0.048 s | 56 |
| Candidate search | 0.000062 s | 0.000186 s | 56 |
| Reranking and preparation | 0.019 s | 0.319 s | 56 |
| Assembly and tokenization | 0.409 s | 2.359 s | 56 |
| Assessment call | 1.163 s | 2.215 s | 63 |
| Extraction call | 1.651 s | 2.993 s | 44 |

These medians have different memberships and nested boundaries; do not add them.
The 500-ms durable-job observer polling also contributes to measured request
wall time. Early refusals lower the overall median. This resident NuExtract run
does not reproduce a 16–29-second Gemma end-to-end workload. The historical
[latency table](../t39-measurement.md#where-answer-time-goes) explains that range
from retained captures without rerunning it.

Ranked-two and facet both have a 3.563-second all-tier median; neither meets the
10% latency gate. Paired strict-success medians do not improve either. Two
ingestion failures lack request times, so full timing completeness also fails.
The frozen harm ceiling fails under its strict `answered_wrong` definition.
Any apparent non-inferiority bootstrap result is descriptive: no sealed split and
insufficient prospective sample size mean there is no formal non-inferiority claim.

## Population and controls

| Split | TXT prose | Clean-render PDF | Structured-table JSON | Positive / negative |
| --- | ---: | ---: | ---: | ---: |
| Development primary | 51 | 17 | 24 | 66 / 26 |
| Exposed candidate primary | 23 | 9 | 23 | 43 / 12 |

Combined primary is **147**, with **38 negatives (25.9%)**. Development has
55 source families and candidates 34; format-specific family counts overlap and
must not be summed. Largest primary cluster is five in each split. Family
bootstrap intervals and Wilson intervals remain in `results.json`; sample
adequacy is not established by publishing an interval. All 60 candidates were
exposed through delegated internal review. Comprehensive corporate lineage
remains uncertified, and the primary total is below the original 150 minimum.

Both models completed all 147 question-only controls. Each matched two positive
development gold answers and zero positive candidate gold answers. NuExtract's
ranked-five closed-book-adjusted development score is **16/90**, versus **17/92**
on all cases; candidates remain **6/55**. The Gemma control mask in the aggregate
JSON is applied to NuExtract's RAG captures as a diagnostic; it is not a Gemma
end-to-end score. A closed-book nonmatch does not prove no training contamination.
All source-relative negative cases remain in the adjusted view.

Three development and two candidate cases are in the derived/inference tier;
none succeeds under the frozen scoring. Sixteen development and three candidate
cases are stress/adjudication items, excluded from factual accuracy. Their
behavioral observations remain explicitly unreviewed rather than inferred from
final status alone. No original-layout PDF extension or fresh NASA/USGS track ran.

## Oracle and attribution boundaries

Oracle definitions were prepared from frozen ingestion snapshots before model
outputs were inspected. They are deterministic, internally reviewed source-bound
bundles, not an independently verified perfect-evidence oracle. Automatic-field
oracles reuse the captured NuExtract field plan for both models. Gold-field
oracles provide reviewed names/types/locations, never answer values. Missing
plans, stress cases, failed ingestion, unreconstructable evidence and budget
failures remain visible. Gold fields are not applicable to negative cases.

Gemma ran question-only controls and oracle interventions, **not the end-to-end
strategy comparison**. Its oracle latency or score must not be labelled a full
Gemma-versus-NuExtract application comparison. Different available-case sets and
different evidence from the baseline prevent interpreting a score gap as a pure
planning cost.

The frozen attribution output is preserved verbatim in `results.json`. The
separate `diagnostics-v1.json` corrects two reporting limitations only: known
format/request refusals are separated from infrastructure, and an unresolved
prose-coordinate alignment cannot establish absent evidence. Proven complete
coverage remains true; incomplete coverage with an alignment gap becomes unknown.
Candidate coverage is established for 32 items and unknown for 79; selected
coverage is established for 35, incomplete for one and unknown for 75. These are
conditional capture diagnostics, not full-corpus recall estimates.
This post-run diagnostic amendment does not change primary scores, proof
requirements, labels, selection gates or any model output. Both views remain
available. Wrong strict-contract output accepted by the application is not
automatically a validator false acceptance; independent proof review is absent.

## Verification and retained evidence

The source and input freeze was committed before measured requests. It binds
232 source files, 1,412 runtime inputs, the 591-member successor package, exact
images/containers, model identities and ingestion-bound snapshots. The public
[execution receipt](../t39-runtime-execution-freeze.json) identifies the private
freeze by SHA-256. Labels, prompts, scoring lists and runtime settings were not
tuned during or after the run. No failed measured request was replayed.

- 181 offline Linux measurement tests passed before the execution freeze.
- Rust main-suite tests, measurement helper builds, formatting and Clippy passed.
  The initial all-target invocation hit the HTTP admission test's three-second
  startup bound during concurrent work; the unchanged focused rerun passed.
  Both logs remain; the initial invocation is not claimed as entirely green.
- Earlier default/instrumentation verification covered 176 Rust main-suite tests,
  71 HTTP contracts, 54 OpenAPI schemas, Python/launcher checks, seven components
  and thirteen offline browser scenarios. Those results are in the
  [default migration report](../t39-measurement.md#verification-and-rollout).
- Isolated synthetic control, two-call extraction and an ordinary source-linked
  UI/API question passed. The synthetic document was removed before freezing.
- Preflight framing, lease-priority and Docker mount-order failures were fixed
  before measured inference; their captures remain. Ingestion committed 184/186
  representations; two admission failures were retained in every applicable arm.
- Candidate-level captures stay private. Public outputs contain aggregate
  candidate results and public-development case changes only. The original
  repository holdout remains unused.

Private retained execution: `tmp/t39-execution-20261017/`; progress log:
`tmp/t39-execution-progress.log`. Exact submissions/responses, attempt identities,
RPC/wire observations, failed attempts, Rust on/off comparisons, resource samples,
source packages and run images remain available. Reproduction requires those
private artifacts and the recorded source environment; a fresh public clone
does not contain candidate labels or original local raw captures.

## Completed execution and oracle counts

- **421 planned API answer outcomes:** 333 development strategy positions, 28
  original-table positions and 60 exposed-candidate positions. Six positions
  inherit the two failed ingestions; one submission is rejected before inference.
  The remaining 414 durable jobs have complete terminal captures.
- **294/294 question-only controls captured:** 147 for each supported model.
- **444 oracle positions accounted for:** 236 attempts (232 captured, four
  generation failures) and 208 explicitly unavailable interventions. NuExtract
  captured 118/118 attempted oracles. Gemma captured 114/118; its four unfinished
  generation outputs remain failures, with no retries.
- **679 Rust comparison artifacts completed without helper errors:** 447 processor
  answer captures (including the oracle calls and retained synthetic preflights),
  plus 232 oracle-directory comparisons of those same oracle candidates. The
  duplicate representations are not independent observations or model requests.

| Oracle variant | Primary attempted / roster | NuExtract correct, validator on/off | Gemma correct, validator on/off |
| --- | ---: | ---: | ---: |
| Captured automatic fields + reviewed evidence | 50 / 92 | 17 / 18 | 21 / 21 |
| Reviewed fields + reviewed evidence | 62 / 92 | 29 / 29 | 40 / 40 |

The Gemma attempted denominators retain one automatic-field and two gold-field
primary generation failures; its fourth failure is derived-tier. The remaining
42/30 primary positions are unavailable, including gold fields being inapplicable
to negatives. These interventions are not ordinary end-to-end accuracy scores.

Across all 111 retained development items (multiple flags per item allowed),
the corrected diagnostic attribution flags one
selection loss, four missed assessments with covered proof, 25 extraction
nonmatches under the frozen contract and 12 cases recovered by reviewed fields
among cases observed in both oracle variants. Thirty-four accepted candidates
fail the strict benchmark contract; this does not establish false acceptance by
the production validator. Two baseline gold-matching rejected candidates remain
unadjudicated. Independent validator false-accept/false-reject counts are unknown.
The three frozen candidate-miss flags become unknown because of unresolved prose
alignment; no new complete-retrieval claim follows. The correction changes no score.

## Hardware and restoration

| Observed model phase | Whole-device VRAM median / p95 | Peak / minimum sampled free | Generator-container RAM peak |
| --- | ---: | ---: | ---: |
| NuExtract (97 samples) | 3,898 / 4,024 MiB | 7,646 / 542 MiB | 9.80 GiB |
| Gemma (56 samples) | 7,697 / 7,697 MiB | 7,697 / 491 MiB | 13.80 GiB |

NuExtract's first whole-device sample is an unexplained 7,646-MiB peak, retained
without trimming. Subsequent low median use does not attribute that peak or prove
exclusive per-process VRAM use. Samples are roughly 22 seconds apart and include
transitions; they cannot prove that no shorter peak or WDDM page-out occurred.
No recorded failure reports OOM. API/processor RAM peaks were about 164/734 MiB.
Initial evaluation NuExtract activation was **44.57 s**, switching to Gemma
**81.06 s**, and normal NuExtract restoration **25.28 s**. These are three observed
activations, not latency distributions or guaranteed restart times.

Normal API, processor and generator are healthy on localhost:8088. Readiness
reports NuExtract as both default and loaded model. The original library,
ingestion-job response and six historical answer-job summaries compare exactly
before/after the evaluation. No normal-library content was used as a fixture.
A brief startup-unready observation is retained. The existing images, volumes,
models and pre-activation rollback backup remain intact. The three isolated
evaluation containers and their two networks were removed; both named evaluation
volumes were preserved.

Twenty-two final offline Docker checks passed for the diagnostic supplement,
coordinate alignment and execution/recovery behavior (including five new checks).
The measurement code/policies already covered by 181 frozen tests were not tuned.
The diagnostic script is a separate post-run addition; it can be rerun over the
retained captures without inference:

```powershell
python -m evals.measurement.internal_supplement --root tmp/t39-execution-20261017 --package tmp/t39-internal-successor-03 --output tmp/t39-diagnostics-new.json
```

## Next decision

Before further retrieval tuning, separately scope the automatic-planner/benchmark
contract mismatch and inspect overbroad unsupported-operation decisions. Use a
fresh, predeclared fixture set for any fix; do not tune and rescore this exposed
pilot into an apparent gain. A future independent benchmark needs fresh custody,
review and sufficient source-family samples. No ANN, model or retrieval-default
change follows from this run.
