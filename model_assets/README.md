# Supported model assets

Production artifact setup and CPU encoders live here, independently of historical experiments.

| Lock | Purpose |
| --- | --- |
| `models.lock.json` | Unchanged MiniLM embedding and reranker identities. |
| `gemma.lock.json` | Pinned Gemma 4 12B QAT Q4_0; original generated-context identity retained. |
| `nuextract.lock.json` | Pinned NuExtract3 Q4_K_M. |
| `setup.lock.json` | Combined explicit setup manifest for both generators and CPU models. |

GGUF files are 6,975,879,296 bytes (Gemma) and 2,783,445,984 bytes (NuExtract). `model_worker/generator_profiles.json` binds their supported runtime aliases, temperatures and template/planner identities. Only one generator is loaded at a time. PDF/OCR assets keep their separate `processor/models.lock.json` setup.

The Windows launcher handles normal setup. Equivalent explicit model preparation:

```powershell
docker compose -f compose.models.yaml build model-download
docker compose -f compose.models.yaml run --rm --no-deps model-download
```

After building the setup image, verify existing files without network access or writes:

```powershell
docker run --rm --network none -v "${PWD}/models:/models:ro" vectornext-model-setup:t37 --verify-only
```

Downloads are explicit, revision-pinned and checked by size/SHA-256 before publication. Routine Start downloads nothing. Do not edit an artifact identity to make incompatible cached vectors or unfinished generation jobs appear compatible. Experimental CPU profiles retain separate identities and locks in their experiment directories; obsolete LLM sources are in [the historical archive](../archives/llm/README.md).
