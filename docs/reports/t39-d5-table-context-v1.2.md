# D5: table context and evidence identity

Decision adopted **2026-10-16**, before benchmark inference. The corrected table
representation is the predeclared primary candidate and v1 is the ablation. This is
a tested development review candidate, not final benchmark approval. No models ran,
no sealed material was opened, and no normal application behavior was changed.

[Policy](../../evals/measurement/table-context-v1.2.md) ·
[Annotations](../../evals/measurement/table-annotations-v1.2.json) ·
[All-table before/after context diff](t39-d5-table-diff-v1.2.md) ·
[Machine-readable scan](t39-d5-table-audit-v1.2.json) ·
[Coordinate proofs](t39-d5-coordinate-proofs-v1.2.json) ·
[Review manifest](t39-d5-review-manifest-v1.2.json).

## Two separate repairs

The generic adapter uses manually declared source structure for **all 32 tables**,
covering **37 questions**. It does not inspect questions, gold answers or model
outputs. Every caption/header/group/data row and finite scope is explicit. The
annotation author did previously see the questions; this is internal source-only
review, not a blind or independent approval.

The second component scores source identity independently of value matching. It
expands D4's adjudicated locations into value-cell plus disambiguating-context
coordinates; it never accepts every cell containing the same number. These changes
are separate in code and in the audit.

| Case | Table-context or proof finding | Result |
| --- | --- | --- |
| 012 | Row 0 is the office-building caption, row 1 the shared year-end phrase, row 2 the years. The 2018 value is cell (3,2), `167,488.48`. | Keep caption and year paths distinct; attach the source MWh label and the appropriate column. |
| 002 | Opening balance (1,1) and prior closing balance (6,2) both contain `$1,264`. | Only opening-balance proof answers this question; primary tier unchanged. |
| 080 | Basic EPS (7,1) and diluted EPS (8,1) both contain `$0.34`. | Require the basic row, EPS heading and 2019 column. No million multiplier is assigned to EPS. Primary tier unchanged. |
| 092 | Gross and net have equal figures, and two FY18 columns cover different geographies. | Gross-row proofs differ from net. Both geographic readings have explicit conditional proofs; the case stays stress. |
| 082 | `GBP` alone does not prove the largest common-currency rate. | Each proof alternative retains all three compared rates for one year and INR context. Remains derived. |
| 064 | More visible year-end dates still do not decide what the question means by “2019”. | Keep 0.6 and 0.8 as separate conditional readings; remains stress. |

Coordinates above are zero-based original table row/column indexes. Proof records
also bind the table ID and original document SHA-256.

## All-table audit

| Check | Finding |
| --- | ---: |
| Source table documents | 32 |
| Table questions | 37: 33 primary, 1 derived, 3 stress |
| Source rows / cells preserved | 339 / 1,224 |
| Annotated data rows | 250 |
| Explicit context rules | 275 |
| Tables with multiple column-header rows | 19 |
| Tables with interior body headings | 10 |
| Questions with duplicate exact gold-cell values | 3: 002, 080, 092 |
| Narrative matches surfaced by the value/number scan | 0 |

Every source narrative and every table row was included in the source-only review.
The narrative scan is a lead detector, not a proof of semantic exhaustiveness:
numeric equivalence never automatically awards a proof. No additional narrative
proof was admitted. The scorer supports explicitly reviewed alternative locations,
including paragraph spans; synthetic tests exercise that route. A later discovered
alternative must be versioned and reported separately, never inferred from a model's
preferred citation during the run.

All original cell strings, row indexes and narrative records are preserved. The
old repeated-first-row `headers` field is replaced by per-column structural context
on data rows; non-data rows keep their original cells without the repetition.
The exact original documents are separately retained with hashes and attribution.
Sidecars retain arrays of original strings, references and derivation tags; only
the renderer joins them with ` | `. Joined text is not a permitted value-cell proof.

The registry tags cross-column propagation as `from_span`. The flattened source
does not retain physical merged-cell geometry, so this is an auditable structural
interpretation, not verified PDF geometry. Group scopes are explicitly enumerated.
Blank labels are not replaced with invented “Total” labels.

Units are scoped separately for money, percentages, counts, EPS, dates and note
numbers. For example, 086's amount column has a thousands scale but its expiry-year
column does not; the narrative explicitly dates the observation to August 31, 2019.
This supplements D4's table-only period description without rewriting D4. Cases
089/090 and 116 retain unspecified scales where the supplied context does not
establish them. A `$6.2 million` narrative elsewhere in the 089/090 source does not
establish the table's scale.

