# T14 evidence-coverage evaluation

Eight new NASA/USGS sources and 16 frozen questions compare ranked five, ranked two, and the opt-in `coverage_v1` strategy. Read the [pre-run protocol](../../docs/t14-protocol.md) before interpreting results. T11 files and the original six-question holdout remain unchanged.

Completed results: five 8/16, two 7/16, coverage 8/16 in each pass. Coverage's median was 43.5–44.4% lower than five; the default remains five. [Full report](../../docs/reports/t14-evidence-coverage.md), [source-review exception](../../docs/reports/t14-source-review.md), [workflow](../../docs/reports/t14-coverage-workflow.md). All test services are stopped and volumes/captures retained.

`sources.json` records primary-source URLs, acquisition time, transformations, source terms and hashes. NASA HTML articles become TXT using the existing deterministic article extractor; USGS GeoJSON retains the downloaded bytes. The fixtures include historical source wording, promotional footer text and date-relative labels; their contents are evidence for this snapshot, not automatically current scientific claims. In particular, the raw USGS tsunami flag is a stored field, not a conclusion that a historical tsunami did or did not occur.

These attributed snapshots are not relicensed as AGPL code. Preserve publisher credits and consult the NASA/USGS terms linked per source; inclusion does not imply publisher endorsement.

`dataset.json` holds labels and byte/pointer annotations. `requests.json` holds only public inputs sent to the application. Annotation v2 accepts source-span gaps containing only whitespace and lists alternate supporting occurrences explicitly. The old T11 scorer and its original exceptions stay separate. Exact answers, source location coverage and human semantic review are distinct checks.

## Reproduce without changing the experiment

Use Python 3.12+, Docker Desktop with NVIDIA GPU support, and the existing pinned models under `models/`. No additional model downloads or cloud inference are required.

**After T15:** run the following commands from the preserved T14 source tree, not current source. Before the repair, all 272 non-ignored repository files were saved byte-for-byte in local `backups/t14-source-before-t15.zip`; both frozen manifests were verified. Extract into a new directory and provide the existing model files separately. The archive hash and restoration details are in [T15 verification](../../docs/reports/t15-numeric-proofs.md). This ignored archive is local and is not included in a fresh Git clone. Current source intentionally fails the old execution check; never refresh that manifest to conceal a runtime change. Retained T14 image tags have not been overwritten.

```powershell
python -m evals.coverage.freeze --kind data
python -m evals.coverage.freeze
docker build -f docker/app.Dockerfile -t vectornext-app:t14 .
docker build -f docker/app-processor.Dockerfile -t vectornext-app-processor:t14 .
docker image inspect vectornext-app-llm:t10
python -m evals.coverage.run --run my-fresh-t14-run --phase all
python -m evals.coverage.summarize --run my-fresh-t14-run --output my-results.json
docker compose -f compose.app.yaml -f compose.coverage.yaml -p vectornext-t14 stop
```

The generator image is the pinned T10/T13 26B runtime. If unavailable, build `docker/app-llm.Dockerfile` with that tag after the normal model setup. The run uses port 8094 and dedicated `vectornext-t14` volumes. Choose an unused run name; existing captures are never overwritten. Each block gets a fresh API/CPU process; cold and warm blocks share that strategy's application cache. The GPU service stays loaded throughout. Only this project's services are stopped; data, caches and captures remain available.

`data-freeze.json` predates inference and binds sources, labels, requests, scorer and protocol. `execution-freeze.json` additionally binds code, model locks and Compose. Runtime image IDs are captured per block. The runner checks both freezes, identical runtime images and unchanged source revisions between blocks. It retains every admission/HTTP/model failure in the denominator. Do not regenerate sources/labels or adjust candidate rules after observing outcomes. A code update requires a separately documented experiment, not rewriting these manifests.

`status.py`, `summarize.py` and `publish_workflows.py` are post-freeze inspection/reporting tools; they do not participate in inference or change the frozen scorer. Before future runtime edits, preserve the currently matching source tree in version control or a snapshot. Model artifacts are not bundled, and the recorded runtime image IDs remain the authority for the measured environment.

Ignored raw results live under `data/t14/<run>/`: ingestion diagnostics, immutable document snapshots, individual API responses, stage/answer scores and GPU/container samples. The source HTML downloads are retained under `data/t14/source-downloads/`. Neither directory contains user documents. Repository fixtures and reports alone are intended for sharing.

## Try the experimental option separately

Build/recreate the normal app from current source, then use an ordinary answer request file:

```powershell
python -m deployment.client ask my-question.json --evidence-strategy coverage_v1 --report my-workflow.md --capture my-capture.json
```

For the isolated T14 instance, add `--url http://127.0.0.1:8094` before `ask`. The option is experimental; the default remains ranked five. Give each requested field a useful description, including the entity/measurement and units. Do not put expected answers into descriptions. `coverage_v1` uses the same 20-candidate pool; it cannot recover an absent candidate, guarantee sufficient evidence, or disambiguate a poorly specified question.
