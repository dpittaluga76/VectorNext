# Development cases needing a decision

Internal review, 2026-10-16. These are recommendations, not applied label changes. Case numbers refer to the unchanged development request order. See [the answer sheet](../reviews/t39-review-decisions.md).

## Case 004 — D1

**Question:** Which job does not require that the member be a citizen of the UK?

**Original proposal:** insufficient_evidence; [].

**Finding:** MSP qualifications explicitly allow several non-UK citizenships. An MSP is a plausible supported answer to the question; the insufficient-evidence label is suspect.

**Recommendation:** Relabel supported with the MSP qualification passage, subject to Daniel confirming this reading.

**Source:** [squad-43f328b69db49d2e.txt](../../tmp/t39-v2-review-proposal-v2/development/documents/squad-43f328b69db49d2e.txt) · Case ID: `squad-5ad0440a77cf76001a686f4b`.

## Case 011 — D3

**Question:** Up to how many samples do they experiment with?

**Original proposal:** supported; ["535", "we considered 4 different proportions i.e., INLINEFORM0 , INLINEFORM1 , INLINEFORM2 and INLINEFORM3 of the training data to train the classifier"].

**Finding:** Human alternatives disagree: 535 utterances in the whole database versus four training proportions with unresolved INLINEFORM placeholders. Experiments use subsets; a database total is not clearly the maximum experimental sample count.

**Recommendation:** Keep as a stress/adjudication case until the intended sample population is fixed; do not accept the alternatives interchangeably.

**Source:** [qasper-1712.05608.txt](../../tmp/t39-v2-review-proposal-v2/development/documents/qasper-1712.05608.txt) · Case ID: `qasper-352bc6de5c5068c6c19062bad1b8f644919b1145`.

## Case 015 — D3

**Question:** How well did the baseline perform?

**Original proposal:** supported; ["accuracy of 30.3% on single sentences and 0.3 on complete paragraphs"].

**Finding:** The question does not specify which baseline. The cited best baseline is NO-MOVE; the sentence says 30.3% on sentences and 0.3 on paragraphs without a percent sign for the latter.

**Recommendation:** Retain the literal statement only in a qualified diagnostic track until baseline and percentage semantics are approved; do not silently convert 0.3 to 30%.

**Source:** [qasper-1909.08970.txt](../../tmp/t39-v2-review-proposal-v2/development/documents/qasper-1909.08970.txt) · Case ID: `qasper-bd419f4094186a5ce74ba6ac1622b24e29e553f4`.

## Case 017 — D3

**Question:** What is their ROUGE score?

**Original proposal:** insufficient_evidence; [].

**Finding:** ROUGE variant and dataset are unspecified; results refer to a table whose cells are absent from the supplied text. Captions name R1/R2/RL and multiple datasets.

**Recommendation:** Separate as an underspecified/missing-table stress case, not a clean text-only missing-fact negative.

**Source:** [qasper-1802.08636.txt](../../tmp/t39-v2-review-proposal-v2/development/documents/qasper-1802.08636.txt) · Case ID: `qasper-5152b78f5dfee26f1b13f221c1405ffa9b9ba3a4`.

## Case 031 — D2

**Question:** What is one of the reason that US production has been held responsible for recessions and lower economic growth?

**Original proposal:** supported; ["distribution and price disruptions", "reduced productivity"].

**Finding:** The paragraph lists reduced productivity as an effect of disruptions, while the question asks for a reason. The human alternative reduced productivity reverses that relation.

**Recommendation:** Keep distribution and price disruptions; reject reduced productivity as a causal answer.

**Source:** [squad-b6860aac55af75d7.txt](../../tmp/t39-v2-review-proposal-v2/development/documents/squad-b6860aac55af75d7.txt) · Case ID: `squad-57261f9f271a42140099d4a9`.

## Case 046 — D3

**Question:** What is the architecture of the model?

**Original proposal:** supported; ["one-layer CNN structure from previous works BIBREF22 , BIBREF4", " one-layer CNN"].

**Finding:** The one-layer CNN is specifically the feature encoder. The full model also includes a fully connected softmax classifier; a question about the whole architecture is broader than the sole labelled component.

**Recommendation:** Adjudicate the intended architecture facts before treating a short encoder label as the exhaustive correct answer.

