# Evaluation fixtures and contracts

T01 supplies five synthetic documents, 22 source references, and 19 questions. It is a correctness seed set, not a benchmark of real-world retrieval quality or the target 400-document workload. T10 adds the integrated local runner (`run.py`), public development request map (`requests.py`), source-coverage scorer (`score.py`), and cold/warm summary (`summarize.py`). The fixture validator still checks integrity only. Read the [evaluation protocol](../docs/evaluation.md) and [completed results](../docs/reports/t10-evaluation.md) before interpreting quality scores.

## Run the checks

From the repository root with Docker Desktop running Linux containers:

```sh
docker compose build evals
docker compose run --rm evals
docker compose run --rm evals python -m unittest evals.test_validate -v
docker compose run --rm evals python -m unittest evals.test_score -v
```

The image contains a snapshot of `evals/`. Rebuild after editing files. The first build needs internet access for the image and packages. Validation and tests then run with networking disabled, no GPU, and no model downloads. Temporary test copies are written under `/tmp`; the repository is not mounted during these checks.

For an existing Python 3.12 development environment with Poppler (`pdftoppm`) on PATH (needed by the generator test):

```sh
python -m pip install -r evals/requirements.txt
python -m evals.validate
python -m unittest evals.test_validate -v
```

Validation returns exit code 0 for valid data and 1 for invalid data. It reports integrity counts, not a retrieval accuracy score.

## Integrated development comparison

Use the pinned models already set up for the application, Docker Desktop and a host Python with the standard library. The host runner measures API round trips and samples containers; all parsing, database work, CPU models and GPU inference run in Docker. It operates only the `vectornext-t10` project, on localhost port 8089, and never removes a volume. Initial setup is in the root README. This experiment runs the six holdout questions **zero times**.

```sh
docker compose -f compose.app.yaml -f compose.eval.yaml -p vectornext-t10 build vectornext processor llm
docker compose -f compose.app.yaml -f compose.eval.yaml -p vectornext-t10 up -d llm
python -m evals.run --run repeat1 --database-root /storage/repeat1 --policy plain --phase ingest
python -m evals.run --run repeat1 --database-root /storage/repeat1 --policy plain --phase queries --structural-weight 0 --generated-weight 0
```

Repeat the ingestion/query pair for `structural` and `generated`, omitting the two zero-weight flags. Use the same run/database-root for one comparison. Run phases sequentially so other evaluations do not contend for the GPU. A fresh run name isolates caches and host captures; a fresh database-root isolates committed data. Existing ingestion/captures are refused. The original 20261014 capture used `/storage/{policy}`; preserve it. Queries use stored vectors and capture all candidates, evidence, proofs, model audits and costs under ignored `data/t10/<run>/`.

```sh
python -m evals.run --run repeat1 --database-root /storage/repeat1 --policy structural --phase queries --variant primary1 --primary-limit 1
python -m evals.run --run repeat1 --database-root /storage/repeat1 --policy structural --phase queries --variant primary2 --primary-limit 2
python -m evals.summarize data/t10/repeat1 --write
python -m evals.run --run repeat1 --database-root /storage/repeat1 --policy structural --phase startup
docker compose -f compose.app.yaml -f compose.eval.yaml -p vectornext-t10 stop
```

`queries` restarts only this project's API/CPU services, waits for readiness, and runs each registered dev question once with empty processing caches and once warm. Models are already loaded; this is not a disk-cold test. No answer cache exists. `startup` separately stops/starts this project's GPU model and measures readiness. `--case` accepts only registered dev IDs for diagnostic subsets; it must not be used to omit failures from a full comparison. Every variant records its selected case IDs and options. Scores do not certify factual entailment: source review must be recorded separately. No automatic regeneration of sources/labels occurs.

Offline retrieval replay is available as `cargo run --release --locked --offline --example replay_eval -- DATABASE_PARENT CAPTURE_ROOT` inside the core image, with the T10 volume and captures mounted, **after stopping its API owner**. It uses captured query vectors with four candidate budgets and four keyword-weight combinations, without model calls or labels. `scale_eval` is a separate 400-document supplied-vector capacity probe; it does not test realistic ingestion or semantic quality.

Score a saved `replay.json` with `python -m evals.replay_score data/t10/<run>`. The offline scorer consumes only the captured development requests and writes `replay-summary.json`. Both summaries preserve raw-body coverage and separately report coverage with original source labels, so table metadata is not mistaken for missing evidence.

## Origin and coverage

All text, numbers, names, layouts, and labels were created for this repository and are covered by the repository's [license](../LICENSE). No external documents or real match results are included. The Pelé/1954 example is explicitly hypothetical; it must never be represented as verified sports history. The equipment is fictional, too.

| Source | Purpose |
| --- | --- |
| `fixtures/fictional_matches.txt` | UTF-8 name, wrapped paragraph, similar matches with different years/opponents, ambiguous and missing matches |
| `fixtures/nested_matches.json` | Record identity, nested match/publication years, numeric zero, explicit null, missing field, string ID, escaped JSON Pointer keys |
| `fixtures/array_matches.json` | Root-array records and a close year distractor |
| `fixtures/equipment_guide.pdf` | Two native-text pages, table headings/units, temperature exception, sentence continued across pages |
| `fixtures/scanned_note.pdf` | One clean image-only page, no hidden text layer, nearby connector/digit distractor |

