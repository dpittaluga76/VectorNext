# D2 development adjudication v1.1

Recorded 2026-10-16. Four source-verified amendments are ready for successor adaptation; **107 remains pending two independent source reviews**. This is a partial amendment, not benchmark approval or an execution freeze. [Machine-readable decisions and offsets](t39-d2-adjudication-v1.1.json) · [Numeric policy](../../evals/measurement/numeric-scoring-v1.1.md) · [Systematic audit](t39-d2-alternative-audit-v1.1.md).

The five candidates came from internal source screening before benchmark inference, not model disagreement. Daniel approved their directions conditionally from the review table; the implementation agent checked the exact scoped documents. These records do not constitute two independent reviews. Original annotations do not explain their rationale.

| Case | Change class | Decision |
| --- | --- | --- |
| 031 | Alternative removed | Drop reduced productivity; retain the complete cause set and permit one requested cause. |
| 072 | Alternative removed; complete qualified span added | Require alleged conduct with the recipients and full threat wording. |
| 081 | Alternative removed + scoring rule added | Exact 22,880; qualified over 20,000 is imprecise only; bare 20,000 wrong. |
| 097 | Scoring rule added | Almost/nearly/just under is faithful; about is imprecise only; bare 2,000 m wrong. |
| 107 | Gold replacement proposed | Level A source checks pass; replacement/rubric await two independent reviews. |

No original source, question, annotation, capture or score was overwritten. The original v1, D1-only, D2-only and combined reviewed v1.1 views must be reported on identical captures, with denominators and exclusions explicit. **No scores exist for this proposal yet.** The old 16/28-question reports remain unchanged and are not this dataset.

## The passages requested: 081

Paper: **Predicting the Industry of Users on Social Media**, QASPER paper `1612.08205`. Question: “How many users do they look at?”

> First, we build a large, industry-annotated dataset that contains over 20,000 blog users.

> The resulting dataset consists of 22,880 users, 41,094 blogs, and 561,003 posts.

Both concern the same U.S. Blogger industry dataset. The Dataset section explains profile scraping, blog collection and category consolidation before the exact count. No separate dates or snapshots are given for the two statements; we cannot independently verify an unstated collection date. The subsequent 17,880 / 2,500 / 2,500 split agrees with 22,880 total users. The rounded introduction is compatible with, and less precise than, the total.

## The passages requested: 107

Paper: **Predicting the Type and Target of Offensive Posts in Social Media**, QASPER paper `1902.09666`. Question: “What is the definition of offensive language?”

> Level A discriminates between offensive (OFF) and non-offensive (NOT) tweets.

> Offensive (OFF): We label a post as offensive if it contains any form of non-acceptable language (profanity) or a targeted offense, which can be veiled or direct. This category includes insults, threats, and posts containing profane language or swear words.

The authors introduce their own OLID hierarchy and say “We label.” Level B classifies offense type; Level C classifies its target. The question does not ask specifically about targeted insults or hate speech. This supports the proposed Level A scope, but it does not replace the two reviews requested for a gold replacement. The current public answer remains intact.

### Proposed manual rubric (not activated)

- Identify this paper's Level A operational definition, rather than presenting a universal definition.
- Include non-acceptable/profane language OR targeted offense as alternative sufficient branches; do not require both.
- Preserve that targeted offense can be veiled or direct.
- Insults/threats/swearing are optional examples; do not require an exact long quotation.
- Reject definitions that require a target in every case, restrict all offense to group hate speech, or substitute a survey of prior research.
- Record semantic correctness and source support separately; an exact-match failure is not by itself a wrong definition. No LLM judge.

Each reviewer must assess the source independently of the other reviewer’s decision and without model outputs. Use the [review packet](../reviews/t39-case-107-independent-review.md); identities and decisions are deliberately blank.

## Per-item evidence and offsets

Offsets below are zero-based, half-open UTF-8 byte ranges in the hashed scoped TXT document. Code-point offsets and answer-alias spans are also recorded in JSON. They are not offsets in a model prompt. No evaluation context exists yet; later context sufficiency must be checked separately.

### 031 — user_approved_source_conditions_verified

The question asks for ONE cause. The coordinated source subject covers production, distribution and price disruptions; reduced productivity is an effect. Retain the original distribution/price answer and the complete cause phrase. A single cause may satisfy the question; restored shared-head paraphrases need the explicit D4 mapping, not substring matching.

Source `development/documents/squad-b6860aac55af75d7.txt`; SHA-256 `03cb2784f170548bcb7d5bac5f52461bd00a24b18ac95bd094e47c9bdf136670`.

Bytes `[395, 577)`:

> In the US production, distribution and price disruptions "have been held responsible for recessions, periods of excessive inflation, reduced productivity, and lower economic growth."

