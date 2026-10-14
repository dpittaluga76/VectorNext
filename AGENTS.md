# Working on VectorNext

VectorNext is an original vector database and local document-retrieval system. The repository currently contains design documentation, not a working application.

## Start here

1. Read [docs/architecture.md](docs/architecture.md) for confirmed requirements, the proposed architecture, invariants, and unresolved choices.
2. Read [docs/plan.md](docs/plan.md) for current status, the next useful task, dependencies, and acceptance criteria.
3. Inspect the relevant implementation and tests before making changes. Do not infer implemented features from the design.

Follow the current user request. This handoff does not itself authorize starting implementation, downloading models, or starting services. When implementation is requested, take the relevant task from the plan and carry it through verification.

## Design discipline

- Explicit user instructions can change the design. Update the documents to reflect those changes.
- Preserve confirmed requirements. Clearly distinguish proposed choices, experiments, and implemented behavior.
- Use the architecture as the implementation reference; tasks and existing code must not silently redefine it.
- Resolve routine implementation details within the requested scope. If a choice materially changes a confirmed requirement, raise the specific conflict rather than inventing a new requirement.
- Build our own vector storage, similarity search, keyword index, and query behavior. General-purpose parsing, numerical, serialization, and model-runtime libraries are allowed.
- Keep model inference outside database transactions. Preserve original evidence separately from generated context and formatted answers.
- Keep all application components containerized and normal operation local. The target has one RTX 4060 with 8 GB VRAM; avoid assuming several large models fit concurrently.

## Keep the handoff current

- After meaningful work, update the current status and affected task in docs/plan.md: what changed, what was verified, remaining issues, and the next concrete step.
- Mark a task complete only when its acceptance criteria have been met; record actual verification results.
- Update docs/architecture.md when component responsibilities, data contracts, or design decisions change. Record the reason and whether the change is proposed or adopted.
- Add real setup and verification commands to README.md as they become available. Do not invent commands for code that does not exist.
- Keep these instructions short. Detailed specifications and progress belong in the linked documents, not here.
- Keep model weights, imported documents, database files, generated caches, and machine-specific secrets out of Git. Commit small synthetic fixtures when needed.

## Verification

No build, test, or Compose commands exist yet. Do not report the application as runnable until it has been implemented and exercised.

Prioritize tests for persistence and crash recovery, atomic document updates, exact-search correctness, source mapping, structured-data fidelity, and retrieval quality. Format compliance alone does not establish answer correctness. Run checks appropriate to the change and record limitations honestly.
