# Additional accepted-answer review leads

Internal source review, 2026-10-16. These are **questions for Daniel**, not new approved label changes. The D2 five-case list stays separate. Original labels remain unchanged. No model outputs informed these leads.

## 010 — Answer-set completeness

**Question:** Where in Central Asia did the Han Chinese move?

**Original alternatives:** ["Besh Baliq, Almaliq, and Samarqand", "Bukhara"]

The source describes administrators sent to Bukhara and artisans/farmers moved to Besh Baliq, Almaliq and Samarqand. The question does not specify a role or ask for only one location. Decide whether either subset is sufficient or a set is required.

Source: `squad-a652253c010b7743.txt`, SHA-256 `55bbfa9052d82fc2074807e0795fc8957a358974ef289c3f0e19e4e8dbb35f85`.

UTF-8 bytes `[0, 1230)`:

> At the same time the Mongols imported Central Asian Muslims to serve as administrators in China, the Mongols also sent Han Chinese and Khitans from China to serve as administrators over the Muslim population in Bukhara in Central Asia, using foreigners to curtail the power of the local peoples of both lands. Han Chinese were moved to Central Asian areas like Besh Baliq, Almaliq, and Samarqand by the Mongols where they worked as artisans and farmers. Alans were recruited into the Mongol forces with one unit called "Right Alan Guard" which was combined with "recently surrendered" soldiers, Mongols, and Chinese soldiers stationed in the area of the former Kingdom of Qocho and in Besh Balikh the Mongols established a Chinese military colony led by Chinese general Qi Kongzhi (Ch'i Kung-chih). After the Mongol conquest of Central Asia by Genghis Khan, foreigners were chosen as administrators and co-management with Chinese and Qara-Khitays (Khitans) of gardens and fields in Samarqand was put upon the Muslims as a requirement since Muslims were not allowed to manage without them. The Mongol appointed Governor of Samarqand was a Qara-Khitay (Khitan), held the title Taishi, familiar with Chinese culture his name was Ahai

**Decision / intended scope:** _Pending._

## 034 — Baseline phase

**Question:** What was the baseline model?

**Original alternatives:** ["by answering always YES (in batch 2 and 3) "]

The annotated evidence describes always-YES for batches 2/3 and entailment for batch 4. The question does not specify a batch. Decide which baseline/phase is requested before changing the gold.

Source: `qasper-2002.01984.txt`, SHA-256 `8b0de396c735a4a627f059419e2e52b7f7651ceaf3413b5cf8466afb23bcbcea`.

UTF-8 bytes `[25035, 25700)`:

> We started by answering always YES (in batch 2 and 3) to get the baseline performance. For batch 4 we used entailment. Our algorithm was very simple: Given a question we iterate through the candidate sentences and try to find any candidate sentence is contradicting the question (with confidence over 50%), if so 'No' is returned as answer, else 'Yes' is returned. In batch 4 this strategy produced better than the BioAsq baseline performance, and compared to our other systems, the use of entailment increased the performance by about 13% (macro F1 score). We used 'AllenNlp' BIBREF13 entailment library to find entailment of the candidate sentences with question.

**Decision / intended scope:** _Pending._

## 047 — Mechanism completeness

**Question:** How does their model improve interpretability compared to softmax transformers?

**Original alternatives:** ["the attention heads in the proposed adaptively sparse Transformer can specialize more and with higher confidence", "We introduce sparse attention into the Transformer architecture"]

Sparse attention is the method and specialization/confidence the reported benefit. Decide whether the short method-only alternative adequately answers how interpretability improves or needs the explicit mechanism.

Source: `qasper-1909.00015.txt`, SHA-256 `45d8f14a0aec099cf331e08c35a3930e910a4d250b5cda1c3a771d3ec049d369`.

UTF-8 bytes `[27060, 27449)`:

> In particular, we analyzed how the attention heads in the proposed adaptively sparse Transformer can specialize more and with higher confidence. Our adaptivity strategy relies only on gradient-based optimization, side-stepping costly per-head hyper-parameter searches. Further speed-ups are possible by leveraging more parallelism in the bisection algorithm for computing $\alpha $-entmax.

UTF-8 bytes `[3219, 3358)`:

> We introduce sparse attention into the Transformer architecture, showing that it eases interpretability and leads to slight accuracy gains.

UTF-8 bytes `[6188, 6804)`:

> The softmax mapping (Equation DISPLAY_FORM8) is elementwise proportional to $\exp $, therefore it can never assign a weight of exactly zero. Thus, unnecessary items are still taken into consideration to some extent. Since its output sums to one, this invariably means less weight is assigned to the relevant items, potentially harming performance and interpretability BIBREF18. This has motivated a line of research on learning networks with sparse mappings BIBREF19, BIBREF20, BIBREF21, BIBREF22. We focus on a recently-introduced flexible family of transformations, $\alpha $-entmax BIBREF23, BIBREF14, defined as:

**Decision / intended scope:** _Pending._

## 053 — Label specificity

**Question:** What are labels in car speak language dataset?

**Original alternatives:** ["car ", "the car"]

The paper says labels identify the car model, ignoring its year. Decide whether bare car is a sufficient categorical label or too underspecified; do not confuse model, manufacturer and individual vehicle.

Source: `qasper-2002.02070.txt`, SHA-256 `af7a772e957a12d20bc406f9c33e264815864c757229720464dd23fcb30b8a4d`.

UTF-8 bytes `[8363, 8772)`:

> We represent each review as a vector of TF-IDF scores for each word in the review. The length of this vector is $10,867$. We label each review vector with the car it reviews. We ignore the year of the car being reviewed and focus specifically on the model (i.e Acura ILX, not 2013 Acura ILX). This is because there a single model of car generally retains the same characteristics over time BIBREF11, BIBREF12.

UTF-8 bytes `[6702, 7187)`:

> Our data set contains $3,209$ reviews about 553 different cars from 49 different car manufacturers. In order to accomplish our goal of translating and classifying car-speak we need to filter our data set so that we only have the most relevant terms. We then need to be able to weight each word in each review, so that we can determine the most relevant ideas in each document for the purpose of classification. Finally, we need to train various classification models and evaluate them.

**Decision / intended scope:** _Pending._

## 071 — Question premise

**Question:** What type of punishment is sometimes offered to civil disobedients?

**Original alternatives:** ["plea bargain", "plead guilty to one misdemeanor count and receive no jail time"]

A plea bargain is the described agreement and no jail time its offered outcome. The question calls this a type of punishment. Decide whether to retain that colloquial reading or flag the wording.

Source: `squad-a0c037e30597c9f0.txt`, SHA-256 `829e809f79e6cd89a4bf8d645fa85c1b0bf92b9d6362547ad071e708ecc99593`.

UTF-8 bytes `[0, 696)`:

> Sometimes the prosecution proposes a plea bargain to civil disobedients, as in the case of the Camden 28, in which the defendants were offered an opportunity to plead guilty to one misdemeanor count and receive no jail time. In some mass arrest situations, the activists decide to use solidarity tactics to secure the same plea bargain for everyone. But some activists have opted to enter a blind plea, pleading guilty without any plea agreement in place. Mohandas Gandhi pleaded guilty and told the court, "I am here to . . . submit cheerfully to the highest penalty that can be inflicted upon me for what in law is a deliberate crime and what appears to me to be the highest duty of a citizen."

**Decision / intended scope:** _Pending._
