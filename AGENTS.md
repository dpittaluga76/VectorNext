# Working on VectorNext

VectorNext is an original Rust vector database and local document-retrieval app, with an Axum API, React workspace and Python processing/model services.

## Start here

1. Read [docs/architecture.md](docs/architecture.md) for requirements, boundaries and invariants.
2. Read [docs/plan.md](docs/plan.md) for active work and acceptance criteria. Consult [docs/tasks-done.md](docs/tasks-done.md) only for relevant historical details.
3. Inspect the implementation, relevant contracts and tests before editing. Design proposals and historical reports do not establish current behavior.

Follow the user's current request. These instructions do not independently authorize implementation, model downloads, service changes or experiments.

## Design and runtime

- Use the architecture as the implementation reference. Explicit user instructions can revise it; update the design before changing confirmed requirements or contracts. Resolve routine details within the requested scope.
- Build our own storage, similarity search, keyword index and query behavior. General-purpose parsing, numerical, serialization and model-runtime libraries are allowed.
- Keep the three-service deployment local and containerized. The API alone owns durable storage; the processor has no database mount; only the generation service uses the GPU. Parsing and inference stay outside database transactions and mutex-held work.
- Target one RTX 4060 with 8 GB VRAM. Only pinned Gemma 4 12B and repaired NuExtract3 are supported generators. NuExtract-only is the default; Hybrid and Gemma remain explicit options. Hold a lease for a complete attempt and stop/reap the old backend before switching.
- Preserve two-call answering, f16 KV, MiniLM, structural ingestion and ranked 30/20/5 defaults unless the user authorizes a change. Never silently reassign saved generation policies or relabel embedding spaces.
- Use the [README configuration guide](README.md#compose-files) and [operations guide](docs/development.md). Routine Start must not build/download; Stop targets only the normal VectorNext project and preserves volumes. Historical experiment deployments require their recorded source environment.

## Data and answer integrity

- Follow [storage](docs/storage.md) and [retrieval](docs/retrieval.md) contracts: atomic revisions, durable publication/recovery, immutable snapshot/embedding identities, exact typed values, filter semantics and stable retry receipts. Linux/Docker storage is supported; native Windows storage is not.
- Follow [ingestion](docs/ingestion.md), [PDF](docs/pdf-ingestion.md) and [model ingestion](docs/model-ingestion.md) contracts: preserve original bytes, UTF-8 mappings, JSON pointers, PDF page/box provenance, actual token budgets and strict partial-extraction behavior. Generated annotations remain separate from evidence. Failed ingestion needs explicit retry.
- Follow [answer](docs/answers.md) and [answer-job](docs/answer-jobs.md) contracts: original questions/history, selected scope and bound revisions are authoritative. Rust materializes exact JSON values from source pointers. Preserve distinctions among null placeholders, stored nulls, missing fields and zero. Rejected drafts never become facts or conversation history.
- Hybrid accepts only supported, validated NuExtract facts, with at most one independent Gemma attempt for eligible failures. Preserve admission, cancellation, deadlines, exact attempt diagnostics and uncertain-outcome reconciliation; never silently replay uncertain work or clear poisoned state in place.
- Preserve [HTTP/browser contracts](docs/browser-api.md): origin/method/body-limit behavior, exact value-as-text projections, opaque reports and revision-bound sources. Update [wire schemas](src/service/http/schemas.json) and contract checks with API changes. Keep blocking HTTP work bounded and retain permits until work finishes after disconnect.
- Browser conversations stay in IndexedDB. Durable answer-job history is separate from database exports. Follow the [backup contract](docs/deployment.md): exclusive writer ownership, verified manifests and restore into a new destination. Preserve rollback copies and never use user data for fresh-volume tests.

## Verification

Run checks appropriate to the change; record actual results and limitations. Documentation-only changes need link/diff checks, not GPU evaluations. Prioritize durability/recovery, atomic updates, exact search, provenance and structured-value fidelity.

Core changes use the offline Docker suite (the initial build may need network access):

```sh
docker compose build core
docker compose run --rm core
docker compose run --rm core cargo fmt --check
docker compose run --rm core cargo clippy --locked --offline --all-targets -- -D warnings
```

- Use [README verification commands](README.md#verification) for fixture/scorer, Python and browser checks; rebuild test images after source edits. Keep ordinary test containers offline. Core tests use supplied vectors; synthetic `TestEncoder` output is not semantic-quality evidence.
- Run live model/browser checks only within authorized scope, using isolated data and explicit GPU ownership. Do not rerun quality benchmarks for unrelated parser, storage or documentation edits.
- Never regenerate fixture sources, PDFs or gold labels during tests. Preserve frozen datasets, manifests, scores, raw captures, failed attempts and separate source-review exceptions. Keep the original holdout out of prompts and tuning; historical reproduction uses its recorded source/image identities.
- Review OCR/source changes against originals. Format compliance and mechanical source support do not establish semantic correctness. Workflow reports must distinguish recorded, recovered and unrecorded information without inventing model reasoning.

## Keep the handoff current

- Keep [docs/plan.md](docs/plan.md) short: current state, active/approved work, acceptance criteria, verification, remaining issues and next steps. Mark complete only after acceptance passes; move completed entries and historical handoffs into [docs/tasks-done.md](docs/tasks-done.md), with detailed evidence in `docs/reports/`.
- Update the architecture for changed responsibilities/contracts and README for real setup or verification commands. Keep `AGENTS.md` limited to current development instructions; do not append task histories, scores or deployment diaries.
- Keep weights, private documents, databases, caches, backups and secrets out of Git. Preserve provenance and source terms for explicitly permitted public/synthetic repository fixtures.
