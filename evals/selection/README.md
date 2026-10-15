# T24 final passage selection

This isolated experiment compares two selectors on identical expanded shortlists: original-question ranking and facet-focused selection. Read the [frozen protocol](../../docs/t24-protocol.md), [source notice](NOTICE.md) and [source manifest](sources.json). The ten NASA text snapshots and 24 question/facet requests are separate from source-bound gold labels. Facets are authored from questions; this does not test automatic planning or generated answers.

The completed run improves final frozen evidence coverage **16/20 → 18/20** positive questions at **685 → 1,437 ms** median first-pass latency. See [results and alternate-support limits](../../docs/reports/t24-final-selection.md). Production defaults remain unchanged. This corpus is now observed regression data; future quality claims need new frozen data.

## Run and verify

From the repository root, use a host Python 3 installation for orchestration, Docker/Linux containers, the existing `vectornext-app-processor:t18` image and the pinned embedding/reranker files in ignored `models/`. No Gemma or GPU is needed. Preparation/build may need network access for cached image/dependency layers; all inference and validation containers run with networking disabled.

```powershell
python -m evals.selection.validate
docker build -f docker/selection-test.Dockerfile -t vectornext-selection:t24 .
docker run --rm --network none --entrypoint /opt/model-env/bin/python vectornext-selection:t24 -m unittest evals.selection.test_selection evals.evidence.test_evidence -v
python -m evals.selection.run --run repeat-01
```

Choose a fresh run name. Existing run directories and named volumes cause refusal. The runner creates `vectornext-t24-<run>-*` volumes, mounts models and public inputs read-only, and applies a 2-CPU/4-GiB limit. Only TXT files, source metadata and question/facet requests enter the inference mount; gold is scored afterward. Model initialization verifies pinned local files. No downloads, automatic retries, normal Compose service changes or data cleanup occur during inference.

The run produces an ingestion JSONL capture, four query captures in ranked/facets/facets/ranked order, command/exit logs, `execution-freeze.json`, `scores.json` and `comparison.json` under `data/t24/<run>/`. Captures retain exact original documents, source revisions, all search/reranker results, selection audit and worker statistics. Processes use separate per-arm caches; a repeated cached pass does not measure fresh inference. Database/cache volumes remain after exited containers are removed with `--rm`.

The new selector is in `examples/support/final_selection.rs`, driven by `examples/final_passages.rs`. Production ranked and coverage_v1 implementations remain unchanged. The new example deliberately preserves the old T23 example rather than refactoring its frozen execution tree. The new validator/scorer reuse read-only helpers from `evals/evidence/`; they do not load old questions or labels.

## Freeze and interpretation

`input-freeze.json` binds sources, questions, labels and protocol before measured inference. Validation checks hashes and exact UTF-8 source ranges, never downloading or regenerating inputs. `acquire.py` is an explicit one-time acquisition tool and refuses existing fixtures. The runner binds code, model locks, base/runtime image IDs and input hashes before each measured run; it verifies them again afterward. It also asserts identical candidate keys/general scores across arms and identical complete selection outputs within each arm's repeated pass.

Score conservative literal quote coverage at raw candidates, the fixed shortlist and final primaries. Failed positive requests remain in denominators. Missing-evidence recall is undefined; returning candidates is not an answerability decision. The candidate can return fewer than five passages if exclusions exhaust the pool. Similarity/reranker scores and facet reuse are heuristics, not factual support proofs.

The historical worker may have CRLF working-tree bytes while Git stores LF, as documented in T23. Execution hashes preserve the actual bytes; use their recorded identities when reproducing exact historical execution. Do not rewrite a freeze to match a new checkout. Frozen evaluation inputs use LF and must match exactly.

T25 integration intentionally changes runtime files in this execution freeze. Reproduce the historical experiment from commit `a4efed3`; the byte-exact pre-integration tree is also retained locally in `backups/t24-source-before-t25.zip` (SHA-256 `9eac7131ecdd04c1f768e1fc0bdb58431dbab4451ab06ad3d1cd7349d9d9eaf6`). Its archived `model_worker/server.py` preserves the original CRLF bytes. Do not replace historical hashes with current sources.
