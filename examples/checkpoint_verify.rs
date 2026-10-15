//! T21 CPU-only checkpoint/export drill against fresh copies of the T20 stores.
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeSet,
    fs::{self, OpenOptions},
    io::Write,
    path::Path,
    time::{Duration, Instant},
};
use vectornext::{Database, ReadSnapshot, backup, contracts::Batch, search::*};
type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;

#[derive(Default)]
struct HashWriter(Sha256);
impl Write for HashWriter {
    fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
        self.0.update(bytes);
        Ok(bytes.len())
    }
    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}
fn digests(snapshot: &ReadSnapshot) -> Result<Value> {
    let mut full = HashWriter::default();
    let mut vectors = Sha256::new();
    let mut chunks = 0;
    for document in snapshot.documents() {
        serde_json::to_writer(&mut full, document)?;
        serde_json::to_writer(
            &mut full,
            snapshot
                .receipt(&document.document_id)
                .ok_or("missing document receipt")?,
        )?;
        for chunk in &document.chunks {
            chunks += 1;
            vectors.update(format!(
                "{}/{}\n{}\n",
                document.document_id, chunk.id, chunk.evidence
            ));
            vectors.update(
                (chunk.attributes["bucket"]
                    .value
                    .as_i64()
                    .ok_or("missing bucket")? as i32)
                    .to_le_bytes(),
            );
            for value in chunk.vectors.values().next().ok_or("missing vector")? {
                vectors.update(value.to_le_bytes());
            }
        }
    }
    for (id, space) in snapshot.spaces() {
        serde_json::to_writer(&mut full, &(id, space))?;
    }
    Ok(
        json!({"documents":snapshot.documents().count(),"chunks":chunks,"records_sha256":format!("{:x}",full.0.finalize()),"t20_digest":format!("{:x}",vectors.finalize())}),
    )
}
fn verify(db: &Database, inputs: &Path, count: usize) -> Result<Value> {
    let snapshot = db.snapshot();
    let digest = digests(&snapshot)?;
    let manifest: Value = serde_json::from_slice(&fs::read(inputs.join("manifest.json"))?)?;
    assert_eq!(
        digest["t20_digest"],
        manifest["corpora"][count.to_string()]["after_sentinel_digest"]
    );
    assert_eq!(digest["documents"], count + 1);
    let space_id = snapshot.spaces().next().ok_or("missing space")?.0.clone();
    let index = SearchIndex::build(snapshot, space_id.clone(), KeywordConfig::default())?;
    let queries: Vec<Value> = serde_json::from_slice(&fs::read(
        inputs.join(count.to_string()).join("queries.json"),
    )?)?;
    let mut checks = vec![];
    for query in &queries {
        let vector: Vec<f32> = serde_json::from_value(query["vector"].clone())?;
        let mut request = SearchRequest::hybrid(
            "",
            QueryVector {
                space_id: space_id.clone(),
                values: vector,
            },
        );
        request.filter = match query["filter"].as_str().ok_or("missing filter")? {
            "all" => Filter::default(),
            "scope5" => Filter::DocumentIds((0..count / 20).map(|i| format!("d{i:05}")).collect()),
            "attribute1" | "empty" => Filter::Attribute {
                key: "bucket".into(),
                pointer: String::new(),
                predicate: Predicate::Eq(json!(if query["filter"] == "empty" { -1 } else { 0 })),
                trust: AttributeTrust::SourceOrDeterministic,
            },
            _ => return Err("unknown filter".into()),
        };
        request.dense_k = 10;
        request.keyword_k = 0;
        request.limit = 10;
        request.keyword_weight = 0.0;
        request.deduplication = Deduplication::None;
        let result = index.search(&request)?;
        let expected = query["after_restart"]["hits"]
            .as_array()
            .ok_or("missing reference")?;
        let returned: BTreeSet<_> = result
            .dense
            .iter()
            .map(|h| format!("{}/{}", h.key.document_id, h.key.chunk_id))
            .collect();
        let expected_ids: BTreeSet<_> = expected
            .iter()
            .map(|h| h["id"].as_str().unwrap().to_owned())
            .collect();
        // These frozen T20 exact requests all matched the strict oracle IDs.
        assert_eq!(returned, expected_ids, "{}", query["id"]);
        assert_eq!(result.dense.len(), expected.len());
        for hit in &result.dense {
            let id = format!("{}/{}", hit.key.document_id, hit.key.chunk_id);
            let expected_score = expected.iter().find(|v| v["id"] == id).unwrap()["score"]
                .as_f64()
                .unwrap();
            assert!((hit.score - expected_score).abs() <= 1e-5);
        }
        checks.push(json!({"query":query["id"],"correct":true}));
    }
    assert_eq!(checks.len(), 128);
    Ok(json!({"digest":digest,"queries":checks,"generation":db.snapshot().generation()}))
}
fn suffix(db: &Database) -> Batch {
    Batch {
        operation_id: "t21-after-checkpoint".into(),
        spaces: vec![db.snapshot().spaces().next().unwrap().1.clone()],
        mutations: vec![],
    }
}
fn save(path: &Path, value: &Value) -> Result<()> {
    let mut file = OpenOptions::new().create_new(true).write(true).open(path)?;
    serde_json::to_writer_pretty(&mut file, value)?;
    file.write_all(b"\n")?;
    file.sync_all()?;
    Ok(())
}
fn run() -> Result<()> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    if args.len() != 5 {
        return Err("usage: checkpoint_verify prepare|recover WORK INPUTS COUNT REPORT".into());
    }
    let work = Path::new(&args[1]);
    let inputs = Path::new(&args[2]);
    let count: usize = args[3].parse()?;
    if ![400, 1600].contains(&count) {
        return Err("unsupported corpus size".into());
    }
    let started = Instant::now();
    let mut db = Database::open(work.join(count.to_string()))?;
    let open_ms = started.elapsed().as_secs_f64() * 1000.0;
    let checked = verify(&db, inputs, count)?;
    let mut report = json!({"corpus":count,"open_ms":open_ms,"verified":checked});
    match args[0].as_str() {
        "prepare" => {
            assert!(
                db.snapshot().receipt("t21-after-checkpoint").is_none(),
                "use a fresh copy"
            );
            let started = Instant::now();
            db.checkpoint()?;
            report["checkpoint_ms"] = json!(started.elapsed().as_secs_f64() * 1000.0);
            let bytes = fs::metadata(work.join(count.to_string()).join("snapshot.bin"))?.len();
            assert!(bytes > 64 * 1024 * 1024);
            report["snapshot_bytes"] = bytes.into();
            report["suffix_receipt"] = serde_json::to_value(db.commit(suffix(&db))?)?;
            report["cgroup_peak"] = fs::read_to_string("/sys/fs/cgroup/memory.peak")?
                .trim()
                .into();
            save(Path::new(&args[4]), &report)?;
            println!("checkpoint and suffix acknowledged; ready for SIGKILL");
            loop {
                std::thread::sleep(Duration::from_secs(1));
            }
        }
        "recover" => {
            let receipt = db
                .snapshot()
                .receipt("t21-after-checkpoint")
                .ok_or("missing suffix receipt")?
                .clone();
            assert_eq!(db.commit(suffix(&db))?, receipt);
            report["suffix_receipt"] = serde_json::to_value(&receipt)?;
            let export = work.join(format!("export-{count}"));
            let restored = work.join(format!("restored-{count}"));
            let started = Instant::now();
            let manifest = db.export(&export)?;
            report["export_ms"] = json!(started.elapsed().as_secs_f64() * 1000.0);
            let started = Instant::now();
            backup::restore(&export, &restored)?;
            report["restore_ms"] = json!(started.elapsed().as_secs_f64() * 1000.0);
            report["manifest"] = serde_json::to_value(manifest)?;
            let mut copy = Database::open(&restored)?;
            assert_eq!(copy.commit(suffix(&copy))?, receipt);
            let checked = verify(&copy, inputs, count)?;
            assert_eq!(checked, report["verified"]);
            report["restored_verified"] = checked;
            report["cgroup_peak"] = fs::read_to_string("/sys/fs/cgroup/memory.peak")?
                .trim()
                .into();
            save(Path::new(&args[4]), &report)?;
            println!("{count}: recovered, exported, restored and verified");
        }
        _ => return Err("unknown operation".into()),
    }
    Ok(())
}
fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(1);
    }
}
