//! Offline development-query replay with the real stored vectors and keyword fields.
//! Requires the API owner to be stopped; never calls a model or reads gold labels.
use serde_json::{Value, json};
use std::{env, fs, path::Path};
use vectornext::{Database, search::*};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = env::args().collect();
    if args.len() != 3 {
        return Err("usage: replay_eval DATABASE_PARENT CAPTURE_ROOT".into());
    }
    let mut runs = vec![];
    for policy in ["plain", "structural", "generated"] {
        let db = Database::open(Path::new(&args[1]).join(policy))?;
        let directory = Path::new(&args[2]).join(policy).join("baseline");
        let mut inputs = vec![];
        for entry in fs::read_dir(directory)? {
            let path = entry?.path();
            let name = path.file_name().unwrap().to_string_lossy();
            if let Some(id) = name
                .strip_prefix("cold-cache-")
                .and_then(|s| s.strip_suffix(".json"))
            {
                let report: Value = serde_json::from_slice(&fs::read(&path)?)?;
                inputs.push((id.to_owned(), report));
            }
        }
        inputs.sort_by(|a, b| a.0.cmp(&b.0));
        if inputs.len() != 13 {
            return Err("expected thirteen captured development requests".into());
        }
        let space = inputs[0].1["embedding_space_id"]
            .as_str()
            .ok_or("missing space")?;
        for (structural_weight, weight) in [(1.0, 0.0), (1.0, 1.0), (1.0, 2.0), (0.0, 0.0)] {
            let index = SearchIndex::build(
                db.snapshot(),
                space.to_owned(),
                KeywordConfig {
                    structural_weight,
                    generated_weight: weight,
                    ..KeywordConfig::default()
                },
            )?;
            for candidates in [5, 10, 20, 30] {
                let mut cases = vec![];
                for (id, report) in &inputs {
                    let mut request: SearchRequest =
                        serde_json::from_value(report["retrieval"]["request"].clone())?;
                    request.dense_k = candidates;
                    request.keyword_k = candidates;
                    request.limit = 20;
                    let (result, times) = index.search_measured(&request)?;
                    cases.push(json!({"case":id,"retrieval":result,"timings_ms":times}));
                }
                runs.push(json!({"policy":policy,"structural_weight":structural_weight,"generated_weight":weight,"candidates":candidates,"cases":cases}));
            }
        }
    }
    println!(
        "{}",
        json!({"scope":"retrieval replay; no reranking/answer inference", "runs":runs})
    );
    Ok(())
}