**Source:** [qasper-1809.00530.txt](../../tmp/t39-v2-review-proposal-v2/development/documents/qasper-1809.00530.txt) · Case ID: `qasper-b46c0015a122ee5fb95c2a45691cb97f80de1bb6`.

## Case 062 — D3

**Question:** What was the State income taxes, net of federal tax benefit in 2020?

**Original proposal:** supported; ["22"].

**Finding:** The first column ends January 3, 2020 but the narrative calls it fiscal 2019. The question says in 2020, without fiscal/calendar qualification.

**Recommendation:** Keep as a date-scope stress case until the year-ended convention is approved.

**Source:** [tatqa-62425e9b-b7de-4d31-9565-1042ad9e4926.json](../../tmp/t39-v2-review-proposal-v2/development/documents/tatqa-62425e9b-b7de-4d31-9565-1042ad9e4926.json) · Case ID: `tatqa-e700aa58-2454-4af7-84fe-965254c07275`.

## Case 064 — D3

**Question:** What was the expected term in 2019 in years?

**Original proposal:** supported; ["0.6"].

**Finding:** The proposed 0.6 is in the January 31, 2020 column; February 1, 2019 contains 0.8. No supplied passage establishes that the first column should answer the question in 2019.

**Recommendation:** Do not silently choose 0.6 or 0.8; adjudicate fiscal-year scope or separate the case.

**Source:** [tatqa-89cf13a2-6d08-48be-a45d-2346422d5c38.json](../../tmp/t39-v2-review-proposal-v2/development/documents/tatqa-89cf13a2-6d08-48be-a45d-2346422d5c38.json) · Case ID: `tatqa-ec066127-4046-4b2f-9332-de14851c6868`.

## Case 065 — D3

**Question:** Who has elected the President of Warsaw since 1990?

**Original proposal:** supported; ["the City council", "City council"].

**Finding:** The source says the city council elected the president from 1990, but also says all citizens elect the president since 2002. The unqualified since-1990 question spans both regimes.

**Recommendation:** Separate as temporal ambiguity unless a multi-period answer is explicitly approved.

**Source:** [squad-c1dd7eef882a11ae.pdf](../../tmp/t39-v2-review-proposal-v2/development/documents/squad-c1dd7eef882a11ae.pdf) · Case ID: `squad-57338255d058e614000b5c10`.

## Case 067 — D1

**Question:** How many members are on the Miasta City Council?

**Original proposal:** insufficient_evidence; [].

**Finding:** The scoped paragraph names Warsaw City Council (Rada Miasta) and states that it comprises 60 members. The question uses Miasta City Council.

**Recommendation:** Relabel supported with 60, subject to confirming the council-name interpretation.

**Source:** [squad-2489f62cd003d65a.txt](../../tmp/t39-v2-review-proposal-v2/development/documents/squad-2489f62cd003d65a.txt) · Case ID: `squad-5ad4f4d95b96ef001a10a793`.

## Case 072 — D2

**Question:** What was Joseph Haas arrested for?

**Original proposal:** supported; ["sending an email to the Lebanon, New Hampshire city councilors", "sending an email", "sending an email to the Lebanon"].

**Finding:** One human alternative ends at sending an email to the Lebanon, cutting off New Hampshire city councilors. The source alleges a threatening email, not just an unexplained geographic fragment.

**Recommendation:** Drop the clipped recipient alternative and approve a complete fact description retaining the allegation qualifier and source context.

**Source:** [squad-4567ab556bfdf34c.txt](../../tmp/t39-v2-review-proposal-v2/development/documents/squad-4567ab556bfdf34c.txt) · Case ID: `squad-5728284e3acd2414000df5cd`.

## Case 073 — D3

**Question:** What background do they have?

**Original proposal:** insufficient_evidence; [].

**Finding:** The standalone pronoun they has no conversation antecedent. The text discusses authors, scholars and participants; author backgrounds are described only broadly.

**Recommendation:** Separate as an ambiguous-reference case; do not count it as a clean absence-of-evidence negative.

**Source:** [qasper-1907.01468.txt](../../tmp/t39-v2-review-proposal-v2/development/documents/qasper-1907.01468.txt) · Case ID: `qasper-975e60535724f4149c7488699a199ba2920a062c`.

## Case 074 — D1

**Question:** What features are used?

**Original proposal:** insufficient_evidence; [].

**Finding:** The title, abstract and method explicitly identify TF-IDF features; the public annotation nevertheless says unanswerable.

