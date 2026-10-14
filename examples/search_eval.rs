//! Deterministic source-coverage diagnostics. No parser, embedding model, or gold-fed search.
#[path = "../tests/support/mod.rs"]
mod support;
use serde::{Deserialize, Serialize};
use serde_json::json;
use sha2::{Digest, Sha256};
use std::collections::BTreeSet;
use vectornext::{contracts::Locator, search::*};

#[derive(Clone, Serialize, Deserialize)]
struct GoldSpan {
    id: String,
    document_id: String,
    revision: String,
    start: u64,
    end: u64,
}

#[derive(Serialize)]
struct Coverage {
    candidates: usize,
    evidence_bytes: usize,
    covered: Vec<String>,
    recall: Option<f64>,
    complete: Option<bool>,
    first_complete_rank: Option<usize>,
}

fn covered(index: &SearchIndex, keys: &[ChunkKey], gold: &GoldSpan) -> bool {
    // Coverage is the union of actual source intervals in the matching logical
    // document/revision. A correct document or matching text alone gets no credit.
    let mut intervals = vec![];
    for key in keys {
        if key.document_id != gold.document_id || key.revision != gold.revision {
            continue;
        }
        let (_, chunk) = index
            .resolve(key)
            .expect("reported key resolves in its generation");
        for source in &chunk.sources {
            if source.revision == gold.revision {
                if let Locator::Text { bytes, .. } = &source.locator {
                    intervals.push((bytes.start, bytes.end));
                }
            }
        }
    }
    intervals.sort();
    let mut through = gold.start;
    for (start, end) in intervals {
        if start > through {
            break;
        }
        if end > through {
            through = end;
        }
        if through >= gold.end {
            return true;
        }
    }
    false
}

fn coverage(index: &SearchIndex, keys: Vec<ChunkKey>, gold: &[GoldSpan]) -> Coverage {
    let matched: Vec<_> = gold
        .iter()
        .filter(|g| covered(index, &keys, g))
        .map(|g| g.id.clone())
        .collect();
    Coverage {
        candidates: keys.len(),
        evidence_bytes: keys
            .iter()
            .map(|k| index.resolve(k).unwrap().1.evidence.len())
            .sum(),
        recall: (!gold.is_empty()).then(|| matched.len() as f64 / gold.len() as f64),
        complete: (!gold.is_empty()).then_some(matched.len() == gold.len()),
        first_complete_rank: if gold.is_empty() {
            None
        } else {
            (1..=keys.len()).find(|&n| gold.iter().all(|g| covered(index, &keys[..n], g)))
        },
        covered: matched,
    }
}

fn span(id: &str, document: &str, start: usize, end: usize) -> GoldSpan {
    GoldSpan {
        id: id.into(),
        document_id: document.into(),
        revision: "r1".into(),
        start: start as u64,
        end: end as u64,
    }
}

