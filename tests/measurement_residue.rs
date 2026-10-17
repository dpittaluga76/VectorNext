//! E0.6: real ingestion history, with a synthetic encoder and no model/network.
#![cfg(target_os = "linux")]
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{collections::BTreeMap, fs, path::Path};
use vectornext::{Database, contracts::*, ingestion::*, maintenance};

fn inventory(root: &Path) -> BTreeMap<String, Value> {
    fn walk(root: &Path, path: &Path, rows: &mut BTreeMap<String, Value>) {
        for entry in fs::read_dir(path).unwrap() {
            let path = entry.unwrap().path();
            let metadata = fs::symlink_metadata(&path).unwrap();
            assert!(!metadata.file_type().is_symlink());
            if metadata.is_dir() {
                walk(root, &path, rows);
            } else {
                let bytes = fs::read(&path).unwrap();
                rows.insert(
                    path.strip_prefix(root).unwrap().to_str().unwrap().into(),
                    json!({"bytes":bytes.len(),"sha256":format!("{:x}", Sha256::digest(&bytes))}),
                );
            }
        }
    }
    let mut rows = BTreeMap::new();
    walk(root, root, &mut rows);
    rows
}

fn finish(db: &mut Database, id: &str, processor: &impl Processor) -> IngestJob {
    for _ in 0..6 {
        let job = db.advance_ingestion(id, processor).unwrap();
        assert!(job.last_failure.is_none());
        if job.stage == Stage::Committed {
            return job;
        }
    }
    panic!("ingestion did not commit");
}

#[test]
fn removed_originals_remain_pinned_by_history_after_compaction() {
    let root = tempfile::tempdir().unwrap();
    let path = root.path().join("db");
    let mut db = Database::open(&path).unwrap();
    let processor = LocalProcessor {
        encoder: TestEncoder {
            max_tokens: 256,
            document_prefix: String::new(),
        },
    };
    let initial = IngestRequest {
        job_id: "residue-first".into(),
        document_id: "residue-document".into(),
        expected_revision: None,
        media_type: MediaType::Txt,
        config: IngestConfig::new(processor.encoder.space()),
    };
    let first_bytes = b"Synthetic audit: the station initially has 8 probes.";
    let second_bytes = b"Synthetic audit: the station now has 12 probes.";
    db.submit_ingestion(initial.clone(), first_bytes).unwrap();
    let first = finish(&mut db, &initial.job_id, &processor);
    let after_ingest = inventory(&path);
    let replacement = IngestRequest {
        job_id: "residue-second".into(),
        expected_revision: Some(first.draft.document.revision.clone()),
        ..initial.clone()
    };
    db.submit_ingestion(replacement.clone(), second_bytes)
        .unwrap();
    let second = finish(&mut db, &replacement.job_id, &processor);
    let after_replace = inventory(&path);
    assert_eq!(db.snapshot().documents().count(), 1);
    let remove = Batch {
        operation_id: "residue-remove".into(),
        spaces: vec![],
        mutations: vec![Mutation::Delete {
            document_id: initial.document_id.clone(),
            expected_revision: second.draft.document.revision.clone(),
        }],
    };
    let receipt = db.commit(remove.clone()).unwrap();
    assert_eq!(db.snapshot().documents().count(), 0);
    // This deliberate orphan is distinct from both retained upload originals.
    let orphan = db
        .put_original(b"Synthetic unreferenced blob; safe GC control.")
        .unwrap();
    let after_remove = inventory(&path);
    let jobs_before = db.ingestion_jobs().unwrap();
    let generation = db.snapshot().generation();
    drop(db);
    let before = maintenance::inspect(&path).unwrap();
    let compact = maintenance::compact(&path).unwrap();
    let after = maintenance::inspect(&path).unwrap();
    let after_compact = inventory(&path);
    assert_eq!(before.history_only_blobs.files, 2);
    assert_eq!(before.document_blobs.files, 0);
    assert_eq!(before.unreferenced_blobs.files, 1);
    assert_eq!(after.history_only_blobs.files, 2);
    assert_eq!(after.retained_receipts, 3);
    assert_eq!(after.retained_revision_ids, 2);
    assert_eq!(after.retained_ingestion_jobs.files, 2);
    assert_eq!(after.journal_bytes, 0);
    for (name, entry) in &after_remove {
        if name.starts_with("jobs/") {
            assert_eq!(after_compact.get(name), Some(entry));
        }
    }
    let mut db = Database::open(&path).unwrap();
    assert_eq!(db.snapshot().generation(), generation);
    assert_eq!(db.snapshot().documents().count(), 0);
    assert_eq!(db.ingestion_jobs().unwrap(), jobs_before);
    assert_eq!(
        db.originals().get(&first.draft.document.original).unwrap(),
        first_bytes
    );
    assert_eq!(
        db.originals().get(&second.draft.document.original).unwrap(),
        second_bytes
    );
    assert!(!path.join("blobs").join(&orphan.sha256).exists());
    assert_eq!(db.commit(remove.clone()).unwrap(), receipt);
    assert_eq!(
        db.commit(first.publication_batch().unwrap()).unwrap(),
        first.receipt.clone().unwrap()
    );
    assert_eq!(
        db.commit(second.publication_batch().unwrap()).unwrap(),
        second.receipt.clone().unwrap()
    );
    assert_eq!(
        db.submit_ingestion(initial.clone(), first_bytes).unwrap(),
        first
    );
    assert_eq!(
        db.submit_ingestion(replacement, second_bytes).unwrap(),
        second
    );
    assert!(db.submit_ingestion(initial, b"conflicting bytes").is_err());
    let mut conflicting = remove;
    conflicting.mutations.clear();
    assert!(db.commit(conflicting).is_err());
    let mut resurrect = first.publication_batch().unwrap();
    resurrect.operation_id = "new-operation-old-revision".into();
    assert!(db.commit(resurrect).is_err());
    assert_eq!(db.snapshot().documents().count(), 0);
    drop(db);
    let report = json!({"version":1,"policy":"preserve-history-v1","fixture":"synthetic-real-ingestion-no-GPU",
        "inventories":{"ingested":after_ingest,"replaced":after_replace,"removed":after_remove,"compacted":after_compact},
        "before":before,"compaction":compact,"after":after,
        "originals":[first.draft.document.original,second.draft.document.original],"orphan":orphan,
        "checks":{"original_bytes_preserved":true,"job_records_unchanged":true,"original_retry_receipts_preserved":true,
        "conflicting_reuse_rejected":true,"old_revision_resurrection_rejected":true,"removed_document_absent":true},
        "outside_scope":["answer-job store","browser IndexedDB","external backups","physical disk blocks"]});
    if let Ok(output) = std::env::var("VECTORNEXT_RESIDUE_REPORT") {
        use std::io::Write;
        let mut file = fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(output)
            .unwrap();
        file.write_all(&serde_json::to_vec_pretty(&report).unwrap())
            .unwrap();
    }
    println!(
        "Residue audit: 2 historical originals/jobs, 3 receipts, 2 revision reservations retained; 1 orphan removed."
    );
}
