#![cfg(target_os = "linux")]
mod support;
use std::{fs, process::Command};
use support::*;
use vectornext::{Database, backup, contracts::*, maintenance, search::*};

#[test]
fn repeated_replacements_and_deletes_reclaim_payloads_preserve_search_and_cli() {
    let root = tempfile::tempdir().unwrap();
    let path = root.path().join("db");
    let mut db = Database::open(&path).unwrap();
    let space = space(128);
    for revision in 0..8 {
        for id in 0..8 {
            let texts: Vec<_> = (0..32).map(|chunk| format!("Approved record {id}, revision {revision}, passage {chunk}. Exact count 9007199254740993123. {}", "Original source evidence. ".repeat(8))).collect();
            let mut vectors = vec![vec![0.1; 128]; 32];
            for (n, v) in vectors.iter_mut().enumerate() {
                v[n] = 1.0;
            }
            let doc = document(
                &mut db,
                &format!("doc-{id}"),
                &format!("r{revision}"),
                &texts.iter().map(String::as_str).collect::<Vec<_>>(),
                vectors,
                &space,
            );
            publish(
                &mut db,
                doc,
                &space,
                (revision > 0)
                    .then(|| format!("r{}", revision - 1))
                    .as_deref(),
            );
        }
    }
    for id in 0..4 {
        db.commit(Batch {
            operation_id: format!("delete-{id}"),
            spaces: vec![],
            mutations: vec![Mutation::Delete {
                document_id: format!("doc-{id}"),
                expected_revision: "r7".into(),
            }],
        })
        .unwrap();
    }
    let request = SearchRequest::hybrid(
        "Approved exact count",
        QueryVector {
            space_id: space.id(),
            values: vec![0.1; 128],
        },
    );
    let before = SearchIndex::build(db.snapshot(), space.id(), KeywordConfig::default())
        .unwrap()
        .search(&request)
        .unwrap();
    let docs_before = serde_json::to_vec(&db.snapshot().documents().collect::<Vec<_>>()).unwrap();
    let generation = db.snapshot().generation();
    drop(db);
    let cli = env!("CARGO_BIN_EXE_vectornext");
    let plan = Command::new(cli)
        .arg("storage-plan")
        .arg(&path)
        .output()
        .unwrap();
    assert!(
        plan.status.success(),
        "{}",
        String::from_utf8_lossy(&plan.stderr)
    );
    let report: serde_json::Value = serde_json::from_slice(&plan.stdout).unwrap();
    assert_eq!(report["unreferenced_blobs"]["files"], 60);
    let invalid = Command::new(cli)
        .arg("compact")
        .arg(&path)
        .output()
        .unwrap();
    assert!(!invalid.status.success()); // An explicit --apply is mandatory.
    let done = Command::new(cli)
        .arg("compact")
        .arg(&path)
        .arg("--apply")
        .output()
        .unwrap();
    assert!(
        done.status.success(),
        "{}",
        String::from_utf8_lossy(&done.stderr)
    );
    let result: serde_json::Value = serde_json::from_slice(&done.stdout).unwrap();
    println!("T38 churn measurement: {result}");
    assert!(
        result["actual_reclaimed_bytes"].as_u64().unwrap()
            > result["store_bytes_before"].as_u64().unwrap() / 2
    );
    assert_eq!(result["retained_receipts"], 68);
    assert_eq!(result["retained_revision_ids"], 64);
    let mut db = Database::open(&path).unwrap();
    assert_eq!(db.snapshot().generation(), generation);
    assert_eq!(
        serde_json::to_vec(&db.snapshot().documents().collect::<Vec<_>>()).unwrap(),
        docs_before
    );
    let after = SearchIndex::build(db.snapshot(), space.id(), KeywordConfig::default())
        .unwrap()
        .search(&request)
        .unwrap();
    assert_eq!(
        serde_json::to_value(before).unwrap(),
        serde_json::to_value(after).unwrap()
    );
    db.export(&root.path().join("export")).unwrap();
    backup::restore(&root.path().join("export"), &root.path().join("restore")).unwrap();
    drop(db);
    let repeated = maintenance::compact(&path).unwrap();
    assert_eq!(repeated.actual_reclaimed_bytes, Some(0));
    assert_eq!(fs::metadata(path.join("journal.bin")).unwrap().len(), 0);
}

#[test]
fn current_processing_metadata_pins_artifacts_by_hash_key_or_value() {
    let root = tempfile::tempdir().unwrap();
    let path = root.path().join("db");
    let mut db = Database::open(&path).unwrap();
    let space = space(2);
    let by_key = db.put_original(b"metadata key artifact").unwrap();
    let by_value = db.put_original(b"metadata value artifact").unwrap();
    let orphan = db.put_original(b"not referenced").unwrap();
    let mut doc = document(
        &mut db,
        "doc",
        "revision",
        &["Source evidence."],
        vec![vec![1.0, 0.0]],
        &space,
    );
    doc.processing.insert(
        "attachments".into(),
        serde_json::json!({by_key.sha256.clone(): {"nested": [by_value.sha256.clone()]}}),
    );
    publish(&mut db, doc, &space, None);
    drop(db);
    let report = maintenance::compact(&path).unwrap();
    assert_eq!(report.document_blobs.files, 3);
    assert_eq!(report.unreferenced_blobs.files, 1);
    let db = Database::open(&path).unwrap();
    assert!(db.originals().get(&by_key).is_ok());
    assert!(db.originals().get(&by_value).is_ok());
    assert!(!path.join("blobs").join(orphan.sha256).exists());
}
