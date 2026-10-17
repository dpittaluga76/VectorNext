# T39 internal measurement results

NuExtract and ranked 30/20/5 remain the defaults. This is an exposed internal pilot, not an independently validated benchmark or evidence for strategy promotion.

**Read the [interpretation and verification](findings.md) before using these scores.** The frozen string-only/field-name contract causes many failures that are not backend outages or independently judged factual errors. The report retains them without changing the score. [Aggregate data](results.json) · [Separate diagnostic correction](diagnostics-v1.json).

The pilot measures the evaluation harness, exact factual extraction, source grounding and observable failure modes on reviewed public-source adaptations.

| Split / strategy | Strict primary correct | Median / p95 seconds | Strict nonmatching answers | Error bucket |
| --- | ---: | ---: | ---: | ---: |
| development / five | 17/92 | 3.56 / 8.62 | 28 | 40 |
| development / two | 16/92 | 3.56 / 6.09 | 27 | 40 |
| development / facet | 18/92 | 3.56 / 7.12 | 26 | 40 |
| exposed_candidates / five | 6/55 | 2.05 / 7.72 | 12 | 35 |

Accuracy rows use the primary tier. Latency covers every planned case in that split (including derived/stress and failures where observed), not only successful answers. Paired primary latency, family-bootstrap intervals and Wilson intervals are in `results.json`.

| Model / oracle fields | Primary roster | Validator on correct | Validator off correct | Retained states |
| --- | ---: | ---: | ---: | --- |
| nuextract / automatic_fields | 92 | 17 | 18 | {'captured': 53, 'unavailable': 58} |
| nuextract / gold_fields | 92 | 29 | 29 | {'captured': 65, 'unavailable': 46} |
| gemma / automatic_fields | 92 | 21 | 21 | {'captured': 52, 'unavailable': 58, 'failed': 1} |
| gemma / gold_fields | 92 | 40 | 40 | {'captured': 62, 'unavailable': 46, 'failed': 3} |

Unavailable oracle definitions/plans and budget failures stay visible. Gold-field interventions are not applicable to negative cases; consult states rather than treating that column as ordinary end-to-end accuracy. Validator-off outputs are untrusted diagnostics. A gold-matching rejection has not been independently established as a validator defect.

Closed-book-adjusted scores, original-label scores, the v1 table-representation ablation, derived/stress counts, separate grounding results and stage/token distributions are retained in the aggregate JSON. Unknown controls block the adjusted headline; no successful-control items are silently discarded from the all-item score.

Failure attribution allows multiple causes and reports unobserved categories. It does not claim a unique root cause or independent semantic proof review.

Not evidence of performance on original publisher layouts, scanned pages, charts or PDF tables.

Not evidence of table-extraction performance, only of reading from supplied structured cells.

Not generalizable to enterprise or domain documents beyond Wikipedia text, arXiv-style papers and financial-report tables.

Not a measurement of the NASA/USGS track. Those historical results remain separate.

The original repository holdout was not used. Raw responses, exact values, errors, attempt records, resource samples and candidate-level results remain in the private execution directory. No prompts, labels or frozen alternatives were tuned from these outputs.

Reproduction: [internal runtime guide](../../../evals/measurement/internal-runtime-guide.md). Execution source commit: `2e8fea1b1d0d65b44a847ba6a5d4797c5d5d22b7`. Private freeze SHA-256: `ea1afed4e58682acc325fe7a9a5910c75fe1d3deac6e9cc9472cb7f2ce69b0cb`.
