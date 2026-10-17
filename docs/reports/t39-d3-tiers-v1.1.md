# D3: typed exclusions and three development views

Declared 2026-10-16 before benchmark inference. [Policy and reserve procedure](../../evals/measurement/tiers-v1.1.md) · [Case evidence, exact source pointers and full roster](t39-d3-tiers-v1.1.json).

Daniel approved separating the 15 cases, requested a defect taxonomy and a separate derived tier, then explicitly waived the proposed two-reviewer blind screening pass. This is **internal, non-blind review**. No model outputs were used, no new model runs occurred, no replacement candidates were inspected/drawn, and no sealed content was opened. The separately recorded case-107 replacement review has not been attested by this waiver.

## Classification of all 15

Each has exactly one primary reason; secondary issues remain in JSON. A derivation is a capability distinction, not a broken question.

| Primary reason | Cases | View |
| --- | --- | --- |
| Scope/period ambiguous | 011, 046, 062, 064, 065, 092 | Stress |
| Unit/format ambiguous | 015 | Stress |
| Question incomplete / unbound referent | 073, 111 | Stress |
| Required source content unavailable | 017, 099 | Stress, acquisition diagnosis |
| Premise/entity/category ambiguous | 076, 079, 110 | Stress |
| Comparison required | 082 | Derived/inference |

D1 uses this same taxonomy: **004 and 088 → derived/inference; 067 → stress**. Literal 074/109 remain primary candidates. D1/D2 original files and their approved meanings are preserved.

## Three views, with n

| Development view | n | TXT | PDF | JSON/table | Status |
| --- | ---: | ---: | ---: | ---: | --- |
| Primary: direct extraction and clean negatives | 102 | 52 | 17 | 33 | Provisional membership; no captures/scores |
| Derived/inference | 3 | 2 | 0 | 1 | Provisional membership; no captures/scores |
| Stress/adjudication | 15 | 10 | 2 | 3 | Provisional membership; no captures/scores |
| Original public v1, unchanged | 120 | 64 | 19 | 37 | 83 supported / 37 unanswerable; no captures/scores |

The primary candidates contain **76 reviewed-answerable and 26 clean-negative cases** (25.5% negatives). The stress cases retain eight originally supported, six originally unanswerable, and D1’s ambiguous 067. The derived cases are 004/082/088. Primary includes six unresolved specific review items (010/034/047/053/071/107), plus outstanding D4–D7 mappings; membership does not approve their gold or permit a run.

Across D1/D3, primary loses **18/120 cases**: 12/64 TXT (18.8%), 2/19 PDF (10.5%) and 4/37 JSON/table (10.8%). By source it loses 6/21 QASPER (28.6%), 8/62 SQuAD (12.9%) and 4/37 TAT-QA (10.8%). The largest proportional loss is scientific QASPER prose, not tables. **33 of 37 table cases remain**, and the D2 numeric-answer inventory falls from **51 to 45**. Table extraction remains represented, but the corpus is changed and all remaining table proof/context concerns persist.

For orientation only, an ordinary Wilson 95% interval at a hypothetical 51/102 correct is about 40.5–59.5% (±9.5 points); this is not an observed score or a guarantee under source-family dependence. Report real outcome counts and paired/family-aware uncertainty after captures exist. The unopened 60 sealed cases have no tier assignment in this report; no whole-benchmark quota compliance is claimed. Historical 16/28-question scores are unrelated data and remain unchanged.

## 082 is a supported comparison

Question: **What is the most expensive currency?** The source narrative says it is presenting average currency exchange rates and explicitly describes USD-INR. The three table rows use the same year-column unit; do not compare weight percentages or revenue growth.

| Currency | FY2019 average rate | FY2018 average rate |
| --- | ---: | ---: | ---: |
| USD | 70.07 | 64.49 |
| GBP | 91.60 | 86.05 |
| EUR | 80.82 | 76.16 |

**GBP** is highest in both years. The answer requires comparing three listed rates; it is not an unsupported comparison of unrelated nominal currency amounts. The damaged-looking backtick unit marker is preserved in the raw headers; the narrative supplies the INR context. No external rates or currency conversion were used. This does not add comparison support to the application.

## Missing source versus extraction loss

