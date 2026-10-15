//! T22 isolated profiler. The same source runs against baseline and optimized cores.
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{collections::BTreeSet, fs, fs::OpenOptions, path::Path, time::Instant};
use vectornext::{Database, search::*};
type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;

fn attr(predicate: Predicate) -> Filter {
    Filter::Attribute {
        key: "bucket".into(),
        pointer: String::new(),
        predicate,
        trust: AttributeTrust::SourceOrDeterministic,
    }
}
fn cases(size: usize) -> Vec<(&'static str, Filter)> {
    let scope = Filter::DocumentIds(
        (0..size / 20)
            .map(|i| format!("d{i:05}"))
            .collect::<BTreeSet<_>>(),
    );
    let range = attr(Predicate::NumericRange {
        min: Some(Bound {
            value: 0.into(),
            inclusive: true,
        }),
        max: Some(Bound {
            value: 4.into(),
            inclusive: true,
        }),
    });
    vec![
        ("all", Filter::default()),
        ("scope5", scope.clone()),
        ("attribute1", attr(Predicate::Eq(json!(0)))),
        ("empty", attr(Predicate::Eq(json!(999)))),
        ("range5", range.clone()),
        ("not", Filter::Not(Box::new(attr(Predicate::Eq(json!(0)))))),
        (
            "or",
            Filter::Any(vec![
                attr(Predicate::Eq(json!(0))),
                attr(Predicate::Eq(json!(1))),
            ]),
        ),
        ("and", Filter::All(vec![scope, range])),
        (
            "missing",
            Filter::Attribute {
                key: "absent".into(),
                pointer: String::new(),
                predicate: Predicate::Eq(json!(0)),
                trust: AttributeTrust::Any,
            },
        ),
        (
            "nested_fallback",
            Filter::Attribute {
                key: "bucket".into(),
                pointer: "/x".into(),
                predicate: Predicate::Eq(json!(0)),
                trust: AttributeTrust::Any,
            },
        ),
        (
            "container_fallback",
            attr(Predicate::Eq(json!({"value":0}))),
        ),
    ]
}
fn main() -> Result<()> {
    let args: Vec<_> = std::env::args().collect();
    if args.len() != 6 {
        return Err("usage: filter_profile DATABASE INPUTS SIZE OUTPUT PASSES".into());
    }
    let size: usize = args[3].parse()?;
    let passes: usize = args[5].parse()?;
    let output = OpenOptions::new()
        .create_new(true)
        .write(true)
        .open(&args[4])?;
    let started = Instant::now();
    let db = Database::open(&args[1])?;
    let open_ms = started.elapsed().as_secs_f64() * 1000.0;
    let snapshot = db.snapshot();
    let space = snapshot.spaces().next().ok_or("no space")?.0.clone();
    let started = Instant::now();
    let index = SearchIndex::build(snapshot, space.clone(), KeywordConfig::default())?;
    let build_ms = started.elapsed().as_secs_f64() * 1000.0;
    let queries: Vec<Value> = serde_json::from_slice(&fs::read(
        Path::new(&args[2])
            .join(size.to_string())
            .join("queries.json"),
    )?)?;
    let cases = cases(size);
    let mut measurements = vec![];
    // Eight independent query vectors per filter, two trace modes, fixed repeated passes.
    for pass in 0..passes {
        for trace in [false, true] {
            for (case, filter) in &cases {
                for (q, query) in queries.iter().take(8).enumerate() {
                    let mut request = SearchRequest::hybrid(
                        "",
                        QueryVector {
                            space_id: space.clone(),
                            values: serde_json::from_value(query["vector"].clone())?,
                        },
                    );
                    request.filter = filter.clone();
                    request.dense_k = 10;
                    request.keyword_k = 0;
                    request.keyword_weight = 0.0;
                    request.limit = 10;
                    request.deduplication = Deduplication::None;
                    request.trace_eligibility = trace;
                    let started = Instant::now();
                    let (response, stages) = index.search_measured(&request)?;
                    let elapsed_ms = started.elapsed().as_secs_f64() * 1000.0;
                    let digest = format!("{:x}", Sha256::digest(serde_json::to_vec(&response)?));
                    measurements.push(json!({"pass":pass,"trace":trace,"case":case,"query":q,"elapsed_ms":elapsed_ms,"stages":stages,"eligible":response.eligible_chunks,"unknown":response.unknown_filter_chunks,"response_sha256":digest}));
                }
            }
        }
    }
    let status = fs::read_to_string("/proc/self/status").unwrap_or_default();
    let memory: Vec<_> = status
        .lines()
        .filter(|l| l.starts_with("VmRSS:") || l.starts_with("VmHWM:"))
        .collect();
    serde_json::to_writer_pretty(
        output,
        &json!({"size":size,"passes":passes,"open_ms":open_ms,"index_build_ms":build_ms,"memory":memory,"measurements":measurements}),
    )?;
    println!("{size}: {} measurements saved", measurements.len());
    Ok(())
}
