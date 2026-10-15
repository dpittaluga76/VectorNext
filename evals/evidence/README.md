# T23 fresh evidence retrieval

Read the [frozen protocol](../../docs/t23-protocol.md), [results](../../docs/reports/t23-evidence.md), [source notice](NOTICE.md) and [source manifest](sources.json). Twelve NIST text snapshots, 24 questions and source-bound labels are checked in. Acquisition is explicit (`acquire.py`) and refuses existing fixtures. **Validation and tests never fetch or regenerate sources or labels.** The original six-question holdout and all historical evaluation files remain unchanged.

The measured experiment improves fixed-shortlist coverage from 18/20 to 20/20 complete questions, but final-five coverage remains 16/20. Production defaults are unchanged. This dataset is now observed regression data; use new data for any next quality claim.

## Reproduction

Requirements: Docker/Linux containers, the existing locally prepared `vectornext-app-processor:t18` image and pinned embedding/reranker files in ignored `models/`. No Gemma/GPU is needed. The runtime never downloads models or accesses the network. The measured processor base ID is recorded in `execution-freeze.json`; a differently rebuilt base is a new execution identity, not an exact historical rerun.

From the repository root, using a host Python 3 installation for orchestration only:

```powershell
python -m evals.evidence.validate
docker build -f docker/evidence-test.Dockerfile -t vectornext-evidence:t23 .
docker run --rm --network none --entrypoint /opt/model-env/bin/python vectornext-evidence:t23 -m unittest evals.evidence.test_evidence -v
python -m evals.evidence.run --run repeat-01
```

Use a new run name every time. The runner refuses existing output directories or experiment volumes. It freezes current source/image identities, creates only `vectornext-t23-<run>-*` volumes, mounts models read-only, and gives each isolated process 2 CPUs / 4 GiB with networking disabled. Inference sees a copied public input directory containing only sources, TXT files and questions/hints. Gold is scored afterward by the host. It never starts/stops normal Compose services, removes data, or retries failed processes silently.

Output: `data/t23/<run>/execution-freeze.json`, ingestion capture, four JSONL query captures, process commands/exit codes, logs and `scores.json`. Each capture includes exact source documents/chunks, stage rankings and worker statistics. Runtime data and caches remain in named Docker volumes. `--rm` removes only exited experiment containers.

Scoring existing captures requires no models:

```powershell
python -m evals.evidence.score data/t23/final-v1/01-baseline.jsonl data/t23/final-v1/02-expanded.jsonl data/t23/final-v1/03-expanded.jsonl data/t23/final-v1/04-baseline.jsonl
```

`input-freeze.json` binds pre-inference source/questions/gold/protocol. `execution-freeze.json` preserves the actual measured code/image identity. Input validation fails on changed frozen files. The runner intentionally freezes current experimental code for each newly named run, so inspect identity differences before comparing it to historical results. Preserve earlier captures and manifests rather than overwriting them.

Publication check: the historical execution freeze hashes `model_worker/server.py` with CRLF line endings, while Git stores that existing file with LF. Its bytes match after newline normalization. A fresh checkout therefore has this expected execution-hash difference; reproducing the exact historical bytes requires converting that file to CRLF in an isolated checkout before building. Keep the original freeze unchanged. Frozen source fixtures, questions, labels and protocol retain their exact bytes in Git.

## Interpretation

Only original, source-revision-matched chunk text satisfies frozen quotes; generated context and headings added for reranking cannot satisfy labels. Report raw candidate union, fixed 20 reranker inputs and final five primary passages separately. Failures remain in positive-question denominators; missing-evidence questions have undefined recall, not automatic success. Literal matching may miss unenumerated or split support; the report records a post-run alternate time passage without changing gold.

Hints are authored decompositions of the question, not generated answers or automatic hard filters. Production `coverage_v1`, answer assembly and Gemma extraction are not tested here. Two cache passes are repeats, not independent questions or evidence of statistical significance.
