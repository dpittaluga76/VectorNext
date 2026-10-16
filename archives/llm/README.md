# Historical generator experiments

The supported application now targets Hybrid, Gemma-only and NuExtract-only execution. Historical comparisons do not add runtime model choices.

`pre-hybrid-source.zip` preserves 189 exact public working-tree source files, including the uncommitted generation experiments, runtime code, Compose files and Dockerfiles before the Hybrid implementation. `pre-hybrid-source.json` records the base Git commit, each file's byte count/hash and archive hash. `removed-runners.json` records which obsolete runners/configurations were subsequently removed. Source snapshots contain no model weights, private documents, database files or caches.

To inspect an old runner, extract the archive into a **separate directory**. For complete reproduction, check out the manifest's base commit separately and overlay these source bytes; follow that experiment's original execution freeze and retained source snapshot. Do not overlay an old runtime onto a running Hybrid installation or rewrite historical manifests to match current code.

Historical results remain in [the report archive](../../docs/reports/) and [completed tasks](../../docs/tasks-done.md), including [Gemma promotion](../../docs/reports/t28-ranked-pointers.md), [published temperatures](../../docs/reports/t35-temperatures.md) and [NuExtract planning](../../docs/reports/t36-planning.md). Frozen sources, labels, input checksums and model locks remain in their original experiment directories. Older reproduction commands refer to the archived source environment.

Production setup and CPU encoders live in [model_assets](../../model_assets/). Embedding/reranking experiments remain separate and keep their historical freezes; compatibility CPU imports do not expose additional generation profiles.

The subsequent [experiment Compose cleanup](../../docs/tasks-done.md#experiment-compose-cleanup) removes standalone YAML for the other completed experiments, including embedding/reranking and Hybrid verification. Those files remain in Git history; this existing source archive and all frozen records are unchanged.