- **017:** raw QASPER references `9-Table2-1.png`; its caption identifies CNN/DailyMail and R1/R2/RL results. Cell payloads are not in the retained JSON. Every supplied paragraph and caption survives TXT adaptation.
- **099:** raw QASPER references `6-Table2-1.png`, captioned as the complete feature set. The prose provides some categories, but the complete table payload is absent from the retained package; its caption survives adaptation.
- The source papers may supply the answers in the referenced images; those images were not acquired/inspected. This is an **acquisition limitation**, not proof the papers lack the information and not a demonstrated VectorNext parser failure. A reviewed source repair needs a new source version and a scope recheck.
- Rechecked all **19 development QASPER documents** against raw title/abstract/sections/paragraphs/captions, all **32 TAT-QA documents** against original cells/paragraphs, and all **62 SQuAD question contexts** against the raw dataset. No supplied text/cells were dropped by these adapters. All **116 development member hashes** still match.
- TAT-QA’s repeated first-row-only headers can omit necessary context from a retrieved record even though the complete document retains every row. That D5 defect is distinct from source absence. No application ingestion has yet run for this proposal, so application-stage extraction/retrieval loss is unmeasured.

## Stress behavior, not single-answer accuracy

Use the dated policy’s separate fields: recognizes the issue; states an assumption; gives source-supported conditional answers; avoids unsupported certainty. Record yes/no/not-observable/not-applicable and exact response evidence, including failures. A generic refusal is not automatically full recognition. Do not merge behavior dimensions into an accuracy score.

For 064 the conditional facts are **0.6 years, year ended January 31, 2020**, versus **0.8 years, year ended February 1, 2019**. The source identifies a VMware employee stock plan; it does not establish the proposed fiscal-2019 convention. For 092, **98,725 tonnes CO2e** is FY18 UK/Ireland and **143,354** is full Group including the US. Name those conditions and cite the gross row plus headers/footnotes.

## Replacements, screening and twins

No reserve registry was frozen, so **no replacements are selected**. The policy fixes seed `t39-d3-reserve-20261016-v1`, original answerability/source/format/structure/question-type strata, a deterministic hash permutation, rejection logging and no relaxation of empty strata. Keep the smaller primary set unless a valid reserve can be established before any candidate inspection. Quotas remain a gate, not a reason to choose attractive examples.

The requested independent blind pass was explicitly waived. The prior 120-case source screen and all-alternative D2 audit remain the review evidence; neither becomes blind or independent by applying taxonomy tags. No fabricated reviewer forms or attestations are added. All 102 primary candidates are still subject to the same dated rules, with unresolved issues visible. Disambiguated twins are documented as a possible new-ID, same-family extension, but **none is created or counted** here.

## Evidence for every D3 item

JSON pointers identify original string values. TXT offsets are half-open UTF-8 bytes; for PDF cases, text offsets refer to the retained source paragraph, not PDF binary positions. Source hashes are in the JSON report.

### 011 — scope_or_period_ambiguous

**Question:** Up to how many samples do they experiment with?

Database population, experimental subset and training proportion are different requested quantities; the question does not select one.

Source text bytes `[8741, 9681)`:

> The standard Berlin speech emotion database (EMO-DB) [18] consisting of 535 utterances corresponding to 7 different emotions is considered for the task of emotion classification. Each utterance is represented by a 19-dimensional feature vector obtained by using the feature selection algorithm from WEKA toolkit [19] on the 384-dimensional utterance level feature vector obtained using openSMILE toolkit [20]. For two class classification, we considered the two most confusing emotion pairs i.e., (Neutral,Sad) and (Anger, Happy). Data corresponding to Speech/Music classification (60 speech and 60 music samples) and Neutral/Sad classification (79 neutral and 62 sad utterances) is balanced whereas Anger/Happy classification task has data imbalance, with anger forming the majority class (127 samples) and happy forming the minority class (71 samples). Therefore, we show the performance of s2sL on both, balanced and imbalanced datasets.

Source text bytes `[9683, 10700)`:

