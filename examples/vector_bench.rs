//! T20-only supplied-vector adapter. Never part of the production API.
use axum::{
    Router,
    body::{Body, to_bytes},
    extract::{Request, State},
    response::Response,
    routing::{get, post},
};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, BTreeSet},
    path::{Path, PathBuf},
    sync::{Arc, Mutex},
    time::Instant,
};
use vectornext::{Database, contracts::*, search::*};

type AnyResult<T> = Result<T, Box<dyn std::error::Error + Send + Sync>>;
struct Slot {
    db: Database,
    index: Option<SearchIndex>,
    path: PathBuf,
}
type Shared = Arc<Mutex<Option<Slot>>>;

#[derive(Deserialize, Serialize)]
struct InputDocument {
    id: String,
    bucket: i32,
    texts: Vec<String>,
    vectors: Vec<Vec<f32>>,
}

fn space() -> EmbeddingSpace {
    EmbeddingSpace {
        model: "synthetic/t20-clustered-f32".into(),
        revision: "v1".into(),
        artifact_sha256: "c".repeat(64),
        tokenizer: "supplied-no-tokenizer".into(),
        preprocessing: "float32-input-v1".into(),
        dimensions: 384,
        max_tokens: 256,
        query_prefix: String::new(),
        document_prefix: String::new(),
        normalization: Normalization::None,
    }
}
fn make_document(db: &mut Database, input: InputDocument) -> AnyResult<DocumentRevision> {
    if input.texts.len() != 32 || input.vectors.len() != 32 {
        return Err("expected 32 chunks".into());
    }
    let original = db.put_original(input.texts.join("\n").as_bytes())?;
    let mut blocks = vec![];
    let mut chunks = vec![];
    let mut offset = 0;
    for (i, (text, vector)) in input.texts.into_iter().zip(input.vectors).enumerate() {
        let range = ByteRange {
            start: offset,
            end: offset + text.len() as u64,
        };
        let source = SourceRef {
            revision: "r1".into(),
            locator: Locator::Text {
                encoding: "UTF-8".into(),
                bytes: range.clone(),
                line_start: (i + 1) as u64,
                line_end: (i + 1) as u64,
                mappings: vec![TextMapping {
                    normalized: range.clone(),
                    original: range,
                }],
            },
        };
        let id = format!("c{i:02}");
        blocks.push(Block {
            id: id.clone(),
            kind: BlockKind::Paragraph,
            parent: None,
            text: text.clone(),
            sources: vec![source.clone()],
        });
        chunks.push(Chunk {
            id: id.clone(),
            spans: vec![BlockSpan {
                block_id: id,
                bytes: ByteRange {
                    start: 0,
                    end: text.len() as u64,
                },
            }],
            evidence: text.clone(),
            representation: Representation::NormalizedText,
            sources: vec![source.clone()],
            structural_context: String::new(),
            generated_context: None,
            attributes: BTreeMap::from([(
                "bucket".into(),
                Attribute {
                    value: json!(input.bucket),
                    sources: vec![source],
                    derivation: Derivation::Deterministic {
                        version: "t20-fixture-v1".into(),
                    },
                },
            )]),
            parent: None,
            previous: None,
            next: None,
            vectors: BTreeMap::from([(space().id(), vector)]),
        });
        offset += text.len() as u64 + 1;
    }
    Ok(DocumentRevision {
        document_id: input.id,
        revision: "r1".into(),
        original,
        media_type: MediaType::Txt,
        processing: BTreeMap::from([("fixture".into(), json!("t20-v1"))]),
        required_spaces: BTreeSet::from([space().id()]),
        blocks,
        chunks,
    })
}
fn filter(kind: &str, documents: usize) -> AnyResult<Filter> {
    Ok(match kind {
        "all" => Filter::default(),
        "scope5" => Filter::DocumentIds((0..documents / 20).map(|i| format!("d{i:05}")).collect()),
        "attribute1" | "empty" => Filter::Attribute {
            key: "bucket".into(),
            pointer: String::new(),
            predicate: Predicate::Eq(json!(if kind == "empty" { -1 } else { 0 })),
            trust: AttributeTrust::SourceOrDeterministic,
        },
        _ => return Err("unknown filter".into()),
    })
}
fn bytes_on_disk(path: &Path) -> AnyResult<u64> {
    let mut total = 0;
    for item in std::fs::read_dir(path)? {
        let item = item?;
        total += if item.file_type()?.is_dir() {
            bytes_on_disk(&item.path())?
        } else {
            item.metadata()?.len()
        };
    }
    Ok(total)
}
fn memory() -> Value {
    let read = |name: &str| std::fs::read_to_string(format!("/sys/fs/cgroup/{name}")).ok();
    json!({"cgroup_current":read("memory.current"),"cgroup_peak":read("memory.peak"),"cpu_stat":read("cpu.stat")})
}
fn execute(state: &Shared, value: Value) -> AnyResult<Value> {
    let start = Instant::now();
    let mut guard = state.lock().map_err(|_| "poisoned benchmark state")?;
    let op = value["op"].as_str().ok_or("missing operation")?;
    if op == "open" {
        let count = value["documents"].as_u64().ok_or("missing corpus size")?;
        if ![2, 400, 1600].contains(&count) {
            return Err("unsupported corpus size".into());
        }
        *guard = None;
        let path = PathBuf::from("/storage").join(count.to_string());
        let db = Database::open(&path)?;
        *guard = Some(Slot {
            db,
            index: None,
            path,
        });
        return Ok(json!({"open_ms":start.elapsed().as_secs_f64()*1000.0}));
    }
    let slot = guard.as_mut().ok_or("open a corpus first")?;
    match op {
        "insert" => {
            let input: InputDocument = serde_json::from_value(value["document"].clone())?;
            let document = make_document(&mut slot.db, input)?;
            let id = document.document_id.clone();
            slot.db.commit(Batch {
                operation_id: id,
                spaces: vec![space()],
                mutations: vec![Mutation::Replace {
                    expected_revision: None,
                    document: Box::new(document),
                }],
            })?;
            slot.index = None;
            Ok(json!({"engine_ms":start.elapsed().as_secs_f64()*1000.0}))
        }
        "index" => {
            slot.index = Some(SearchIndex::build(
                slot.db.snapshot(),
                space().id(),
                KeywordConfig::default(),
            )?);
            Ok(json!({"engine_ms":start.elapsed().as_secs_f64()*1000.0,"memory":memory()}))
        }
        "search" => {
            let vector: Vec<f32> = serde_json::from_value(value["vector"].clone())?;
            let mut request = SearchRequest::hybrid(
                "",
                QueryVector {
                    space_id: space().id(),
                    values: vector,
                },
            );
            request.filter = filter(
                value["filter"].as_str().ok_or("missing filter")?,
                value["documents"].as_u64().ok_or("missing size")? as usize,
            )?;
            request.dense_k = 10;
            request.keyword_k = 0;
            request.limit = 10;
            request.keyword_weight = 0.0;
            request.deduplication = Deduplication::None;
            let index = slot.index.as_ref().ok_or("build index first")?;
            let query_start = Instant::now();
            let result = index.search(&request)?;
            let engine_ms = query_start.elapsed().as_secs_f64() * 1000.0;
            let hits: Vec<_> = result.dense.iter().map(|h|json!({"id":format!("{}/{}",h.key.document_id,h.key.chunk_id),"score":h.score})).collect();
            Ok(json!({"hits":hits,"engine_ms":engine_ms,"eligible":result.eligible_chunks}))
        }
        "checkpoint" => {
            slot.db.checkpoint()?;
            Ok(json!({"engine_ms":start.elapsed().as_secs_f64()*1000.0}))
        }
        "stats" | "verify" => {
            let snapshot = slot.db.snapshot();
            let mut digest = Sha256::new();
            let mut documents = 0;
            let mut chunks = 0;
            for doc in snapshot.documents() {
                documents += 1;
                for chunk in &doc.chunks {
                    chunks += 1;
                    if op == "verify" {
                        digest.update(format!(
                            "{}/{}\n{}\n",
                            doc.document_id, chunk.id, chunk.evidence
                        ));
                        digest.update(
                            (chunk.attributes["bucket"]
                                .value
                                .as_i64()
                                .ok_or("invalid bucket")? as i32)
                                .to_le_bytes(),
                        );
                        for v in &chunk.vectors[&space().id()] {
                            digest.update(v.to_le_bytes());
                        }
                    }
                }
            }
            Ok(
                json!({"documents":documents,"chunks":chunks,"digest":format!("{:x}",digest.finalize()),"disk_bytes":bytes_on_disk(&slot.path)?,"memory":memory()}),
            )
        }
        _ => Err("unknown operation".into()),
    }
}
async fn handle(State(state): State<Shared>, request: Request) -> Response {
    let result: AnyResult<Value> = async {
        let bytes = to_bytes(request.into_body(), 8 * 1024 * 1024).await?;
        let input = serde_json::from_slice(&bytes)?;
        tokio::task::spawn_blocking(move || execute(&state, input)).await?
    }
    .await;
    let (status, value) = match result {
        Ok(value) => (200, value),
        Err(e) => (500, json!({"error":format!("{e}")})),
    };
    Response::builder()
        .status(status)
        .header("Content-Type", "application/json")
        .body(Body::from(value.to_string()))
        .unwrap()
}
#[tokio::main(worker_threads = 2)]
async fn main() -> AnyResult<()> {
    let state: Shared = Arc::new(Mutex::new(None));
    let router = Router::new()
        .route("/bench", post(handle))
        .route("/healthz", get(|| async { "ok" }))
        .with_state(state);
    axum::serve(tokio::net::TcpListener::bind("0.0.0.0:8080").await?, router).await?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn filters_are_explicit_and_bounded_to_the_corpus() {
        assert_eq!(
            filter("scope5", 400).unwrap(),
            Filter::DocumentIds((0..20).map(|i| format!("d{i:05}")).collect())
        );
        assert!(filter("inferred", 400).is_err());
        assert_ne!(
            filter("empty", 400).unwrap(),
            filter("attribute1", 400).unwrap()
        );
    }
}
