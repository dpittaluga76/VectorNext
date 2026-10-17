# T39 D6: development source families and custodian protocol

Review date: **2026-10-17**. D6's five amendments are recorded and the development trace/tools are implemented. **Cross-split verification remains pending.** No sealed material or T39 model outputs were used. No inference, source/gold rewrite, replacement draw, service change or final execution freeze occurred.

## Coverage and confidence

All **102 provisional primary cases** have trace records. **98 have established identities** at the stated scope: 25 tier A public-report matches and 73 tier B pinned article/paper or explicit supplied-company identities. **Four remain tier C candidates**; they are not certified families. Tier U has zero cases, but candidate and unresolved lineage still count as uncertainty.

This means **source identity traced for 98/102; candidate-only for 4/102; cross-split separation verified for 0/102, pending the custodian**. It does not mean zero collisions. Source identity is weaker than a claim that no related company, republication or copied disclosure exists elsewhere.

The full exposure ledger includes all **120 development cases**, with 26 A, 89 B and five C records. The custodian input contains **69 development family keys**, including candidate keys and derived/stress exposure. It contains no question, answer or source text. Sealed candidate count remains 60; their membership, confidence, exclusions and quotas are unknown here.

| Primary format | Supported | Negative | Total | Established identity | Candidate-only | Established families | Largest cluster |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| TXT | 33 | 19 | 52 | 52 | 0 | 32 | 4 |
| PDF | 10 | 7 | 17 | 17 | 0 | 9 | 4 |
| JSON/table | 33 | 0 | 33 | 29 | 4 | 23 | 4 |
| All | 76 | 26 | 102 | 98 | 4 | 57 | 5 |

The negative fraction is **26/102 = 25.49%**. Format family counts are not additive: seven article families span TXT/PDF. Among the 98 established primary identities, the cluster-size distribution is **34 singleton families, 13 pairs, four triples, four groups of four, and two groups of five**. This is 57 trace units, not 98 independent samples or an estimated effective sample size. Rhine and Immune_system are the two five-case article families.

Examples of company-level grouping: Tencent contributes four primary cases from three tables (012/013/041/105); Carpenter Technology contributes 023/040; Woolworths has established supplied attribution for 048/049 and an unverified candidate match for 030. Cogeco Communications is grouped with its controlling parent Cogeco Inc., supported by the report's voting-control disclosure. Company/report year remains a secondary field; missing report identity is not guessed from a comparative column or a misleading mirror filename.

## Unresolved tracing and lineage

| Primary cases | Candidate filer | Remaining check |
| --- | --- | --- |
| 030 | Woolworths Group (Australia) | Exact performance-rights table attribution; repeated PDF text retrieval failed. Do not infer certainty from 048/049's different table. |
| 056 | Sealed Air | Match the exact December 2019 revised allocation, not a later changed acquisition table. |
| 089/090 | CalAmp | Confirm the complete ASC606 adoption table; the report search and TRACKER context are leads. |

Stress case **062** has a Leidos candidate trace and remains in the exposure handoff. VMware/Dell, TCS/Tata, later corporate successors and copied acquired-business disclosures need custodian lineage reconciliation where relevant. A/B does not certify that exhaustive lineage work has happened. Article keys establish the original dataset article, not byte identity to today's Wikipedia page; paper keys establish the recorded arXiv paper, not universal deduplication of every later publication.

If the four candidate primary cases remain unresolved, the family-eligible development subset would be **98 = 72 supported + 26 negative**, including 29 table cases. That would remove four table positives, moving table coverage from **33/102 (32.35%)** to **29/98 (29.59%)**, before any custodian collisions or gold decisions. This is a scenario, not an applied split. No family exclusions have been applied yet, and no reserve has been acquired or drawn.

## Custodian check, replacements and quotas

