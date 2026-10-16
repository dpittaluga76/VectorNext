use super::*;
use crate::{
    backup,
    contracts::{Batch, MediaType, Mutation},
    ingestion::{
        Encoder, IngestConfig, IngestJob, IngestRequest, LocalProcessor, Stage, TestEncoder, pdf,
    },
};
use fs2::FileExt;
use std::{
    os::unix::fs::{MetadataExt, symlink},
    process::{Command, Stdio},
    thread,
    time::{Duration, Instant},
};
use tempfile::TempDir;

fn seed(path: &Path) -> IngestJob {
    let mut db = Database::open(path).unwrap();
    let p = LocalProcessor {
        encoder: TestEncoder::default(),
    };
    db.submit_ingestion(IngestRequest {
        job_id: "exact".into(), document_id: "record".into(), expected_revision: None,
        media_type: MediaType::Json, config: IngestConfig::new(p.encoder.space()),
    }, br#"[{"id":"007","large":9007199254740993123,"decimal":0.123456789012345678901,"zero":0,"missing":null}]"#).unwrap();
    loop {
        let job = db.advance_ingestion("exact", &p).unwrap();
        if job.stage == Stage::Committed {
            return job;
        }
    }
}
fn content(db: &Database) -> Vec<u8> {
    serde_json::to_vec(&db.state).unwrap()
}
fn delete(db: &mut Database, job: &IngestJob, operation: &str) {
    db.commit(Batch {
        operation_id: operation.into(),
        spaces: vec![],
        mutations: vec![Mutation::Delete {
            document_id: job.request.document_id.clone(),
            expected_revision: job.draft.document.revision.clone(),
        }],
    })
    .unwrap();
}

#[test]
fn compaction_preserves_exact_state_history_retries_and_lock_inode() {
    let tmp = TempDir::new().unwrap();
    let path = tmp.path().join("db");
    let job = seed(&path);
    let mut db = Database::open(&path).unwrap();
    let orphan = db.put_original(b"unreferenced upload bytes").unwrap();
    let before = content(&db);
    let jobs = db.ingestion_jobs().unwrap();
    let lock_inode = fs::metadata(path.join("writer.lock")).unwrap().ino();
    db.checkpoint().unwrap();
    drop(db);
    let sibling = tmp.path().join("db.answer-jobs");
    fs::create_dir(&sibling).unwrap();
    fs::write(
        sibling.join("opaque.job"),
        br#"{"exact":"9007199254740993123","historical":true}"#,
    )
    .unwrap();
    let recorded = fs::read(sibling.join("opaque.job")).unwrap();
    let files = inventory(&path).unwrap();
    let dry = inspect(&path).unwrap();
    assert_eq!(dry.unreferenced_blobs.files, 1);
    assert_eq!(inventory(&path).unwrap(), files);
    assert!(dry.estimated_reclaimed_bytes > 0);
    let done = compact(&path).unwrap();
    assert_eq!(done.status, "compacted");
    assert_eq!(
        done.actual_reclaimed_bytes,
        Some(dry.estimated_reclaimed_bytes)
    );
    assert_eq!(fs::metadata(path.join("journal.bin")).unwrap().len(), 0);
    assert_eq!(
        fs::metadata(path.join("writer.lock")).unwrap().ino(),
        lock_inode
    );
    assert!(!path.join("blobs").join(orphan.sha256).exists());
    assert_eq!(fs::read(sibling.join("opaque.job")).unwrap(), recorded);
    let mut db = Database::open(&path).unwrap();
    assert_eq!(content(&db), before);
    assert_eq!(db.ingestion_jobs().unwrap(), jobs);
    assert_eq!(
        db.commit(job.publication_batch().unwrap()).unwrap(),
        job.receipt.clone().unwrap()
    );
    assert_eq!(
        db.submit_ingestion(
            job.request.clone(),
            &db.originals().get(&job.draft.document.original).unwrap()
        )
        .unwrap(),
        job
    );
    let mut conflict = job.publication_batch().unwrap();
    conflict.spaces.clear();
    assert!(matches!(db.commit(conflict), Err(Error::RetryConflict)));
    assert!(matches!(
        db.submit_ingestion(job.request.clone(), b"different"),
        Err(Error::RetryConflict)
    ));
    delete(&mut db, &job, "delete");
    db.checkpoint().unwrap();
    drop(db);
    compact(&path).unwrap();
    let mut db = Database::open(&path).unwrap();
    assert_eq!(db.commit_ingestion("exact").unwrap().receipt, job.receipt);
    assert_eq!(db.snapshot().documents().count(), 0);
    assert_eq!(db.snapshot().generation(), 2);
    let mut resurrection = job.publication_batch().unwrap();
    resurrection.operation_id = "new-operation-old-revision".into();
    assert!(db.commit(resurrection).is_err());
    assert_eq!(
        db.originals()
            .get(&job.draft.document.original)
            .unwrap()
            .len() as u64,
        job.draft.document.original.bytes
    );
    let export = tmp.path().join("export");
    db.export(&export).unwrap();
    let restored = tmp.path().join("restored");
    backup::restore(&export, &restored).unwrap();
    assert_eq!(content(&Database::open(&restored).unwrap()), content(&db));
}

#[test]
fn unfinished_failed_and_pdf_jobs_pin_sources_and_resume() {
    let tmp = TempDir::new().unwrap();
    let path = tmp.path().join("db");
    seed(&path);
    let mut db = Database::open(&path).unwrap();
    let p = LocalProcessor {
        encoder: TestEncoder::default(),
    };
    for (id, text) in [
        ("pending", b"Unfinished source.".as_slice()),
        ("failed", b"\xffbad UTF-8".as_slice()),
    ] {
        db.submit_ingestion(
            IngestRequest {
                job_id: id.into(),
                document_id: id.into(),
                expected_revision: None,
                media_type: MediaType::Txt,
                config: IngestConfig::new(p.encoder.space()),
            },
            text,
        )
        .unwrap();
    }
    assert!(db.advance_ingestion("failed", &p).is_err());
    let artifact =
        pdf::Artifact::from_slice(&fs::read("tests/fixtures/pdf/scanned_note.json").unwrap())
            .unwrap();
    let pdf_blob = db
        .put_original(&serde_json::to_vec(&artifact).unwrap())
        .unwrap();
    db.submit_ingestion(
        IngestRequest {
            job_id: "pdf".into(),
            document_id: "pdf".into(),
            expected_revision: None,
            media_type: MediaType::Pdf,
            config: artifact.config(p.encoder.space(), false).unwrap(),
        },
        &fs::read("evals/fixtures/scanned_note.pdf").unwrap(),
    )
    .unwrap();
    let saved = db.ingestion_jobs().unwrap();
    drop(db);
    compact(&path).unwrap();
    let mut db = Database::open(&path).unwrap();
    assert_eq!(saved, db.ingestion_jobs().unwrap());
    assert_eq!(
        db.originals().get(&pdf_blob).unwrap(),
        serde_json::to_vec(&artifact).unwrap()
    );
    while db.advance_ingestion("pending", &p).unwrap().stage != Stage::Committed {}
    let generation = db.snapshot().generation();
    db.commit_ingestion("pending").unwrap();
    assert_eq!(db.snapshot().generation(), generation);
    let adapter = pdf::PdfProcessor { local: p, artifact };
    while db.advance_ingestion("pdf", &adapter).unwrap().stage != Stage::Committed {}
}

#[test]
fn dry_run_and_apply_preserve_uncommitted_tail_until_publication() {
    let tmp = TempDir::new().unwrap();
    let path = tmp.path().join("db");
    seed(&path);
    let before = content(&Database::open(&path).unwrap());
    let mut journal = OpenOptions::new()
        .append(true)
        .open(path.join("journal.bin"))
        .unwrap();
    journal.write_all(b"VNX").unwrap();
    journal.sync_all().unwrap();
    fs::write(path.join("snapshot.pending"), b"unfinished checkpoint").unwrap();
    fs::write(path.join("blobs/original.pending"), b"unfinished original").unwrap();
    fs::write(path.join("jobs/stage.pending"), b"unfinished job").unwrap();
    let files = inventory(&path).unwrap();
    let report = inspect(&path).unwrap();
    assert_eq!(report.uncommitted_tail_bytes, 3);
    assert_eq!(inventory(&path).unwrap(), files);
    assert!(
        compact_with(&path, |stage| if stage == "before_exchange" {
            Err(std::io::Error::from_raw_os_error(libc::ENOSPC).into())
        } else {
            Ok(())
        })
        .is_err()
    );
    assert_eq!(inventory(&path).unwrap(), files);
    assert_eq!(inspect(&path).unwrap().leftover_workspaces.len(), 1);
    compact(&path).unwrap();
    assert_eq!(content(&Database::open(&path).unwrap()), before);
    assert!(!path.join("snapshot.pending").exists());
}

#[test]
fn legacy_checkpoint_compacts_and_accepts_new_commits_and_exports() {
    let tmp = TempDir::new().unwrap();
    let path = tmp.path().join("db");
    let job = seed(&path);
    let mut db = Database::open(&path).unwrap();
    let old = super::super::Checkpoint {
        journal_offset: db.committed_offset,
        journal_sha256: super::super::prefix_hash(&mut db.journal, db.committed_offset).unwrap(),
        state: db.state.as_ref().clone(),
    };
    fs::write(
        path.join("snapshot.bin"),
        crate::frame::encode(crate::frame::SNAPSHOT, &serde_json::to_vec(&old).unwrap()).unwrap(),
    )
    .unwrap();
    delete(&mut db, &job, "after-legacy");
    let expected = content(&db);
    drop(db);
    compact(&path).unwrap();
    let mut db = Database::open(&path).unwrap();
    assert_eq!(content(&db), expected);
    assert_eq!(
        db.commit(job.publication_batch().unwrap()).unwrap(),
        job.receipt.unwrap()
    );
    let p = LocalProcessor {
        encoder: TestEncoder::default(),
    };
    db.submit_ingestion(
        IngestRequest {
            job_id: "next".into(),
            document_id: "next".into(),
            expected_revision: None,
            media_type: MediaType::Txt,
            config: IngestConfig::new(p.encoder.space()),
        },
        b"New source after compaction.",
    )
    .unwrap();
    while db.advance_ingestion("next", &p).unwrap().stage != Stage::Committed {}
    assert_eq!(db.snapshot().generation(), 3);
    db.checkpoint().unwrap();
    db.export(&tmp.path().join("export")).unwrap();
    backup::restore(&tmp.path().join("export"), &tmp.path().join("restored")).unwrap();
    assert_eq!(
        content(&Database::open(tmp.path().join("restored")).unwrap()),
        content(&db)
    );
}

#[test]
fn rejects_live_writer_missing_store_symlinks_unknown_files_and_corruption() {
    let tmp = TempDir::new().unwrap();
    let path = tmp.path().join("db");
    let job = seed(&path);
    let db = Database::open(&path).unwrap();
    assert!(matches!(inspect(&path), Err(Error::Locked)));
    assert!(matches!(compact(&path), Err(Error::Locked)));
    drop(db);
    let missing = tmp.path().join("missing");
    assert!(inspect(&missing).is_err());
    assert!(!missing.exists());
    let link = tmp.path().join("link");
    symlink(&path, &link).unwrap();
    assert!(inspect(&link).is_err());
    fs::write(path.join("unknown"), b"never remove").unwrap();
    assert!(compact(&path).is_err());
    assert_eq!(fs::read(path.join("unknown")).unwrap(), b"never remove");
    fs::remove_file(path.join("unknown")).unwrap();
    let blob = path.join("blobs").join(&job.draft.document.original.sha256);
    let bytes = fs::read(&blob).unwrap();
    let external = tmp.path().join("external");
    fs::write(&external, &bytes).unwrap();
    fs::remove_file(&blob).unwrap();
    symlink(&external, &blob).unwrap();
    assert!(compact(&path).is_err());
    assert_eq!(fs::read(&external).unwrap(), bytes);
    fs::remove_file(&blob).unwrap();
    fs::write(&blob, b"corrupt").unwrap();
    assert!(inspect(&path).is_err());
}

const POINTS: &[&str] = &[
    "staging",
    "copy",
    "checkpoint_segment",
    "checkpoint_write",
    "checkpoint_sync",
    "verified",
    "before_exchange",
    "after_exchange",
    "published_sync",
    "before_cleanup",
    "cleanup_file",
    "cleanup_sync",
];

#[test]
fn injected_io_failures_recover_exact_old_or_new_state() {
    for point in POINTS {
        let tmp = TempDir::new().unwrap();
        let path = tmp.path().join("db");
        let job = seed(&path);
        let before = content(&Database::open(&path).unwrap());
        assert!(
            compact_with(&path, |at| if at == *point {
                Err(std::io::Error::from_raw_os_error(libc::ENOSPC).into())
            } else {
                Ok(())
            })
            .is_err(),
            "{point}"
        );
        let mut db = Database::open(&path).unwrap();
        assert_eq!(content(&db), before, "{point}");
        assert_eq!(db.commit_ingestion("exact").unwrap().receipt, job.receipt);
    }
}

#[test]
fn publication_keeps_old_lock_descriptors_exclusive() {
    let tmp = TempDir::new().unwrap();
    let path = tmp.path().join("db");
    seed(&path);
    let old_descriptor = OpenOptions::new()
        .read(true)
        .write(true)
        .open(path.join("writer.lock"))
        .unwrap();
    compact_with(&path, |point| {
        if point == "after_exchange" || point == "before_cleanup" {
            assert!(matches!(Database::open(&path), Err(Error::Locked)));
            assert!(old_descriptor.try_lock_exclusive().is_err());
        }
        Ok(())
    })
    .unwrap();
    old_descriptor.try_lock_exclusive().unwrap();
    assert!(matches!(Database::open(&path), Err(Error::Locked)));
    FileExt::unlock(&old_descriptor).unwrap();
    Database::open(&path).unwrap();
}

#[test]
fn crash_child() {
    let Ok(path) = std::env::var("VNX_MAINTENANCE_TEST_PATH") else {
        return;
    };
    let point = std::env::var("VNX_MAINTENANCE_TEST_POINT").unwrap();
    let path = Path::new(&path);
    compact_with(path, |at| {
        if at == point {
            fs::write(path.parent().unwrap().join("ready"), at).unwrap();
            loop {
                thread::sleep(Duration::from_secs(1));
            }
        }
        Ok(())
    })
    .unwrap();
    panic!("crash boundary did not run");
}

#[test]
fn killed_process_at_each_boundary_reopens_and_retries_without_data_loss() {
    for point in POINTS {
        let tmp = TempDir::new().unwrap();
        let path = tmp.path().join("db");
        let job = seed(&path);
        let before = content(&Database::open(&path).unwrap());
        let mut child = Command::new(std::env::current_exe().unwrap())
            .args([
                "--exact",
                "storage::maintenance::tests::crash_child",
                "--nocapture",
            ])
            .env("VNX_MAINTENANCE_TEST_PATH", &path)
            .env("VNX_MAINTENANCE_TEST_POINT", point)
            .stdout(Stdio::null())
            .stderr(Stdio::inherit())
            .spawn()
            .unwrap();
        let deadline = Instant::now() + Duration::from_secs(15);
        while !tmp.path().join("ready").exists() && Instant::now() < deadline {
            if child.try_wait().unwrap().is_some() {
                panic!("child exited before {point}");
            }
            thread::sleep(Duration::from_millis(10));
        }
        let ready = tmp.path().join("ready").exists();
        child.kill().unwrap();
        child.wait().unwrap();
        assert!(ready, "child did not reach {point}");
        let mut db = Database::open(&path).unwrap();
        assert_eq!(content(&db), before, "{point}");
        assert_eq!(db.commit_ingestion("exact").unwrap().receipt, job.receipt);
    }
}
