# Measurement foundation

This tool reads retained captures and labels. It never starts models, downloads sources, edits historical scores, or runs an old execution protocol against new code.

This describes `rescore.py`. The separate benchmark/oracle tools below can call models only when explicitly invoked with reviewed inputs and an execution freeze.

## Benchmark v2 tools

The [v1.7 internal review](../../docs/reports/t39-internal-review-v1.7.md) completes
the user-delegated candidate screening and known-family collision check. It leaves
92 development and 55 exposed-candidate primary questions, with derived, stress
and nine collision exclusions separate. All 60 candidates are now exposed to the
implementation assistant; no independent/blind receipt is claimed. Comprehensive
lineage remains uncertified. Source identity, screening, quotas and limits are
explicit in the report. The older original holdout remains unused.

Development gold comes from [v1.6](../../docs/reports/t39-gold-review-v1.6.md),
including 107 under the user's waiver, with v1.7's exclusion overlay applied before
building final rosters. Earlier commands reproduce historical snapshots. Final
runtime/scorer/coordinate integration and a committed execution freeze remain pending.

```powershell
python -m evals.measurement.activate_level_a --audit tmp/t39-internal-review/source-audit.json --proposal tmp/t39-v2-review-proposal-v2 --output tmp/t39-gold-review-reproduction
python -m unittest evals.measurement.test_level_a -v
```

The builder verifies the preserved development inputs and earlier review hashes;
output must be a new directory. It performs no inference or sealed reads.

[Protocol and decision gates](protocol.md) · [Current review handoff](REVIEW.md) · [Residue audit](../../docs/reports/t39-residue.md).

The original 180-question proposal is preserved and is not an execution freeze.
Source screening and confirmed-collision reconciliation are complete internally;
corpus ingestion, final scorer/control integration, execution freeze and measurements
remain prerequisites. No new benchmark/oracle inference has run. NuExtract/ranked-five
defaults are unchanged. This harness pilot uses TXT prose QA, **PDF text ingestion
(clean render)** and **structured-table QA (JSON)**; it makes no broad PDF/table-extraction
claim. [Coverage limits](../../docs/reports/t39-d7-pilot-scope-v1.4.md).

