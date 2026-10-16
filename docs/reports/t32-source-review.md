# T32 — separate post-run source review

The frozen `pdf_correction` label requires the literal passage `Type B manifold: inspect every 45 days` inside cited evidence. All four arms returned the exact value **45** but cited another valid passage on the same PDF page:

> The final July 2031 interval for the Cedar type B manifold is 45 days.

This is original text from the correction notice in [the synthetic source](../../experiments/t32/fixtures/cedar-audit.pdf), page 1. It explicitly supplies the entity, edition and final interval, followed by withdrawal of the earlier 90-day draft. Each capture cites evidence `E1`, chunk `c7`, block `#/texts/7`, bytes `[0,130)`. Rust passed schema, source-reference and mechanical-support validation. The separate labelled schedule passage is also in every assembled evidence set, but it is not the cited passage.

Source SHA-256: `d718f78196f0b4372e6b0e584f630e960194357c74af2f4d28bc00519d3427cd`.

Revision for MiniLM arms: `5ef4b5f0247868a8d48a99aa78c446d8e8503c5f57d0d8a8c57c2a8ede586c7d`. Revision for Nomic arms: `295339424b33f2a3cb4e7dddffd0126367689a50580ffb53b71f2bae66315b17`. Revisions differ because processing/embedding identities differ; the source bytes are identical.

This is an omitted valid support alternative in the author-created label. Keep the frozen scorer/labels and their results unchanged. A separately reviewed count credits this one case to every arm:

| Embedding / reranker | Frozen score | With this reviewed support alternative |
| --- | ---: | ---: |
| MiniLM / MiniLM | 4/6 | 5/6 |
| MiniLM / Ettin-17M | 5/6 | 6/6 |
| Nomic / MiniLM | 1/6 | 2/6 |
| Nomic / Ettin-17M | 1/6 | 2/6 |

No additional inference was run for this review. It does not excuse the baseline's missing lifeboat evidence, the eight Nomic-arm HTTP failures, or establish broad semantic quality. Raw captures remain `data/t32/pilot-v1/<arm>/pdf_correction.response.json`; [the main report](t32-replacements.md) keeps frozen and reviewed counts distinct.