> All experimental results are validated using 5-fold cross validation (80% of data for training and 20% for testing in each fold). Further, to analyze the effectiveness of s2sL in low resource scenarios, different proportions of training data, within each fold, are considered to train the system. For this analysis, we considered 4 different proportions i.e., INLINEFORM0 , INLINEFORM1 , INLINEFORM2 and INLINEFORM3 of the training data to train the classifier. For instance, INLINEFORM4 means considering only half of the original training data to train the classifier, and INLINEFORM5 means considering the complete training data. 5-fold cross validation is considered for all data proportions. Accuracy (in %) is used as a performance measure for balanced data classification tasks (i.e., Speech/Music classification and Neutral/Sad emotion classification), whereas the more preferred INLINEFORM6 measure [21] is used as a measure for imbalanced data classification task (i.e., Anger/Happy emotion classification).

### 015 — unit_or_format_ambiguous

**Question:** How well did the baseline perform?

The cited baseline gives 30.3% for sentences and bare 0.3 for paragraphs. Preserve the unit uncertainty; never infer 30%.

Source text bytes `[12525, 12935)`:

> Table TABREF8 shows the results for the baseline models as well as the HUMAN measured performance on the task. The human performance provides an upper bound for the RUN task performance, while the simple baselines provide lower bounds. The best baseline model is NO-MOVE, reaching an accuracy of 30.3% on single sentences and 0.3 on complete paragraphs. For the HUMAN case, paragraph accuracy reaches above 80.

### 017 — source_content_unavailable

**Question:** What is their ROUGE score?

ROUGE table cells are not in the retained text package; metric variant and dataset are also unspecified.

Source text bytes `[20501, 20886)`:

> Table 2: Results on the CNN and DailyMail test sets. We report ROUGE-1 (R1), ROUGE-2 (R2), and ROUGE-L (RL) F1 scores. Extractive systems are in the first block and abstractive systems in the second. Table cells are filled with — whenever results are not available. Models marked with ∗ are not directly comparable to ours as they are based on an anonymized version of the dataset.

### 046 — scope_or_period_ambiguous

**Question:** What is the architecture of the model?

The labelled one-layer CNN is the feature encoder; the paper also specifies a fully connected softmax classifier, so whole architecture versus component is unresolved.

Source text bytes `[8813, 9471)`:

> For the proposed model, we denote INLINEFORM0 parameterized by INLINEFORM1 as a neural-based feature encoder that maps documents from both domains to a shared feature space, and INLINEFORM2 parameterized by INLINEFORM3 as a fully connected layer with softmax activation serving as the sentiment classifier. We aim to learn feature representations that are domain-invariant and at the same time discriminative on both domains, thus we simultaneously consider three factors in our objective: (1) minimize the classification error on the labeled source examples; (2) minimize the domain discrepancy; and (3) leverage unlabeled data via semi-supervised learning.

Source text bytes `[16191, 17065)`:

> We have left the feature encoder INLINEFORM0 unspecified, for which, a few options can be considered. In our implementation, we adopt a one-layer CNN structure from previous works BIBREF22 , BIBREF4 , as it has been demonstrated to work well for sentiment classification tasks. Given a review document INLINEFORM1 consisting of INLINEFORM2 words, we begin by associating each word with a continuous word embedding BIBREF23 INLINEFORM3 from an embedding matrix INLINEFORM4 , where INLINEFORM5 is the vocabulary size and INLINEFORM6 is the embedding dimension. INLINEFORM7 is jointly updated with other network parameters during training. Given a window of dense word embeddings INLINEFORM8 , the convolution layer first concatenates these vectors to form a vector INLINEFORM9 of length INLINEFORM10 and then the output vector is computed by Equation ( EQREF11 ): DISPLAYFORM0

### 062 — scope_or_period_ambiguous

**Question:** What was the State income taxes, net of federal tax benefit in 2020?

The year-ended January 3, 2020 column and narrative fiscal 2019 terminology cannot establish a calendar-2020 amount.

- `/records/1/cells/1` (string): January 3, 2020

- `/records/4/cells/0` (string): State income taxes, net of federal tax benefit

- `/records/4/cells/1` (string): 22

- `/records/19/text` (string): The Company's effective tax rate for fiscal 2019 was favorably impacted primarily by excess tax benefits related to employee stock-based payment transactions and federal research tax credits, partially offset by an increase in valuation allowances arising from foreign withholding tax and an increase in taxes related to the sale of the commercial cybersecurity business.