- `public-sources.json`: pinned source URLs, hashes, attribution and terms. Raw acquisitions stay outside Git. [SQuAD 2.0](https://rajpurkar.github.io/SQuAD-explorer/) supplies human spans/negatives; [QASPER](https://huggingface.co/datasets/allenai/qasper) supplies paper questions/evidence; [TAT-QA](https://huggingface.co/datasets/next-tat/TAT-QA) supplies annotated financial tables. These public benchmarks may have appeared in pretraining.
- `prepare_review.py`: deterministic candidate selection and complete source-family separation, retaining provisional report-family caveats. It verifies pinned local acquisitions and creates an unused output directory. PDF preparation uses ReportLab and pypdf with an explicit Unicode font; creates fixtures once, never during tests or measured runs.
- `review.py`: checks a named independent approval, exact manifest/file identities, complete case coverage, typed/support review, strata and custody attestation. Hashes do not prove independence or secure files.
- `internal_custody.py`: separately validates delegated, exposed source-review records and publishes only aggregate counts/public development collision keys. Its receipt cannot satisfy `review.py` or the old independent runner gate. See [v1.7 commands and limitations](../../docs/reports/t39-internal-review-v1.7.md).
- `internal_successor.py`: builds the reviewed private package without inference, preserving original/corrected source representations and reviewed-text coordinates. `capture_grounding.py` / `capture_projection.py` connect captured records/block spans to the frozen scorer and keep rejected drafts separate. [Reproduction, checks and remaining integration](../../docs/reports/t39-internal-successor-preflight.md).
- `evaluation_processor.py` / `evaluation_worker.py`: isolated evaluation entry points; the same frozen D4 instruction reaches planning, assessment and extraction before native template counting/generation. D7 question-only control accepts no source/gold hints. Raw RPC frames and explicitly decoded transport observations are retained in new per-process capture directories. Normal Compose/worker behavior is unchanged. Final runner/freeze/coordinate-scoring integration is still pending; these are not a bypass for custody gates.
- `table_pipeline_preflight.py`, `table_preflight_report.py`, `formatted_budget_preflight.py`: unscored real ingestion/reranking and native token checks for the nine flagged rows. [Results, limits and reproduction](../../docs/reports/t39-table-pipeline-preflight.md). No answer generation.
- `run_benchmark.py`: current API durable-job capture, family-based arm rotation, frozen image/code/input checks, revision binding, retained ingestion failures and polling-only uncertain-outcome recovery. Requires a separate isolated deployment/ingestion freeze; no model setup or automatic resubmission.
- `oracle.py`: one reviewed development evidence/field intervention with the existing two-call processor operation and full model lease. Saves original bytes before invoking a model, checks the existing token budget and preserves errors. Does not disable production validation or retry.
- Rust `measurement_candidate` example: compile with `--features measurement`; compare the **same** raw candidate using exact JSON materialization and the existing validator. The feature is absent from the production build. Missing pointers stay unresolved in both branches; null abstention and mechanical rejection remain separate.
- `attribution.py`: conservative, multi-cause failure flags from independently scored observations; distinguishes bad proofs from proven false rejection and semantic errors from mechanical validator bugs.
- `gate.py`: paired source-family bootstrap, harmful-answer/latency gates and explicit prospective inadequacy. The bounded pilot cannot meet the predeclared 520-sealed-question requirement; do not call its outcomes a default promotion.

Preparation, using the pinned source files already acquired locally and a Unicode TrueType font:

```powershell
python -m evals.measurement.prepare_review --sources LOCAL_SOURCE_DIRECTORY --output NEW_REVIEW_DIRECTORY --font PATH_TO_UNICODE_TTF
python -m unittest discover -s evals/measurement -t . -v
docker compose run --rm core cargo test --locked --offline --features measurement
docker compose run --rm core cargo clippy --locked --offline --all-targets --features measurement -- -D warnings
```

The preparation command needs `reportlab` and `pypdf`; scorer/review/runner unit tests use Python's standard library. The separate evaluation-worker tests require Linux and the processor image's pinned Python dependencies; host discovery skips that module on Windows. Run those tests in the offline processor image with current evaluation/model sources mounted read-only, as recorded in the continuation report. See the handoff for reviewed execution commands and required JSON records. Preserve all failed preparations/attempts. Never run an evaluation against the normal application volume.

## Historical rescoring

From the repository root, with Python 3.11 or newer:

```powershell
python -m unittest evals.measurement.test_measurement -v
python -m evals.measurement.rescore --output tmp/measurement/new-report
```

The output directory must not exist. `measurement.md` contains the outcome matrix; `measurement.json` contains per-question results, separate component tracks, observed stage distributions, missing observations and SHA-256 identities of every consumed input. Input hashes are checked again before writing results. Raw captures are local and ignored by Git, so a fresh clone can only rescore capture families that are actually available. Published results link their retained source environments; the tool does not recreate them.

## Definitions

- **Answered correct:** the frozen expected outcome, exact typed values and annotated source support pass, together with recorded mechanical validation. This is agreement with the available labels, not independently verified semantic correctness.
- **Answered wrong:** a supported output fails that criterion. Value correctness and citation/support correctness are separate fields; known reviewed source exceptions remain separate from frozen scores.
- **Abstained correct:** the expected ambiguity or insufficient-evidence outcome is returned correctly.
- **Abstained missed:** an answerable question is declined or its candidate is rejected.
- Wrong negative categories, correct/incorrect request declines, infrastructure/model failures and unscorable captures are reported separately. A different negative outcome is not automatically correct; an unavailable model is not an appropriate abstention.
- **Gold-matching rejected draft:** a retained rejected candidate's exact values match gold. It is not automatically a validator false rejection: the proof can still be invalid. Missing/truncated candidates and unresolved JSON null placeholders remain unobservable. Source-review exceptions never overwrite frozen labels.

Denominators include scheduled failures and missing captures within discovered blocks. Transport/preflight errors with an explicitly empty response remain errors. A missing capture remains unscorable, not an invented model result. A missing whole run is not manufactured. Planner-only and retrieval-only trials have their own denominators; they are not complete answer trials.

Wilson 95% intervals describe distinct questions within one arm/cache pass. Duplicate questions in a group are rejected. Models, strategies and repeated passes are not pooled as independent observations. The small, previously observed datasets and shared source families limit inference; paired, source-family-aware comparisons and an independently labelled holdout belong to the later benchmark protocol.

## Latency

Each observation has its own sample count. Missing timings/tokens remain null. Request wall time includes failures and observed interruptions. Job queue, activation and work are retained per attempt. `assessment_call_ms` and `extraction_call_ms` include preparation when only the old audit is available; `*_inference_ms` is reported only when explicitly recorded. Model-load time is not inferred from answer latency, nor is a process-startup measurement assigned to every question.

Rust parent stages and Python child calls overlap. Do not add their medians or combine medians with different sample counts. `unattributed_core_ms` subtracts only the known disjoint parent buckets from each request's recorded core total; it includes uninstrumented work and does not identify its cause. Negative residuals are flagged. Prompt/output tokens are counts, never milliseconds.

New worker replies carry an optional internal `measurement` object on success and failure. It records stage, completion/failure, preparation/inference/decoding durations and observed token counts. Rust retains it inside each durable attempt's operations. Errors before generation or loss of the worker/transport can still leave timing unknown. No extra model call, prompt change, retry, budget change or validator bypass is introduced.

Coverage and remaining adapters are explicitly listed in each report. See [initial results and limitations](../../docs/reports/t39-measurement.md). The original holdout and normal-library operational captures are excluded.

## Development label audit

The [D2 review](../../docs/reports/t39-d2-adjudication-v1.1.md) records source-checked amendments, precision tiers and the original definition-review condition, later waived in v1.6. Its [systematic audit](../../docs/reports/t39-d2-alternative-audit-v1.1.md) preserves every original alternative, flags possible defects and binds the numeric policy without changing labels. The scanner requires the retained private development proposal and source audit:

```powershell
python -m unittest evals.measurement.test_audit_labels -v
python -m evals.measurement.audit_labels --audit tmp/t39-internal-review/source-audit.json --proposal tmp/t39-v2-review-proposal-v2 --output tmp/t39-internal-review/new-alternative-scan.json
```

Use a new output filename. Only development member paths are permitted. Source matches and heuristic flags are not semantic correctness decisions; original v1 and D1/D2 reviewed views remain distinct. Scorer integration and benchmark execution still require the complete approved freeze. Sealed material is excluded.

## Development tier review

[D3 findings and source-loss checks](../../docs/reports/t39-d3-tiers-v1.1.md) classify the unchanged development questions as primary direct extraction/clean negatives, derived/inference, or stress/adjudication. The [dated tier policy](tiers-v1.1.md) supplements protocol 1 with explicit exclusions, stress-behavior reporting and a reserve-draw procedure. At that freeze no reserve was drawn and the roster was 102/3/15, with original v1 n=120 retained. These are provisional counts without model scores, not an approved execution freeze. The user waived the proposed blind two-reviewer D3 screening pass; no independent-review flag is set. Missing table payloads in the retained source package are distinguished from adapter/application losses.

## D4 typed-fact candidate

[The D4 report](../../docs/reports/t39-d4-typed-facts-v1.1.md) incorporates D1–D3 with a [format instruction](answer-format-v1.1.txt), [scorer](typed_facts.py), per-case alternatives, exact proofs and primary/derived/stress views. Run `python -m unittest evals.measurement.test_typed_facts` for synthetic checks. The [contract](typed-facts-v1.1.md) separates source strings, exact conversions and imprecision. D5 below supersedes its joint primary definition; the frozen D4 scorer remains unchanged. Later v1.6/v1.7 records resolve gold and internally reconcile known collisions; runtime format/proof/control integration remains pending. The candidate is not execution approval.

## D5 table-context candidate

[D5's report](../../docs/reports/t39-d5-table-context-v1.2.md) and
[policy](table-context-v1.2.md) make typed values primary, with grounding and joint
correctness reported separately. Production validation is unchanged.

The generic adapter uses explicit annotations for all 32 development tables; it
does not use questions or gold to infer headers/units. All source cells and
narratives remain exact. Structured sidecars preserve references and derivation
tags, and coordinate proofs distinguish equal values in different rows. Corrected
context is predeclared primary; v1 is an ablation. [All-table diff](../../docs/reports/t39-d5-table-diff-v1.2.md).

```powershell
python -m evals.measurement.build_table_candidate --output tmp/t39-d5-new-candidate
python -m unittest evals.measurement.test_table_context
```

Outputs must be new. Only committed development sources are consumed. Nine rows
exceed MiniLM's whole-record budget and require actual subtree/capture integration
checks. Later v1.6/v1.7 records resolve gold and known collisions; full lineage certification, runtime prompt/scorer/capture
integration and the execution freeze remain unfulfilled. No benchmark has run.

## Source-family tracing and custodian receipt

[D6 findings](../../docs/reports/t39-d6-families-v1.3.md) trace all 102 provisional
primary cases and retain all 120 exposed development cases. Company/filer families
span reports/years; article/paper keys span TXT/PDF and revisions. Provenance
confidence, family clusters and actual split verification are separate.

```powershell
python -m evals.measurement.families build --audit tmp/t39-internal-review/source-audit.json --proposal tmp/t39-v2-review-proposal-v2 --output tmp/t39-d6-new-trace
python -m unittest evals.measurement.test_families -v
```

The build needs the retained ignored development proposal/audit, verifies its
members and refuses an existing output directory. It reads no sealed files and
makes no network/model calls. The public ledger and table trace registry are
review artifacts; URLs are evidence references, not immutable report copies.

Use the [private custodian procedure](../../docs/reviews/t39-d6-custodian-handoff-v1.3.md)
for equal D3-D5 screening, alias/lineage checks and an aggregate-only response.
`families check-receipt` validates that response and creates a development
exclusion/count overlay; it does not rewrite gold or certify that private review
happened. No completed receipt exists yet. Family bootstrap and reserve ordering
helpers are tested with synthetic inputs; no new benchmark outcomes or replacement
draws exist. The prior reviewer/runner must be integrated with this successor
before the final committed execution freeze.

## Pilot scope and question-only controls

[D7's contract](pilot-scope-v1.4.md) fixes track names, negative-case handling,
closed-book matching/masks and mandatory claim limits. Its development audit found
zero matched TXT/PDF paragraphs/questions; the per-system ingestion gap is not
estimable. PDFs 065/079 are stress exclusions. NASA/USGS historical scores remain
separate, with no fresh extension. A real-layout probe is conditional and separate.

```powershell
python -m evals.measurement.pilot_controls --audit tmp/t39-internal-review/source-audit.json --proposal tmp/t39-v2-review-proposal-v2 --output tmp/t39-d7-new-audit.json
python -m unittest evals.measurement.test_pilot_controls -v
```

The offline audit verifies retained development bytes, writes a new output only,
and never reads sealed content or calls a model. The fixed instruction/schema and
matching helpers are ready for integration, not an inference runner. Final execution
must capture one control per primary case/model before retrieval runs and report
all/adjusted primary scores without treating failed controls as nonmatches.
[Audit and verification](../../docs/reports/t39-d7-pilot-scope-v1.4.md).
