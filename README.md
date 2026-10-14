# VectorNext

An original vector database for finding document evidence and answering questions locally, with local models and a Docker deployment that uses an NVIDIA GPU.

**Status: design and planning. There is no runnable application yet.**

The initial workload is approximately 400 TXT, PDF, and JSON files of 10–30 KB each, on a PC with an RTX 4060 (8 GB VRAM) and roughly 64 GB system RAM.

## Project documents

| File | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Entry point and working instructions for Codex |
| [Architecture](docs/architecture.md) | Confirmed requirements, proposed components, data flow, and open choices |
| [Build plan and status](docs/plan.md) | Current state, sequenced tasks, acceptance criteria, and handoff |

The proposed design combines our own vector and keyword search with document-aware chunking, optional local contextual enrichment, reranking, and source-linked answers. MinIO and Redis are optional design choices, not requirements.

## Resuming with Codex

Open this repository and describe the work you want to do. For example:

> Read AGENTS.md, docs/architecture.md, and docs/plan.md. Summarize the current state and the most important unresolved design choice. Continue the architecture discussion without implementing code yet.

When ready to build:

> Read the project instructions and design, then implement the next ready task in docs/plan.md. Verify its acceptance criteria and update the handoff with the results.

Setup and run instructions will be added when the corresponding implementation exists.