### 064 — scope_or_period_ambiguous

**Question:** What was the expected term in 2019 in years?

Bind 0.6 to year-ended January 31, 2020 and 0.8 to February 1, 2019. The supplied source does not name the first fiscal 2019.

- `/records/1/cells/0` (string): VMware Employee Stock Purchase Plan

- `/records/1/cells/1` (string): January 31, 2020

- `/records/1/cells/2` (string): February 1, 2019

- `/records/5/cells/0` (string): Expected term (in years)

- `/records/5/cells/1` (string): 0.6

- `/records/5/cells/2` (string): 0.8

### 065 — scope_or_period_ambiguous

**Question:** Who has elected the President of Warsaw since 1990?

The source changes from City council since 1990 to all Warsaw citizens since 2002; a timeless single actor is incomplete.

Source text bytes `[0, 763)`:

> The mayor of Warsaw is called President. Generally, in Poland, the mayors of bigger cities are called presidents – i.e. such cities, which have over 100,000 people or these, where already was president before 1990. The first Warsaw President was Jan Andrzej Menich (1695–1696). Between 1975 and 1990 the Warsaw Presidents was simultaneously the Warsaw Voivode. Since 1990 the President of Warsaw had been elected by the City council. In the years of 1994–1999 the mayor of the district Centrum automatically was designated as the President of Warsaw: the mayor of Centrum was elected by the district council of Centrum and the council was elected only by the Centrum residents. Since 2002 the President of Warsaw is elected by all of the citizens of Warsaw.

### 073 — question_incomplete

**Question:** What background do they have?

Standalone they has no unique antecedent; authors, scholars and participants are discussed with no supplied conversation history.

Source text bytes `[510, 680)`:

> Still, given our diversity of disciplinary backgrounds and research practices, we hope to capture a range of ideas and identify commonalities that will resonate for many.

### 076 — premise_or_entity_ambiguous

**Question:** What are engines using four expansion cylinders known as?

The question substitutes four cylinders for four expansion stages; the source explicitly also describes a four-cylinder triple-expansion engine.

Source text bytes `[180, 304)`:

> Such engines use either three or four expansion stages and are known as triple and quadruple expansion engines respectively.

Source text bytes `[1080, 1291)`:

> This made the 4-cylinder triple-expansion engine popular with large passenger liners (such as the Olympic class), but this was ultimately replaced by the virtually vibration-free turbine engine.[citation needed]

### 079 — premise_or_entity_ambiguous

**Question:** In what year did the second wave of the plague hit the Netherlands?

The source links Low Countries spread from 1350 to a suggested second wave and possible southern-Netherlands reach; the question asserts a definitive Netherlands second-wave arrival.

Source text bytes `[687, 1223)`:

> Surveys of plague pit remains from the Dutch town of Bergen op Zoom showed the Y. pestis genotype responsible for the pandemic that spread through the Low Countries from 1350 differed from that found in Britain and France, implying Bergen op Zoom (and possibly other parts of the southern Netherlands) was not directly infected from England or France in 1349 and suggesting a second wave of plague, different from those in Britain and France, may have been carried to the Low Countries from Norway, the Hanseatic cities or another site.

### 082 — requires_derivation

**Question:** What is the most expensive currency?

The three currency rows give common INR exchange rates. GBP is the maximum in both listed years; compare rates, not portfolio weights or revenue growth.

- `/records/0/cells/0` (string): Currency

- `/records/0/cells/2` (string): FY 2019 `

- `/records/0/cells/3` (string): FY 2018 `

- `/records/1/cells/0` (string): USD

- `/records/1/cells/2` (string): 70.07

- `/records/1/cells/3` (string): 64.49

- `/records/2/cells/0` (string): GBP

- `/records/2/cells/2` (string): 91.60

- `/records/2/cells/3` (string): 86.05

- `/records/3/cells/0` (string): EUR

- `/records/3/cells/2` (string): 80.82

- `/records/3/cells/3` (string): 76.16