### 072 — user_approved_source_conditions_verified

Replace clipped/underqualified alternatives with the complete alleged conduct, including recipients and threat wording. The allegation qualifier must remain explicit in the answer or an approved allegation field; do not assert that the email was sent as an established fact. Field mappings remain subject to D4.

Source `development/documents/squad-4567ab556bfdf34c.txt`; SHA-256 `fd93028701526b473dbe93cb4ded11a23207c124c84b16733c2ee2e9b442c706`.

Bytes `[461, 602)`:

> For example, Joseph Haas was arrested for allegedly sending an email to the Lebanon, New Hampshire city councilors stating, "Wise up or die."

### 081 — user_approved_source_conditions_verified

Same final Blogger industry dataset, summarized approximately in the introduction and specified exactly in Dataset. No different dated snapshot is given. The subsequent split is consistent with 22,880 total users. A qualified lower bound is diagnostic partial support, not primary correctness.

Source `development/documents/qasper-1612.08205.txt`; SHA-256 `d64c578125080898aae9b3cdb7bd01ccea8faad8f6ed3bd195569a49d36c9c6c`.

Bytes `[10795, 10875)`:

> The resulting dataset consists of 22,880 users, 41,094 blogs, and 561,003 posts.

Bytes `[2803, 2892)`:

> First, we build a large, industry-annotated dataset that contains over 20,000 blog users.

Bytes `[11075, 11192)`:

> The sizes of these sets are 17,880, 2,500, and 2,500 users, respectively, with users randomly assigned to these sets.

### 097 — user_approved_source_conditions_verified

The quantity is the regional upper extent of alpine areas. Preserve the below-bound approximation. About is separately imprecise, not full credit. Mount Bogong's 1,986 m is a different, explicitly named peak quantity.

Source `development/documents/squad-68b5149b27e1f7aa.txt`; SHA-256 `ca0f7b7018127b2736fe74e8ea343545834b32796fc74beb48cde30324c80067`.

Bytes `[158, 296)`:

> the snow-covered Victorian alpine areas which rise to almost 2,000 m (6,600 ft), with Mount Bogong the highest peak at 1,986 m (6,516 ft).

### 107 — pending_two_independent_reviews

Source checks support Level A: the question asks for the general definition; the paper says We label and explicitly separates Level A from type/target Levels B/C. Two independent source reviews must approve the replacement and rubric before activation. No active replacement is made by this artifact.

Source `development/documents/qasper-1902.09666.txt`; SHA-256 `8b40b29eabc1d84c3a09a9512910aac0ae394df97d6552bd8e30c9f31261a7f2`.

Bytes `[5909, 6112)`:

> In the OLID dataset, we use a hierarchical annotation model split into three levels to distinguish between whether language is offensive or not (A), and type (B) and target (C) of the offensive language.

Bytes `[6264, 6341)`:

> Level A discriminates between offensive (OFF) and non-offensive (NOT) tweets.

Bytes `[6415, 6672)`:

> Offensive (OFF): We label a post as offensive if it contains any form of non-acceptable language (profanity) or a targeted offense, which can be veiled or direct. This category includes insults, threats, and posts containing profane language or swear words.

Bytes `[6721, 6842)`:

> Level B categorizes the type of offense and two labels are used: targeted (TIN) and untargeted (INT) insults and threats.

Bytes `[7171, 7276)`:

> Level C categorizes the targets of insults and threats as individual (IND), group (GRP), and other (OTH).

## Provenance and remaining work

SQuAD 2.0 excerpts are derived from its Wikipedia passages under CC BY-SA 4.0; QASPER paper excerpts/adaptations retain their public dataset provenance under CC BY 4.0. See the [pinned source ledger](../../evals/measurement/public-sources.json) and the original IDs/hashes in the JSON. Modified annotations are identified above; no public dataset file was edited.

D3–D7, the five new audit leads, final typed/proof mappings, 107’s independent reviews and independent benchmark approval/custody remain open. Numeric aliases are review rules; runtime semantic scorer integration remains pending. The sealed 60 questions and the original holdout were not opened.

## Verification and review freeze

All **30 Python measurement tests passed**, including six scanner tests. Reverified **116 development members**, **19 D2 evidence/answer spans**, the unchanged D1 amendment/policy and original source/label/request hashes. Diff whitespace checks passed. No inference, service changes or sealed-data reads were performed. [Verification record](t39-d2-verification-v1.1.json) · [Frozen review list and artifact hashes](t39-d2-review-freeze-v1.1.json).

The freeze binds the five D2 directions and their current approval states; it is **not an execution freeze**. Case 107 is still pending, and the five newly surfaced leads remain separate. Subsequent decisions need a new amendment rather than silently altering this snapshot.
