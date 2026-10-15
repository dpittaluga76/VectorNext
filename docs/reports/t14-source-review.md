# T14 — source review notes

These notes explain observed outputs without changing the frozen dataset, scorer, denominators or implementation. They are post-run review, not new independent measurements. Exact scores remain those specified by [the protocol](../t14-protocol.md).

## Numerical quote validation

The source snapshots store `7,329`, `4,165` and `48,069` with thousands separators. Several rejected drafts returned their correct integer values and exact supporting quotations. The validator searches for the canonical value literal inside the quote, so an integer such as `7329` does not match `7,329`. These are genuine application validation failures, not evidence that the source was absent or the draft number was wrong. A rejected draft remains an error; it is never counted as a successful answer.

Coverage also located the three launch sources and drafted the correct years. The Mariner 6 quotation was `Feb. 25,1969`, exactly as stored in the source. The current numeric-boundary guard rejects the year because it follows a comma without a space. A future repair needs source-exact, context-sensitive numeric/date handling and must retain protection against extracting `3` from `3,000`, dropping signs, changing decimals or losing precision. Blindly removing punctuation is not a safe repair.

A separate deterministic [boundary probe](../../examples/proof_boundaries.rs), using invented text and no models, also found a false-positive gap: a quote reduced to `3` is accepted for value 3 when the complete source says `Count: 3,000.`. Boundaries are currently checked inside the submitted quote rather than against its full source occurrence. This probe is outside the 16-question evaluation and changes none of its scores. A follow-up must check both the quote and full source context; accepting additional number formats alone would leave this defect unresolved.

## One question permits more than one reading

Frozen case `unspecified_flyby` asks: “At what closest range in kilometers did Mariner 10 fly by Mercury?” Its gold label is `ambiguous` under the app's rule for several matching events without a distinguishing encounter/date; the source records three flybys.

However, “closest range” can reasonably ask for the minimum across the mission. The source explicitly calls the third flyby the closest and gives 327 km. The two-passage and coverage cold runs returned that value with a source quote. That is a defensible reading of the question, even though it fails the frozen clarification label. The five-passage cold run returned 703 km, the first flyby's range; it also fails the frozen label and is not the minimum.

Do not interpret all three strict failures as equally wrong factual answers. Preserve this question and its original score in T14, and record this annotation limitation separately. A future ambiguity test should explicitly ask for an encounter-specific range while leaving the encounter unspecified; a separate minimum-range question should request the source's explicitly reported minimum. Do not silently relabel this observed case or use its revised wording as fresh independent validation.

Context completeness for this case requires all three annotated alternatives. That is a conservative evaluation requirement, not proof that a minimum-range answer needs all three passages when the source explicitly states which encounter was closest. This limits conclusions from the adoption gate and aggregate context counts.

## Candidate selection versus candidate retrieval

In the five-passage cold run, NEAR Shoemaker's launch source was present in the fused candidate pool but fell below the primary cutoff. Coverage selected all three requested missions; quote validation then rejected the draft as described above.

Magellan's mass did not reach the 20-candidate pool for the three-mass question. Reranking that same pool cannot restore it. This motivates a separately scoped experiment with field-specific candidate retrieval, rather than treating a larger reranker or field ordering as a complete solution.

For the two-earthquake question, two passages selected Nepal's response metadata and Sumatra's event record. Thus two distinct document IDs did not mean both requested magnitudes were present. Coverage also selected Nepal's actual event record and returned both exact `/properties/mag` values. Field-level source support matters more than counting documents alone.

All source assertions here are against the frozen [NASA/USGS snapshots and attribution](../../evals/coverage/sources.json). Model assessment reasons are descriptions of returned outputs, not verified explanations of internal model reasoning.