- `/records/10/text` (string): FY 2019 saw volatility in USD-INR, ranging from `64.90 and `74.10, and averaging at `70.07. There was also significant volatility in exchange rates of emerging markets’ currencies. Average currency exchange rates during FY 2019 for the three major currencies are given below:

### 092 — scope_or_period_ambiguous

**Question:** What is the total gross emissions (Scope 1 and 2) for FY18?

FY18 has UK/Ireland and full-Group columns with different gross totals; the question omits geography.

- `/records/2/cells/2` (string): FY18**

- `/records/2/cells/3` (string): FY18***

- `/records/5/cells/0` (string): Total gross emissions (Scope 1 and 2)

- `/records/5/cells/2` (string): 98,725

- `/records/5/cells/3` (string): 143,354

- `/records/13/text` (string): * Our GHG emissions have been calculated using the GHG Protocol Corporate Accounting and Reporting Standard, and emissions factors from DEFRA’s UK government GHG conversion factors for company reporting (where factors have not been provided directly by a supplier). ** UK & Ireland only – comparable with FY19 Group structure. *** Full Group including US business.

### 099 — source_content_unavailable

**Question:** What traditional linguistics features did they use?

Some feature categories are stated, but the complete feature table is only an image reference/caption in the retained package. Do not mistake partial categories for a verified exhaustive list.

Source text bytes `[14504, 15117)`:

> We describe the features used for sarcasm detection in Table . The features enlisted under lexical,implicit incongruity and explicit incongruity are borrowed from various literature (predominantly from joshi2015harnessing). These features are essential to separate sarcasm from other forms semantic incongruity in text (for example ambiguity arising from semantic ambiguity or from metaphors). Two additional textual features viz. readability and word count of the text are also taken under consideration. These features are used to reduce the effect of text hardness and text length on the eye-movement patterns.

Source text bytes `[25353, 25410)`:

> Table 2: The complete set of features used in our system.

### 110 — premise_or_entity_ambiguous

**Question:** Inter-network routing was what kind of system?

The text calls AppleTalk a plug-n-play system; inter-network routing is one configured function, so answering for that function by substituting the whole system is contested.

Source text bytes `[0, 513)`:

> AppleTalk was a proprietary suite of networking protocols developed by Apple Inc. in 1985 for Apple Macintosh computers. It was the primary protocol used by Apple devices through the 1980s and 90s. AppleTalk included features that allowed local area networks to be established ad hoc without the requirement for a centralized router or server. The AppleTalk system automatically assigned addresses, updated the distributed namespace, and configured any required inter-network routing. It was a plug-n-play system.

### 111 — question_incomplete

**Question:** `What delivery message was used `

The unfinished delivery-message question fails to distinguish the message unit (packets) from its delivery mechanism (store and forward).

Source text bytes `[0, 696)`:

> Baran developed the concept of distributed adaptive message block switching during his research at the RAND Corporation for the US Air Force into survivable communications networks, first presented to the Air Force in the summer of 1961 as briefing B-265, later published as RAND report P-2626 in 1962, and finally in report RM 3420 in 1964. Report P-2626 described a general architecture for a large-scale, distributed, survivable communications network. The work focuses on three key ideas: use of a decentralized network with multiple paths between any two points, dividing user messages into message blocks, later called packets, and delivery of these messages by store and forward switching.

## Provenance and remaining work

Adapted excerpts retain SQuAD/Wikipedia CC BY-SA 4.0 and QASPER/TAT-QA CC BY 4.0 provenance; pinned source identifiers and hashes are in the [source ledger](../../evals/measurement/public-sources.json). No original data, label or historical result was changed.

D4–D7, six specific primary review decisions, source families, final typed/proof mappings, sealed custody and whole-benchmark quotas remain unresolved. NuExtract and ranked-five defaults are unchanged. This report is a pre-inference tier amendment, not benchmark completion or independent validation.

## Verification and frozen review record

Reverified **116 development member hashes**, **44 evidence span/pointer bindings**, disjoint/exhaustive 120-case tier membership, the original request/label hashes and all **10 frozen D2 artifacts**. The retained QASPER archive contains JSON datasets, with no image/PDF payloads. Link and whitespace checks passed. [Verification details](t39-d3-verification-v1.1.json) · [Dated policy/report hashes](t39-d3-review-freeze-v1.1.json).

These are source/metadata checks, not inference or independent semantic-validation results. No application code, model setting, production source data or historical score was changed during D3. Preserve this partial review freeze and use a successor for later decisions; it is not an execution approval.