[Custodian instructions](../reviews/t39-d6-custodian-handoff-v1.3.md) bind the [development-only input](../reviews/t39-d6-custodian-input-v1.3.json) and [incomplete receipt template](../reviews/t39-d6-custodian-receipt-template-v1.3.json). The custodian applies the same D3 taxonomy, D4 scoring record and D5 table/proof checks to every sealed candidate and retains a private evidence audit. Only aggregate counts and affected development keys return. Unknown sealed provenance limits the claim; there is no silent assumption that all 60 candidates enter primary.

Whole colliding development families move to diagnostics, including any previously derived/stress members; original tiers and labels remain recorded. Unknown development identities stay outside the certified subset. No sealed item moves into development. The receipt validator checks arithmetic/allowed fields, not the truth of the human attestation. It rejects leaked sealed identifiers, unexpected free-text fields, altered input/policy hashes, incomplete screening and inconsistent counts.

Targets remain **150-300 primary overall, 25-30% negatives, >=30% sealed, >=20 families in each split, >=20 cases of each format and >=20 table cases**. Development currently contributes 102 provisional cases; final achieved whole-benchmark totals are **pending**, not 162 by assumption. The reconciliation tool recomputes counts and losses from a real receipt. No actual receipt exists yet.

The [v1.3 policy](../../evals/measurement/families-v1.3.md) freezes size bands and seed `t39-d6-reserve-20261017-v1`, adding supplied-text UTF-8 size to the earlier source/label/format/structure/question-type strata. A reserve must be development-only, source-screened and established noncolliding before selection; no handpicked or cross-stratum substitutions. Missing/exhausted reserves mean a smaller reported set and explicit quota shortfalls. Only the pure ordering helper has been tested with synthetic records.

## Uncertainty and verification

A case-weighted **family bootstrap** is implemented with 10,000 resamples, seed 3906 and empirical 95% bounds. Each sampled family contributes all its cases; repeat passes are not pooled. One-family inputs return no interval, unknown provenance is refused, and failures require explicit outcomes rather than being dropped. No accuracy intervals are reported now because this proposal has no measured outputs. Existing paired strategy gate rules are preserved. Runtime/scorer integration must bind the corrected family ledger and custodian receipt before the final execution freeze; the older proposal reviewer alone is insufficient.

**88 offline measurement tests pass**, including 17 new family/privacy/statistical checks. The live development build reverified **116 original development members** and matched all 37 table questions to 32 table traces with actual local source pointers. All 72 artifact entries in the prior D2-D5 manifests still match their recorded hashes (entries overlap). Tests use synthetic receipts and outcomes only; they do not read sealed material. No GPU or Docker checks were needed for these offline evaluation tools.

Reproduce the trace with the retained ignored development package and source audit, using a fresh output directory:

```powershell
python -m evals.measurement.families build --audit tmp/t39-internal-review/source-audit.json --proposal tmp/t39-v2-review-proposal-v2 --output tmp/t39-d6-reproduction
python -m unittest discover -s evals/measurement -t .
```

A fresh clone has the public ledger, table trace registry and tests; the private proposal/audit is not reconstructed or downloaded by these commands. Public report URLs are mutable evidence references, not newly pinned source fixtures. Failed/partial trace builds remain under `tmp/`; no attempt was deleted. [Review manifest](t39-d6-review-manifest-v1.3.json) hashes this review candidate, not an executable benchmark.

Remaining: verify the four candidate primary traces and applicable lineage, obtain the aggregate custodian check with equal sealed screening, resolve D7 and gold decisions 010/034/047/053/071/107, integrate the successor/scorer/actual table splitting, recompute final quotas, then hash and commit the complete execution inputs before inference. T39 stays active; NuExtract/ranked-five defaults are unchanged.

## Primary trace index

The [full ledger](t39-d6-family-ledger-v1.3.json) contains exact source hashes, methods, report locators, local clue pointers and limitations for all 120 exposed cases. Financial clues identify the report; they are not new answer-proof annotations. A/B below means established source identity at the recorded scope, **not certified cross-split separation**.