fn make_report() -> serde_json::Value {
    let (_dir, db, space) = support::diagnostic_corpus();
    let index = SearchIndex::build(db.snapshot(), space.id(), KeywordConfig::default()).unwrap();
    let target = span("target-match", "b-target", 0, support::TARGET.len());
    let near = span("different-year", "a-near", 0, support::NEAR.len());
    let unit = span("torque-unit", "d-maintenance", 0, support::UNIT.len());
    let value = span(
        "torque-value",
        "d-maintenance",
        support::UNIT.len() + 1,
        support::UNIT.len() + 1 + support::VALUE.len(),
    );
    let mut base = SearchRequest::hybrid(
        "Pele Argentina 1954",
        QueryVector {
            space_id: space.id(),
            values: vec![1., 0., 0.],
        },
    );
    base.dense_k = 1;
    base.keyword_k = 2;
    base.limit = 3;
    base.trace_eligibility = true;
    let mut final_cut = base.clone();
    final_cut.limit = 1;
    let mut filtered = base.clone();
    filtered.filter = Filter::Attribute {
        key: "match.year".into(),
        pointer: "".into(),
        predicate: Predicate::Eq(json!(1954)),
        trust: AttributeTrust::default(),
    };
    let mut wrong_filter = base.clone();
    wrong_filter.filter = Filter::Attribute {
        key: "match.year".into(),
        pointer: "".into(),
        predicate: Predicate::Eq(json!(1955)),
        trust: AttributeTrust::default(),
    };
    let mut maintenance = SearchRequest::hybrid(
        "J2 torque tightening",
        QueryVector {
            space_id: space.id(),
            values: vec![0., 0., 1.],
        },
    );
    maintenance.dense_k = 2;
    maintenance.keyword_k = 2;
    maintenance.limit = 1;
    maintenance.trace_eligibility = true;
    let mut maintenance_full = maintenance.clone();
    maintenance_full.limit = 2;
    let mut ambiguous = SearchRequest::hybrid(
        "Pele Argentina",
        QueryVector {
            space_id: space.id(),
            values: vec![1., 0., 0.],
        },
    );
    ambiguous.dense_k = 5;
    ambiguous.keyword_k = 5;
    ambiguous.limit = 5;
    ambiguous.trace_eligibility = true;
    let mut absent = SearchRequest::keyword("8 goals against Mars");
    absent.trace_eligibility = true;
    let cases = vec![
        (
            "keyword-rescues-dense-cutoff",
            "supported",
            base,
            vec![target.clone()],
        ),
        (
            "final-limit-loses-rescued-evidence",
            "supported",
            final_cut,
            vec![target.clone()],
        ),
        (
            "explicit-year-filter",
            "supported",
            filtered,
            vec![target.clone()],
        ),
        (
            "incorrect-explicit-filter-loses-evidence",
            "supported",
            wrong_filter,
            vec![target],
        ),
        (
            "unit-and-value-budget-loss",
            "supported",
            maintenance,
            vec![unit.clone(), value.clone()],
        ),
        (
            "unit-and-value-retained",
            "supported",
            maintenance_full,
            vec![unit, value],
        ),
        (
            "ambiguous-year-alternatives",
            "ambiguous",
            ambiguous,
            vec![
                near,
                span("target-match", "b-target", 0, support::TARGET.len()),
            ],
        ),
        (
            "no-support-defined",
            "insufficient_evidence",
            absent,
            vec![],
        ),
    ];
    let mut corpus = vec![];
    for (key, document, chunk) in index.records() {
        corpus.push(json!({"key":key,"original":document.original,"chunk":chunk}));
    }
    let corpus_hash = format!("{:x}", Sha256::digest(serde_json::to_vec(&corpus).unwrap()));
    let mut output = vec![];
    for (id, status, request, gold) in cases {
        // Gold is used only below, after search. Requests contain no gold IDs/locations.
        let response = index.search(&request).unwrap();
        let stages = vec![
            (
                "eligible",
                response
                    .eligibility
                    .as_ref()
                    .unwrap()
                    .iter()
                    .filter(|e| e.decision == Truth::True)
                    .map(|e| e.key.clone())
                    .collect::<Vec<_>>(),
            ),
            (
                "dense",
                response.dense.iter().map(|h| h.key.clone()).collect(),
            ),
            (
                "keyword",
                response.keyword.iter().map(|h| h.key.clone()).collect(),
            ),
            (
                "fused",
                response.fused.iter().map(|h| h.key.clone()).collect(),
            ),
            (
                "deduplicated",
                response
                    .deduplicated
                    .iter()
                    .map(|h| h.key.clone())
                    .collect(),
            ),
            (
                "results",
                response.results.iter().map(|h| h.key.clone()).collect(),
            ),
        ];
        let metrics: serde_json::Map<_, _> = stages
            .into_iter()
            .map(|(stage, keys)| {
                (
                    stage.into(),
                    serde_json::to_value(coverage(&index, keys, &gold)).unwrap(),
                )
            })
            .collect();
        output.push(json!({"id":id,"expected_outcome":status,"gold_sources":gold,"coverage":metrics,"search":response}));
    }
    let definitions_hash=format!("{:x}",Sha256::digest(serde_json::to_vec(&output.iter().map(|c|json!({"id":c["id"],"status":c["expected_outcome"],"request":c["search"]["request"],"gold":c["gold_sources"]})).collect::<Vec<_>>()).unwrap()));
    let source_hashes: serde_json::Map<_, _> = [
        (
            "src/search/mod.rs",
            include_bytes!("../src/search/mod.rs").as_slice(),
        ),
        (
            "src/search/filter.rs",
            include_bytes!("../src/search/filter.rs").as_slice(),
        ),
        (
            "src/search/keyword.rs",
            include_bytes!("../src/search/keyword.rs").as_slice(),
        ),
        (
            "tests/support/mod.rs",
            include_bytes!("../tests/support/mod.rs").as_slice(),
        ),
        (
            "examples/search_eval.rs",
            include_bytes!("search_eval.rs").as_slice(),
        ),
        ("Cargo.lock", include_bytes!("../Cargo.lock").as_slice()),
    ]
    .into_iter()
    .map(|(name, bytes)| (name.into(), json!(format!("{:x}", Sha256::digest(bytes)))))
    .collect();
    json!({
        "contract":"t04-source-coverage-v1","split":"synthetic_algorithm_diagnostics","git_revision":std::env::var("VECTORNEXT_GIT_REVISION").ok(),
        "worktree_dirty":std::env::var("VECTORNEXT_WORKTREE_DIRTY").ok().and_then(|s|s.parse::<bool>().ok()),"image_id":std::env::var("VECTORNEXT_IMAGE_ID").ok(),
        "os":std::env::consts::OS,"architecture":std::env::consts::ARCH,"source_sha256":source_hashes,
        "crate_version":env!("CARGO_PKG_VERSION"),"embedding_space":space,"embedding_space_id":space.id(),"models_invoked":false,
        "corpus_sha256":corpus_hash,"case_definitions_sha256":definitions_hash,"documents":index.records().map(|(k,_,_)|&k.document_id).collect::<BTreeSet<_>>().len(),
        "chunks":index.records().count(),"corpus":corpus,"cases":output,
        "limitations":["Hand-prepared synthetic TXT records; no ingestion/PDF/OCR evaluation.","Vectors are deliberately supplied algorithm fixtures, not model embeddings or semantic-quality evidence.","Gold locations are scored after retrieval; this is not T01 dev/holdout or a tuned retrieval benchmark.","Eligible-stage ordering is key order, not relevance ranking.","Insufficient-evidence recall is null; T04 does not classify outcomes or generate answers.","Evidence bytes, not tokenizer tokens, are reported; no performance benchmark or timing claims."]
    })
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let report = make_report();
    let content = serde_json::to_string_pretty(&report)?;
    if let Some(path) = std::env::args().nth(1) {
        std::fs::write(path, format!("{content}\n"))?;
        println!(
            "Recorded {} source-coverage cases.",
            report["cases"].as_array().unwrap().len()
        );
    } else {
        println!("{content}");
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn diagnostics_record_entry_loss_partial_support_and_undefined_recall() {
        let report = make_report();
        let cases = report["cases"].as_array().unwrap();
        assert_eq!(cases[0]["coverage"]["dense"]["recall"], json!(0.0));
        assert_eq!(cases[0]["coverage"]["keyword"]["complete"], json!(true));
        assert_eq!(cases[0]["coverage"]["results"]["complete"], json!(true));
        assert_eq!(cases[1]["coverage"]["fused"]["complete"], json!(true));
        assert_eq!(cases[1]["coverage"]["results"]["complete"], json!(false));
        assert_eq!(cases[3]["coverage"]["eligible"]["recall"], json!(0.0));
        assert_eq!(cases[4]["coverage"]["results"]["recall"], json!(0.5));
        assert_eq!(cases[5]["coverage"]["results"]["complete"], json!(true));
        assert_eq!(cases[6]["coverage"]["results"]["complete"], json!(true));
        assert!(cases[7]["coverage"]["results"]["recall"].is_null());
    }
    #[test]
    fn location_coverage_does_not_credit_other_documents_or_partial_spans() {
        let (_dir, db, space) = support::diagnostic_corpus();
        let index =
            SearchIndex::build(db.snapshot(), space.id(), KeywordConfig::default()).unwrap();
        let gold = span("target", "b-target", 0, support::TARGET.len());
        let copy = index
            .records()
            .find(|(k, _, _)| k.document_id == "f-copy")
            .unwrap()
            .0
            .clone();
        assert!(!covered(&index, &[copy], &gold));
        let key = index
            .records()
            .find(|(k, _, _)| k.document_id == "d-maintenance" && k.chunk_id == "c0")
            .unwrap()
            .0
            .clone();
        assert!(!covered(
            &index,
            &[key],
            &span(
                "both",
                "d-maintenance",
                0,
                support::UNIT.len() + 1 + support::VALUE.len()
            )
        ));
    }
}
