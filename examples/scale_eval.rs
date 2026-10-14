//! Explicit synthetic capacity probe, not semantic retrieval or model inference.
#[path = "../tests/support/mod.rs"]
mod support;
use serde_json::json;
use std::{collections::BTreeMap, time::Instant};
use vectornext::{contracts::*, search::*};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let (directory, mut db) = support::database();
    let space = support::space(384);
    let mut seed = 42u64;
    let mut next_vector = || {
        (0..384)
            .map(|_| {
                seed ^= seed << 13;
                seed ^= seed >> 7;
                seed ^= seed << 17;
                (seed % 20001) as f32 / 10000.0 - 1.0
            })
            .collect::<Vec<_>>()
    };
    let start = Instant::now();
    let mut original_bytes = 0;
    for i in 0..400 {
        let texts: Vec<_> = (0..32)
            .map(|j| {
                format!(
                    "Synthetic document {i} passage {j}. {}",
                    "Bearing calibration is recorded in this invented capacity fixture. ".repeat(9)
                )
            })
            .collect();
        let vectors = (0..32).map(|_| next_vector()).collect();
        let doc = support::document(
            &mut db,
            &format!("d{i:03}"),
            "r1",
            &texts.iter().map(String::as_str).collect::<Vec<_>>(),
            vectors,
            &space,
        );
        original_bytes += doc.original.bytes;
        db.commit(Batch {
            operation_id: format!("insert-{i}"),
            spaces: if i == 0 { vec![space.clone()] } else { vec![] },
            mutations: vec![Mutation::Replace {
                expected_revision: None,
                document: Box::new(doc),
            }],
        })?;
    }
    let ingestion_seconds = start.elapsed().as_secs_f64();
    let start = Instant::now();
    let index = SearchIndex::build(db.snapshot(), space.id(), KeywordConfig::default())?;
    let build_seconds = start.elapsed().as_secs_f64();
    let mut times = BTreeMap::new();
    for filtered in [false, true] {
        let mut records = vec![];
        for _ in 0..30 {
            let mut request = SearchRequest::hybrid(
                "bearing calibration",
                QueryVector {
                    space_id: space.id(),
                    values: next_vector(),
                },
            );
            if filtered {
                request.filter = Filter::DocumentIds((0..20).map(|i| format!("d{i:03}")).collect());
            }
            let (result, timings) = index.search_measured(&request)?;
            records.push(json!({"timings_ms":timings,"eligible":result.eligible_chunks,"dense_scored":result.dense_scored}));
        }
        times.insert(
            if filtered {
                "20_documents"
            } else {
                "400_documents"
            },
            records,
        );
    }
    let peak_rss = std::fs::read_to_string("/proc/self/status")?
        .lines()
        .find(|line| line.starts_with("VmHWM:"))
        .unwrap_or("unavailable")
        .to_string();
    println!(
        "{}",
        json!({"scope":"synthetic supplied vectors; no parsing/embedding/generation or quality claim", "documents":400,"chunks":12800,"dimensions":384,
        "original_bytes":original_bytes,"mean_document_bytes":original_bytes/400,"storage_preparation_seconds":ingestion_seconds,"index_build_seconds":build_seconds,"peak_process_rss":peak_rss,
        "temporary_database":directory.path(),"queries":times})
    );
    Ok(())
}
