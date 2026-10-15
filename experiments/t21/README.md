# T21 checkpoint and export verification

CPU-only storage verification, without model downloads, GPU inference or a PostgreSQL performance rerun. Read the [checkpoint format and compatibility boundary](../../docs/storage.md#t21-bounded-checkpoint-stream). The normal application is not restarted or upgraded by these commands.

## Regression checks

```powershell
docker compose build core
docker compose run --rm core
docker compose run --rm core cargo fmt --all -- --check
docker compose run --rm core cargo clippy --locked --offline --all-targets -- -D warnings
docker build -f docker/checkpoint-test.Dockerfile -t vectornext-checkpoint:t21 .
```

Tests cover legacy migration, exact values/receipts/revisions/jobs, stream boundaries, corruption/truncation, partial writes and publication failures. A regression creates a valid state above 64 MiB from 33 individually valid transactions, then exports/restores it. The commands below add disk-volume and forced-process-interruption checks on copies of the actual T20 stores that previously failed. Builds need initial dependency access; all verification containers use `--network none`.

## Retained T20 state drill

Requires the stopped `vectornext-t20-v3_vector_data` volume and unmodified `data/t20/20261015-fixed-v3` inputs from T20. Never use a live production volume as the source. For a repeat, choose a new empty target volume, new output directory and container names. The input volume is always mounted read-only; `copy_data.py` verifies every copied file and refuses a nonempty destination.

From the repository root in PowerShell:

```powershell
$checkpointVolume = 'vectornext-t21-repeat01'
$checkpointReports = Join-Path $PWD 'data/t21/repeat01'
New-Item -ItemType Directory $checkpointReports
docker volume create $checkpointVolume
docker run --rm --network none --entrypoint python -v vectornext-t20-v3_vector_data:/old:ro -v "${checkpointVolume}:/work" -v "${PWD}/experiments/t21:/tools:ro" -v "${checkpointReports}:/reports" vectornext-checkpoint:t21 /tools/copy_data.py copy /old /work /reports/source-volume-hashes.json
```

Run each corpus separately; the prepare process intentionally stays alive after acknowledging a checkpoint and an additional journal transaction. Use `400`, then `1600` for `$checkpointSize`. Check every exit code and wait for the readiness line before the explicit kill:

```powershell
$checkpointSize = 400
$checkpointContainer = "vectornext-t21-repeat01-$checkpointSize"
docker run -d --name $checkpointContainer --network none --cpus 2 --memory 4g -v "${checkpointVolume}:/work" -v "${PWD}/data/t20/20261015-fixed-v3:/inputs:ro" -v "${checkpointReports}:/reports" vectornext-checkpoint:t21 prepare /work /inputs $checkpointSize "/reports/$checkpointSize-prepare.json"
docker logs $checkpointContainer
# Wait until: checkpoint and suffix acknowledged; ready for SIGKILL
docker kill --signal KILL $checkpointContainer
docker run --rm --network none --cpus 2 --memory 4g -v "${checkpointVolume}:/work" -v "${PWD}/data/t20/20261015-fixed-v3:/inputs:ro" -v "${checkpointReports}:/reports" vectornext-checkpoint:t21 recover /work /inputs $checkpointSize "/reports/$checkpointSize-recover.json"
```

The 128 frozen exact queries run before checkpoint, after SIGKILL and after export/restore, including the existing T20 sentinel. The separate post-checkpoint transaction re-registers the same embedding identity and adds only a durable receipt/generation, so document/query expectations stay fixed. Recovery verifies that receipt and its idempotent retry. Reports contain full record/receipt/embedding-space digests, the original T20 chunk/vector digest, query checks, generation, backup manifest, durations and cgroup peak. Preparation asserts the actual snapshot exceeds 64 MiB. Reports and export/restore destinations refuse overwrite.

Recheck the original source volume after both sizes:

```powershell
docker run --rm --network none --entrypoint python -v vectornext-t20-v3_vector_data:/old:ro -v "${checkpointVolume}:/work:ro" -v "${PWD}/experiments/t21:/tools:ro" -v "${checkpointReports}:/reports:ro" vectornext-checkpoint:t21 /tools/copy_data.py check-source /old /work /reports/source-volume-hashes.json
docker run --rm --network none --entrypoint python -v "${checkpointVolume}:/work:ro" -v "${PWD}/experiments/t21:/tools:ro" vectornext-checkpoint:t21 /tools/check_frames.py /work
```

The two killed containers remain stopped. Retain the new volume/reports and the original volume; no `down -v` or pruning is needed. These are correctness/operational measurements, not new search-performance or quality scores.

## Legacy backup and rollback check

The copied two-document smoke store supports a quick real-old-binary check if `vectornext-app:t19` is retained. Use a fresh target volume with unused paths:

```powershell
docker run --rm --network none --entrypoint vectornext -v "${checkpointVolume}:/work" vectornext-app:t19 export /work/2 /work/legacy-export
docker run --rm --network none --entrypoint vectornext -v "${checkpointVolume}:/work" vectornext-checkpoint:t21 restore /work/legacy-export /work/legacy-restored
docker run --rm --network none --entrypoint vectornext -v "${checkpointVolume}:/work" vectornext-checkpoint:t21 export /work/legacy-restored /work/upgraded-export
docker run --rm --network none --entrypoint vectornext -v "${checkpointVolume}:/work" vectornext-app:t19 inspect /work/legacy-restored
```

The last command **must fail** with an unknown frame kind: an old reader must never silently accept a new snapshot. Compare `inspect` outputs from the old binary on `/work/2` and the new binary on `/work/legacy-restored` for identical documents/jobs/generation. The original `/work/legacy-export` remains compatible with the old binary. New releases continue to accept both snapshot versions; the original backup file manifest remains format 1.