| Case | Format | Tier | Source family | Evidence |
| --- | --- | --- | --- | --- |
| 001 | TXT | B | `paper:arxiv:1905.07791` | [Source](https://arxiv.org/abs/1905.07791) |
| 002 | JSON | A | `company:sec-39020` | [Source](https://www.sec.gov/Archives/edgar/data/39020/000118518519001020/freqelec20190430_10k.htm) |
| 003 | PDF | B | `article:wikipedia:Scottish_Parliament` | [Source](https://en.wikipedia.org/wiki/Scottish_Parliament) |
| 005 | TXT | B | `article:wikipedia:Scottish_Parliament` | [Source](https://en.wikipedia.org/wiki/Scottish_Parliament) |
| 006 | TXT | B | `article:wikipedia:Scottish_Parliament` | [Source](https://en.wikipedia.org/wiki/Scottish_Parliament) |
| 007 | TXT | B | `article:wikipedia:Yuan_dynasty` | [Source](https://en.wikipedia.org/wiki/Yuan_dynasty) |
| 008 | TXT | B | `article:wikipedia:Yuan_dynasty` | [Source](https://en.wikipedia.org/wiki/Yuan_dynasty) |
| 009 | TXT | B | `article:wikipedia:Yuan_dynasty` | [Source](https://en.wikipedia.org/wiki/Yuan_dynasty) |
| 010 | TXT | B | `article:wikipedia:Yuan_dynasty` | [Source](https://en.wikipedia.org/wiki/Yuan_dynasty) |
| 012 | JSON | A | `company:hkex-00700` | [Source](https://www.hkexnews.hk/listedco/listconews/sehk/2020/0402/2020040201883.pdf) |
| 013 | JSON | A | `company:hkex-00700` | [Source](https://www.hkexnews.hk/listedco/listconews/sehk/2020/0402/2020040201883.pdf) |
| 014 | TXT | B | `paper:arxiv:2003.11645` | [Source](https://arxiv.org/abs/2003.11645) |
| 016 | TXT | B | `article:wikipedia:Harvard_University` | [Source](https://en.wikipedia.org/wiki/Harvard_University) |
| 018 | TXT | B | `article:wikipedia:Geology` | [Source](https://en.wikipedia.org/wiki/Geology) |
| 019 | TXT | B | `article:wikipedia:Geology` | [Source](https://en.wikipedia.org/wiki/Geology) |
| 020 | TXT | B | `paper:arxiv:1909.13104` | [Source](https://arxiv.org/abs/1909.13104) |
| 021 | JSON | A | `company:sec-1385157` | [Source](https://www.te.com/content/dam/te-com/documents/about-te/our-company/global/annual-report/te-connectivity-ltd-2019-annual-report.pdf) |
| 022 | JSON | A | `company:sec-51143` | [Source](https://www.ibm.com/annualreport/assets/past-reports/2019-ibm-annual-report.pdf) |
| 023 | JSON | A | `company:sec-17843` | [Source](https://s201.q4cdn.com/736712880/files/doc_financials/2019/q4/cd38d9fa-931a-4078-9621-d5d2e7759392.pdf) |
| 024 | JSON | A | `company:sec-1124804` | [Source](https://www.annualreports.com/HostedData/AnnualReportArchive/a/NASDAQ_MDRX_2018.pdf) |
| 025 | JSON | A | `company:gb-00470893` | [Source](https://assets.ctfassets.net/63dbmymdqn3g/1G3Lbkq4Es137gDqn5ofq5/83a1abc2bfae9a031f559445e4e8667c/PR-532020_Full-Year-Results-2019.pdf) |
| 026 | TXT | B | `article:wikipedia:Sky_(United_Kingdom)` | [Source](https://en.wikipedia.org/wiki/Sky_%28United_Kingdom%29) |
| 027 | TXT | B | `article:wikipedia:Sky_(United_Kingdom)` | [Source](https://en.wikipedia.org/wiki/Sky_%28United_Kingdom%29) |
| 028 | JSON | B | `company:sec-1033767` | [Source](https://www.sec.gov/Archives/edgar/data/1033767/000129281420001808/exhibit99_1.htm) |
| 029 | JSON | B | `company:sec-1033767` | [Source](https://www.sec.gov/Archives/edgar/data/1033767/000129281420001808/exhibit99_1.htm) |
| 030 | JSON | C | `company:au-woolworths-group` | [Source](https://announcements.asx.com.au/asxpdf/20190829/pdf/447zlz9gr2dl58.pdf) |
| 031 | TXT | B | `article:wikipedia:1973_oil_crisis` | [Source](https://en.wikipedia.org/wiki/1973_oil_crisis) |
| 032 | TXT | B | `article:wikipedia:1973_oil_crisis` | [Source](https://en.wikipedia.org/wiki/1973_oil_crisis) |
| 033 | TXT | B | `paper:arxiv:1709.05036` | [Source](https://arxiv.org/abs/1709.05036) |
| 034 | TXT | B | `paper:arxiv:2002.01984` | [Source](https://arxiv.org/abs/2002.01984) |
| 035 | PDF | B | `article:wikipedia:Immune_system` | [Source](https://en.wikipedia.org/wiki/Immune_system) |
| 036 | TXT | B | `article:wikipedia:Immune_system` | [Source](https://en.wikipedia.org/wiki/Immune_system) |
| 037 | TXT | B | `article:wikipedia:Immune_system` | [Source](https://en.wikipedia.org/wiki/Immune_system) |
| 038 | PDF | B | `article:wikipedia:Immune_system` | [Source](https://en.wikipedia.org/wiki/Immune_system) |
| 039 | PDF | B | `article:wikipedia:Immune_system` | [Source](https://en.wikipedia.org/wiki/Immune_system) |
| 040 | JSON | A | `company:sec-17843` | [Source](https://s201.q4cdn.com/736712880/files/doc_financials/2019/q4/cd38d9fa-931a-4078-9621-d5d2e7759392.pdf) |
| 041 | JSON | A | `company:hkex-00700` | [Source](https://www.hkexnews.hk/listedco/listconews/sehk/2020/0402/2020040201883.pdf) |
| 042 | TXT | B | `article:wikipedia:University_of_Chicago` | [Source](https://en.wikipedia.org/wiki/University_of_Chicago) |
| 043 | PDF | B | `article:wikipedia:Pharmacy` | [Source](https://en.wikipedia.org/wiki/Pharmacy) |
| 044 | TXT | B | `article:wikipedia:Pharmacy` | [Source](https://en.wikipedia.org/wiki/Pharmacy) |
| 045 | TXT | B | `article:wikipedia:Pharmacy` | [Source](https://en.wikipedia.org/wiki/Pharmacy) |
| 047 | TXT | B | `paper:arxiv:1909.00015` | [Source](https://arxiv.org/abs/1909.00015) |
| 048 | JSON | B | `company:au-woolworths-group` | [Source](https://announcements.asx.com.au/asxpdf/20190829/pdf/447zlz9gr2dl58.pdf) |
| 049 | JSON | B | `company:au-woolworths-group` | [Source](https://announcements.asx.com.au/asxpdf/20190829/pdf/447zlz9gr2dl58.pdf) |
| 050 | TXT | B | `article:wikipedia:Huguenot` | [Source](https://en.wikipedia.org/wiki/Huguenot) |
| 051 | TXT | B | `article:wikipedia:Huguenot` | [Source](https://en.wikipedia.org/wiki/Huguenot) |
| 052 | TXT | B | `article:wikipedia:Huguenot` | [Source](https://en.wikipedia.org/wiki/Huguenot) |
| 053 | TXT | B | `paper:arxiv:2002.02070` | [Source](https://arxiv.org/abs/2002.02070) |
| 054 | TXT | B | `paper:arxiv:2002.02070` | [Source](https://arxiv.org/abs/2002.02070) |
| 055 | JSON | A | `company:au-nextdc` | [Source](https://23251048.fs1.hubspotusercontent-na1.net/hubfs/23251048/ASX%20Announcements/FY19%20ANNUAL%20Report_1965129.pdf) |
| 056 | JSON | C | `company:sec-1012100` | [Source](https://www.sec.gov/Archives/edgar/data/1012100/000162828020002658/q4201910-kdocument.htm) |
| 057 | TXT | B | `article:wikipedia:Normans` | [Source](https://en.wikipedia.org/wiki/Normans) |
| 058 | TXT | B | `article:wikipedia:Economic_inequality` | [Source](https://en.wikipedia.org/wiki/Economic_inequality) |
| 059 | TXT | B | `article:wikipedia:Economic_inequality` | [Source](https://en.wikipedia.org/wiki/Economic_inequality) |
| 060 | PDF | B | `article:wikipedia:Economic_inequality` | [Source](https://en.wikipedia.org/wiki/Economic_inequality) |
| 061 | PDF | B | `article:wikipedia:Economic_inequality` | [Source](https://en.wikipedia.org/wiki/Economic_inequality) |
| 063 | TXT | B | `paper:arxiv:1810.12085` | [Source](https://arxiv.org/abs/1810.12085) |
| 066 | TXT | B | `article:wikipedia:Warsaw` | [Source](https://en.wikipedia.org/wiki/Warsaw) |
| 068 | TXT | B | `article:wikipedia:Warsaw` | [Source](https://en.wikipedia.org/wiki/Warsaw) |
| 069 | JSON | A | `company:sec-23217` | [Source](https://www.sec.gov/Archives/edgar/data/23217/000002321719000006/cag-2019x10k.htm) |
| 070 | PDF | B | `article:wikipedia:Civil_disobedience` | [Source](https://en.wikipedia.org/wiki/Civil_disobedience) |
| 071 | TXT | B | `article:wikipedia:Civil_disobedience` | [Source](https://en.wikipedia.org/wiki/Civil_disobedience) |
| 072 | TXT | B | `article:wikipedia:Civil_disobedience` | [Source](https://en.wikipedia.org/wiki/Civil_disobedience) |
| 074 | TXT | B | `paper:arxiv:1903.07406` | [Source](https://arxiv.org/abs/1903.07406) |
| 075 | TXT | B | `article:wikipedia:Steam_engine` | [Source](https://en.wikipedia.org/wiki/Steam_engine) |
| 077 | TXT | B | `article:wikipedia:Steam_engine` | [Source](https://en.wikipedia.org/wiki/Steam_engine) |
| 078 | PDF | B | `article:wikipedia:Black_Death` | [Source](https://en.wikipedia.org/wiki/Black_Death) |
| 080 | JSON | A | `company:sec-796505` | [Source](https://ir.seeclearfield.com/sec-filings/all-sec-filings/content/0001171843-19-007586/f10k_111419p.htm) |
| 081 | TXT | B | `paper:arxiv:1612.08205` | [Source](https://arxiv.org/abs/1612.08205) |
| 083 | TXT | B | `paper:arxiv:1906.07701` | [Source](https://arxiv.org/abs/1906.07701) |
| 084 | PDF | B | `article:wikipedia:Private_school` | [Source](https://en.wikipedia.org/wiki/Private_school) |
| 085 | PDF | B | `article:wikipedia:Private_school` | [Source](https://en.wikipedia.org/wiki/Private_school) |
| 086 | JSON | A | `company:sec-898293` | [Source](https://www.sec.gov/Archives/edgar/data/898293/000119312519271646/d782178d10k.htm) |
| 087 | JSON | A | `company:sec-1274494` | [Source](https://www.annualreports.com/HostedData/AnnualReportArchive/f/NASDAQ_FSLR_2019.pdf) |
| 089 | JSON | C | `company:sec-730255` | [Source](https://www.annualreports.co.uk/HostedData/AnnualReportArchive/c/NASDAQ_CAMP_2019.pdf) |
| 090 | JSON | C | `company:sec-730255` | [Source](https://www.annualreports.co.uk/HostedData/AnnualReportArchive/c/NASDAQ_CAMP_2019.pdf) |
| 091 | JSON | A | `company:ie-greencore` | [Source](https://www.greencore.com/app/uploads/2019/05/Greencore-Group-plc-Annual-Report-Financial-Statements-2019.pdf) |
| 093 | TXT | B | `article:wikipedia:Southern_California` | [Source](https://en.wikipedia.org/wiki/Southern_California) |
| 094 | PDF | B | `article:wikipedia:Southern_California` | [Source](https://en.wikipedia.org/wiki/Southern_California) |
| 095 | PDF | B | `article:wikipedia:Southern_California` | [Source](https://en.wikipedia.org/wiki/Southern_California) |
| 096 | TXT | B | `article:wikipedia:Southern_California` | [Source](https://en.wikipedia.org/wiki/Southern_California) |
| 097 | TXT | B | `article:wikipedia:Victoria_(Australia)` | [Source](https://en.wikipedia.org/wiki/Victoria_%28Australia%29) |
| 098 | TXT | B | `article:wikipedia:Victoria_(Australia)` | [Source](https://en.wikipedia.org/wiki/Victoria_%28Australia%29) |
| 100 | PDF | B | `article:wikipedia:Rhine` | [Source](https://en.wikipedia.org/wiki/Rhine) |
| 101 | PDF | B | `article:wikipedia:Rhine` | [Source](https://en.wikipedia.org/wiki/Rhine) |
| 102 | PDF | B | `article:wikipedia:Rhine` | [Source](https://en.wikipedia.org/wiki/Rhine) |
| 103 | TXT | B | `article:wikipedia:Rhine` | [Source](https://en.wikipedia.org/wiki/Rhine) |
| 104 | PDF | B | `article:wikipedia:Rhine` | [Source](https://en.wikipedia.org/wiki/Rhine) |
| 105 | JSON | A | `company:hkex-00700` | [Source](https://www.hkexnews.hk/listedco/listconews/sehk/2020/0402/2020040201883.pdf) |
| 106 | TXT | B | `paper:arxiv:1902.09666` | [Source](https://arxiv.org/abs/1902.09666) |
| 107 | TXT | B | `paper:arxiv:1902.09666` | [Source](https://arxiv.org/abs/1902.09666) |
| 108 | JSON | A | `company:sec-849399` | [Source](https://materials.proxyvote.com/Approved/871503/20191105/CMB10_410903.PDF) |
| 109 | TXT | B | `article:wikipedia:Packet_switching` | [Source](https://en.wikipedia.org/wiki/Packet_switching) |
| 112 | TXT | B | `article:wikipedia:Packet_switching` | [Source](https://en.wikipedia.org/wiki/Packet_switching) |
| 113 | JSON | A | `company:ca-cogeco` | [Source](https://www.annualreports.com/HostedData/AnnualReportArchive/c/TSX_CGO_2019.pdf) |
| 114 | JSON | A | `company:au-national-storage-reit` | [Source](https://www.annualreports.com/HostedData/AnnualReportArchive/n/ASX_NSR_2019.pdf) |
| 115 | JSON | A | `company:gb-sophos-group` | [Source](https://www.annualreports.com/HostedData/AnnualReports/PDF/LSE_SOPH_2018.pdf) |
| 116 | JSON | A | `company:sec-1609711` | [Source](https://d18rn0p25nwr6d.cloudfront.net/CIK-0001609711/cf2c41a0-20eb-4642-9248-7615e122394b.pdf) |
| 117 | JSON | A | `company:sec-807882` | [Source](https://www.sec.gov/Archives/edgar/data/807882/000080788219000023/fy201910-k.htm) |
| 118 | TXT | B | `paper:arxiv:1910.06592` | [Source](https://arxiv.org/abs/1910.06592) |
| 119 | JSON | A | `company:us-advanced-energy-industries` | [Source](https://www.annualreports.com/HostedData/AnnualReportArchive/a/NASDAQ_AEIS_2019.pdf) |
| 120 | JSON | A | `company:sec-1158324` | [Source](https://www.sec.gov/Archives/edgar/data/1158324/000110465920026777/ccoi-20191231x10k90102d.htm) |