**Recommendation:** Relabel supported with TF-IDF features and the feature-extraction method passage.

**Source:** [qasper-1903.07406.txt](../../tmp/t39-v2-review-proposal-v2/development/documents/qasper-1903.07406.txt) · Case ID: `qasper-1eef2d2c296fdd10b08bf7b4ff7792cccf177d3b`.

## Case 076 — D3

**Question:** What are engines using four expansion cylinders known as?

**Original proposal:** insufficient_evidence; [].

**Finding:** The source distinguishes expansion stages from cylinders and describes four-cylinder triple-expansion engines. Four cylinders do not uniquely identify quadruple expansion.

**Recommendation:** Treat as ambiguous terminology; do not substitute four stages for four cylinders.

**Source:** [squad-198dfa258b2e70a8.txt](../../tmp/t39-v2-review-proposal-v2/development/documents/squad-198dfa258b2e70a8.txt) · Case ID: `squad-5ad41b12604f3c001a4004fc`.

## Case 079 — D3

**Question:** In what year did the second wave of the plague hit the Netherlands?

**Original proposal:** insufficient_evidence; [].

**Finding:** The text associates a distinct Low Countries outbreak with 1350 but phrases a second wave as a hypothesis. This can support a qualified date reading, while the source label is unanswerable.

**Recommendation:** Separate until the geographic and hypothetical-language interpretation is adjudicated.

**Source:** [squad-a2bd00ba9ec7b403.pdf](../../tmp/t39-v2-review-proposal-v2/development/documents/squad-a2bd00ba9ec7b403.pdf) · Case ID: `squad-5a2ecb43a83784001a7d248c`.

## Case 081 — D2

**Question:** How many users do they look at?

**Original proposal:** supported; ["22,880 users", "20,000"].

**Finding:** The final dataset has 22,880 users. Another passage says over 20,000; accepting exactly 20,000 loses the inequality qualifier.

**Recommendation:** Use 22,880 for an exact count; retain over 20,000 only as an explicitly qualified alternative, never exact 20,000.

**Source:** [qasper-1612.08205.txt](../../tmp/t39-v2-review-proposal-v2/development/documents/qasper-1612.08205.txt) · Case ID: `qasper-692c9c5d9ff9cd3e0ce8b5e4fa68dda9bd23dec1`.

## Case 082 — D3

**Question:** What is the most expensive currency?

**Original proposal:** supported; ["GBP"].

**Finding:** Most expensive currency requires comparing exchange-rate rows; GBP occurs in a cell but is not explicitly labelled the maximum. The source req_comparison flag is false.

**Recommendation:** Move to a comparison stress track, outside the direct-extraction primary denominator.

**Source:** [tatqa-e8877535-8ade-4ba3-aae2-cd4db2b5c59c.json](../../tmp/t39-v2-review-proposal-v2/development/documents/tatqa-e8877535-8ade-4ba3-aae2-cd4db2b5c59c.json) · Case ID: `tatqa-c3f4ec9b-2e21-42fd-950b-2e7b24e4b0b9`.

## Case 088 — D1

**Question:** Who has said that climate models are uncertain?

**Original proposal:** insufficient_evidence; [].

**Finding:** The paragraph explicitly attributes criticism about understated climate-model uncertainty to Richard Lindzen.

**Recommendation:** Relabel supported with the attributed speaker; this reviews source entailment, not climate-model truth.

**Source:** [squad-cdeffc5b021044b2.txt](../../tmp/t39-v2-review-proposal-v2/development/documents/squad-cdeffc5b021044b2.txt) · Case ID: `squad-5a3e3752378766001a0024f7`.

## Case 092 — D3

**Question:** What is the total gross emissions (Scope 1 and 2) for FY18?

**Original proposal:** supported; ["98,725"].

**Finding:** Two FY18 gross-emissions columns exist: UK/Ireland (98,725) and full group including US (143,354). The question omits geographic scope. 98,725 also appears in a net-emissions row.

**Recommendation:** Treat as ambiguous or approve both scope-qualified alternatives; never accept the net-emissions cell as gross-emissions proof.

**Source:** [tatqa-502dd70a-926b-49d7-b236-63855c98e740.json](../../tmp/t39-v2-review-proposal-v2/development/documents/tatqa-502dd70a-926b-49d7-b236-63855c98e740.json) · Case ID: `tatqa-69b61533-e155-408f-b189-5bb0ddfbc274`.