## Scoring and retrieval

**D5 supersedes D4's joint primary definition.** The validated final answer's typed
value and frozen field mapping determine primary correctness. Grounding and joint
correctness are reported separately, including `correct_answer_wrong_evidence`.
The prior D4 joint score remains available for comparison. Rejected drafts do not
become primary answers. Production validation is unchanged.

Evidence must identify the selected value cell and the required source context.
The right cell merely being somewhere in the evidence does not rescue a citation
to the wrong cell. Source hashes/table IDs and paragraph ranges are checked.
Conditional grounding for stress cases never enters primary accuracy; recognition
of ambiguity and stated assumptions still require separately recorded review.

The original development roster remains **102 primary, 3 derived, 15 stress**.
The six pending primary cases remain unscored. Cases 002/080 are not in D3's stress
list. Cases 062/064/092 retain unresolved scope/period readings. The generic adapter
cannot supply the absent table-image payloads for 017/099; their D3 source-loss
finding remains unchanged. No cases re-enter primary and no replacements are drawn.

Context is part of the indexed JSON record, so it changes retrieval and generation
inputs. Report value-cell recall and complete-proof recall at candidate/selection k
separately from answer accuracy. The helper checks full captured records against
their frozen representation; it does not grant hidden sidecar context. For raw
subtree candidates, a range/pointer-aware capture adapter is still needed. Mark that
measurement unavailable until integration; do not treat an uncaptured full row as
visible. Answer assembly restores complete record bundles, while current reranking
uses selected subtree text after JSON splitting.

Automatic planning still sees the original question/history and the same D4 answer
format instruction. No headers or gold values are added to that planning input.
Representation, annotations, prompt instruction, proof registry and scorer must be
bound together in the eventual execution freeze.

## Token-size preflight

A CPU-only tokenizer check ran inside the existing processor, loading its pinned
tokenizer files without running an encoder or generator. It started no containers,
changed no services and downloaded nothing. The original raw check is retained
locally; the clarified [public result](t39-d5-token-preflight-v1.2.json) records the
same counts with an explicit distinction between whole rows and actual subtrees.

| Size screen | v1 | Corrected v2 |
| --- | ---: | ---: |
| Table rows checked | 339 | 339 |
| Whole structural row inputs above MiniLM's 256 tokens | 0 | 9 |
| Maximum whole-row token count | 129 | 330 |
| Question/whole-row pairs checked | 398 | 398 |
| Whole-row pairs above 512 tokens | 0 | 0 |
| Maximum whole-row pair count | 132 | 333 |

The nine rows occur in two tables used by cases **087 and 091/092**. They would
trigger JSON subtree splitting. This is a fragmentation warning, not an observed
ingestion failure: actual ingestion, chunk counts, retrieval and reranking have
not run. Whole-row pair counts are a size screen, not measured reranker inputs.
Do not truncate context, raise model limits or claim unchanged recall. Track the
actual split behavior and full-record answer-budget impact during integration.

## Reproduction and verification

From the repository root, use a new output directory:

```powershell
python -m evals.measurement.build_table_candidate --output tmp/t39-d5-reproduction
python -m unittest discover -s evals/measurement -t .
```

Optional CPU token-size check against an **already running** processor:

```powershell
python -m evals.measurement.table_token_preflight --container vectornext-processor-1 --output tmp/t39-d5-new-token-check.json
```

The builder writes 32 corrected documents, 32 sidecars, coordinate proofs, an
all-table audit and a readable context diff; it refuses an existing directory.
Its input set is the committed development table fixtures, annotations, D4 candidate
and explicit conditional-reading adjudications. It has no sealed-input path.

**71 measurement tests passed**, including 24 new adapter/grounding tests. Checks
cover source preservation, caption/year separation, finite groups, mixed units,
changed hashes, invalid/overlapping scopes, context-as-value rejection, wrong cells,
missing disambiguating context, alternative proofs, comparison evidence, stress
denominators, malformed captures and rejected drafts. The 25 artifacts bound by
D2/D3/D4 review manifests remain byte-identical; D1 and the original 116 development
members are also unchanged. Source-only deterministic rebuild checks passed.

No accuracy or latency claim follows from these tests. D6/D7, unresolved gold,
custody/family checks, runtime capture/format/scorer integration and the final
execution freeze remain outstanding. NuExtract/ranked-five stays the app default.