The scan is a rasterized synthetic page, not a photograph of paper. It establishes a clean OCR baseline; noise, skew, complex layouts, mixed native/scanned pages, and additional languages need later fixtures. The examples are intentionally small and are not a latency or scaling workload.

Thirteen questions are labeled `dev` and six `holdout`. Keep holdout questions out of prompts, demonstrations, and tuning decisions; ingest only the source documents. Both splits share a small corpus, so holdout scores would be a regression signal rather than evidence of broad generalization. Add an independently authored test corpus before making quality claims.

## Dataset contract

`dataset.json` follows `dataset.schema.json` (JSON Schema 2020-12), with additional source and relationship checks in `validate.py`.

- **Documents:** paths relative to this directory, media type, and SHA-256 of exact file bytes. The hash identifies the immutable source revision. Changing line endings changes the revision; `.gitattributes` keeps text fixtures as LF.
- **Evidence:** a unique ID, document ID, format-specific location, and expected source content. These are gold references, not predetermined runtime chunk IDs. A later chunker may choose different boundaries.
- **Questions:** split, tags, question, optional conversation history, and one expected outcome. History can resolve “that match”; it is not evidence that the match facts are true.
- **Supported:** exact typed answer fields, a source list for each field, and `support_sets`. Each inner set is AND: all members are needed. The outer list is OR: any complete set suffices. Field sources list valid evidence across those sets. The initial data uses one set per question.
- **Ambiguous:** distinct alternatives, their evidence, and the fields that need clarification. Do not silently choose one alternative or sum separate matches.
- **Insufficient evidence:** no supported answer fields, plus an explanatory reason. Unknown/null/absent counts must not become zero. A request for the *raw JSON value* may correctly return null.
- **Presentation:** an optional simple template and its expected rendering. This checks formatting independently of retrieval and factual extraction. T08 implements optional free-form drafts, but T10 does not benchmark them.

Source locations:

| Kind | Convention | Validation |
| --- | --- | --- |
| TXT | Zero-based UTF-8 byte range `[byte_start, byte_end)`; inclusive one-based line numbers | Exact byte slice, UTF-8 decoding, and line boundaries must match |
| JSON | Revision-scoped JSON Pointer; empty pointer means root, `~1` means `/`, `~0` means `~` | Pointer resolves to the exact typed value; absent keys fail, null remains null |
| PDF | One-based page and `[x0, top, x1, bottom]` in points from the top-left | Region is within the page; native text matches after whitespace normalization |

The v1 PDF fixtures use unrotated pages with a zero MediaBox origin. This fixture restriction is not the future database's PDF contract. PDF OCR evidence uses a visually reviewed transcription: the validator checks image-only structure and region bounds, **not OCR text correctness**. It cannot detect an incorrect human transcription automatically.

Source indices must use integer JSON tokens, not `1.0`. Values are compared recursively without treating false as zero, null as missing, or numeric/string IDs as interchangeable. This seed contract also distinguishes integer and floating-point values. Duplicate keys, non-finite numbers, unknown schema properties, duplicate IDs, broken source links, stale hashes, and invalid templates fail validation.

The validator does not infer whether an answer follows from its cited text. Gold facts and expected outcomes require review. Regenerating both a source and a wrong label can produce internally consistent but incorrect data.

## Change or regenerate fixtures

Edit `build_fixtures.py`, then explicitly regenerate sources and labels together:

```sh
docker compose build evals
docker compose run --rm --volume ./evals:/workspace/evals evals python -m evals.build_fixtures
docker compose build evals
docker compose run --rm evals
docker compose run --rm evals python -m unittest evals.test_validate -v
```

The regeneration command deliberately mounts `evals/` writable. Never regenerate as part of validation: stale hashes must be detected, not repaired automatically. The generator uses ReportLab plus Poppler for the scan and requires `pdftoppm` on PATH outside Docker.

ReportLab timestamps are fixed for reproducibility within the same toolchain. Poppler/font changes across operating systems may change raster pixels and PDF hashes. Keep checked-in fixtures as the canonical revision; review any regeneration diff. The Python image is pinned by digest and Python packages by version; Debian package repositories are not a frozen snapshot.

After regenerating, render **all three pages** and inspect the actual content, table labels, cross-page order, and scanned digits. For example, inside the eval image with a writable temporary output mount:

```sh
docker compose run --rm --volume ./tmp/pdfs:/render evals pdftoppm -r 120 -png evals/fixtures/equipment_guide.pdf /render/guide
docker compose run --rm --volume ./tmp/pdfs:/render evals pdftoppm -r 120 -png evals/fixtures/scanned_note.pdf /render/scan
```

Create `tmp/pdfs` first. Generated previews are ignored by Git. Record review results and fixture revisions in the [build plan](../docs/plan.md). See [metrics.md](metrics.md) for the measurement contract that later implementation tasks must follow.