## Case 097 — D2

**Question:** How high are Victoria's alpine regions?

**Original proposal:** supported; ["2,000 m", "almost 2,000 m"].

**Finding:** The source says almost 2,000 m; the bare 2,000 m alternative drops that qualifier. It separately gives a highest-peak height of 1,986 m.

**Recommendation:** Preserve almost in the approved regional-height answer; do not silently substitute a peak height or an exact 2,000 m claim.

**Source:** [squad-68b5149b27e1f7aa.txt](../../tmp/t39-v2-review-proposal-v2/development/documents/squad-68b5149b27e1f7aa.txt) · Case ID: `squad-570d35b7b3d812140066d54d`.

## Case 099 — D3

**Question:** What traditional linguistics features did they use?

**Original proposal:** insufficient_evidence; [].

**Finding:** The text lists lexical, implicit/explicit incongruity, readability and word-count features, while the complete feature table is not supplied. Unanswerability depends on whether a complete fine-grained list is required.

**Recommendation:** Separate pending an explicit completeness rule; do not score every text-supported feature answer as harmful.

**Source:** [qasper-1701.05574.txt](../../tmp/t39-v2-review-proposal-v2/development/documents/qasper-1701.05574.txt) · Case ID: `qasper-4e748cb2b5e74d905d9b24b53be6cfdf326e8054`.

## Case 107 — D2

**Question:** What is the definition of offensive language?

**Original proposal:** supported; [" Most prior work focuses on a different aspect of offensive language such as abusive language BIBREF0 , BIBREF1 , (cyber-)aggression BIBREF2 , (cyber-)bullying BIBREF3 , BIBREF4 , toxic comments INLINEFORM0 , hate speech BIBREF5 , BIBREF6 , BIBREF7 , BIBREF8 , BIBREF9 , BIBREF10 , and offensive language BIBREF11 . Prior work has focused on these aspects of offensive language in Twitter BIBREF3 , BIBREF7 , BIBREF8 , BIBREF11 , Wikipedia comments, and Facebook posts BIBREF2 ."].

**Finding:** The human span lists related research rather than defining the term. A separate Level A paragraph explicitly defines offensive posts via profanity or targeted offense.

**Recommendation:** Use the explicit operational definition with its own proof as a documented adaptation; retain the original human label separately.

**Source:** [qasper-1902.09666.txt](../../tmp/t39-v2-review-proposal-v2/development/documents/qasper-1902.09666.txt) · Case ID: `qasper-5a8cc8f80509ea77d8213ed28c5ead501c68c725`.

## Case 109 — D1

**Question:** How is information charged differently for Circuit Switching?

**Original proposal:** insufficient_evidence; [].

**Finding:** The scoped paragraph directly contrasts circuit switching billed by connection time with packet switching billed by information transmitted.

**Recommendation:** Relabel supported with the connection-time charging rule and the contrast passage.

**Source:** [squad-b432d2704c4cc56e.txt](../../tmp/t39-v2-review-proposal-v2/development/documents/squad-b432d2704c4cc56e.txt) · Case ID: `squad-5a55068b134fea001a0e180f`.

## Case 110 — D3

**Question:** Inter-network routing was what kind of system?

**Original proposal:** insufficient_evidence; [].

**Finding:** The text calls AppleTalk plug-n-play and says it configures inter-network routing. The question names routing rather than AppleTalk, leaving the intended subject uncertain.

**Recommendation:** Separate pending subject disambiguation; preserve the original question.

**Source:** [squad-a2c1c2176d3c262a.txt](../../tmp/t39-v2-review-proposal-v2/development/documents/squad-a2c1c2176d3c262a.txt) · Case ID: `squad-5a668b1df038b7001ab0bf8a`.

## Case 111 — D3

**Question:** What delivery message was used

**Original proposal:** supported; ["by store and forward switching", "packets", "store and forward switching"].

**Finding:** The question is incomplete, and human alternatives mix a data unit (packets) with a delivery mechanism (store and forward switching).

**Recommendation:** Separate pending clarification; do not treat unit and mechanism as equivalent facts.

**Source:** [squad-ea95fc496ddc121e.txt](../../tmp/t39-v2-review-proposal-v2/development/documents/squad-ea95fc496ddc121e.txt) · Case ID: `squad-57263677ec44d21400f3dc4c`.
