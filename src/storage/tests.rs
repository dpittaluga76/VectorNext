use super::*;
use serde_json::{Value, json};
use std::{
    io::Cursor,
    process::{Command, Stdio},
    time::{Duration, Instant},
};
use tempfile::TempDir;

fn space(dimensions: usize) -> EmbeddingSpace {
    EmbeddingSpace {
        model: "synthetic/supplied-vectors".into(),
        revision: "fixture-v1".into(),
        artifact_sha256: "a".repeat(64),
        tokenizer: "fixture-v1".into(),
        preprocessing: "identity-v1".into(),
        dimensions,
        max_tokens: 256,
        query_prefix: String::new(),
        document_prefix: String::new(),
        normalization: Normalization::L2,
    }
}

fn fixture(db: &mut Database, id: &str, revision: &str, dimensions: usize) -> DocumentRevision {
    let text = "Pelé scored 3 goals. Synthetic data.";
    let original = db.put_original(text.as_bytes()).unwrap();
    let source = SourceRef {
        revision: revision.into(),
        locator: Locator::Text {
            encoding: "UTF-8".into(),
            bytes: ByteRange {
                start: 0,
                end: original.bytes,
            },
            line_start: 1,
            line_end: 1,
            mappings: vec![TextMapping {
                normalized: ByteRange {
                    start: 0,
                    end: text.len() as u64,
                },
                original: ByteRange {
                    start: 0,
                    end: original.bytes,
                },
            }],
        },
    };
    let mut vector = vec![0.0; dimensions];
    vector[0] = 1.0;
    DocumentRevision {
        document_id: id.into(),
        revision: revision.into(),
        original,
        media_type: MediaType::Txt,
        processing: BTreeMap::from([("chunker".into(), json!("fixture-v1"))]),
        required_spaces: BTreeSet::from([space(dimensions).id()]),
        blocks: vec![Block {
            id: "b1".into(),
            kind: BlockKind::Paragraph,
            parent: None,
            text: text.into(),
            sources: vec![source.clone()],
        }],
        chunks: vec![Chunk {
            id: "c1".into(),
            spans: vec![BlockSpan {
                block_id: "b1".into(),
                bytes: ByteRange {
                    start: 0,
                    end: text.len() as u64,
                },
            }],
            evidence: text.into(),
            representation: Representation::NormalizedText,
            sources: vec![source.clone()],
            structural_context: "Synthetic match".into(),
            generated_context: Some(GeneratedContext {
                text: "A fictional match.".into(),
                model: "fixture-model@v1".into(),
                prompt_version: "v1".into(),
                source_scope: vec![source.clone()],
            }),
            attributes: BTreeMap::from([(
                "goals".into(),
                Attribute {
                    value: json!(3),
                    sources: vec![source],
                    derivation: Derivation::Source,
                },
            )]),
            parent: None,
            previous: None,
            next: None,
            vectors: BTreeMap::from([(space(dimensions).id(), vector)]),
        }],
    }
}

fn batch(operation: &str, document: DocumentRevision, expected: Option<&str>) -> Batch {
    let dimensions = document.chunks[0].vectors.values().next().unwrap().len();
    Batch {
        operation_id: operation.into(),
        spaces: vec![space(dimensions)],
        mutations: vec![Mutation::Replace {
            expected_revision: expected.map(str::to_owned),
            document: Box::new(document),
        }],
    }
}

fn delete(operation: &str, id: &str, revision: &str) -> Batch {
    Batch {
        operation_id: operation.into(),
        spaces: vec![],
        mutations: vec![Mutation::Delete {
            document_id: id.into(),
            expected_revision: revision.into(),
        }],
    }
}

fn seed() -> (TempDir, Database, Batch) {
    let dir = TempDir::new().unwrap();
    let mut db = Database::open(dir.path()).unwrap();
    let document = fixture(&mut db, "match", "r1", 384);
    let first = batch("insert", document, None);
    db.commit(first.clone()).unwrap();
    (dir, db, first)
}

#[test]
fn exact_typed_round_trip_and_originals() {
    let dir = TempDir::new().unwrap();
    let mut db = Database::open(dir.path()).unwrap();
    let mut document = fixture(&mut db, "structured", "json-r1", 3);
    let original = br#"{"id":"007","n":123456789012345678901234567890,"decimal":0.12345678901234567890123456789,"null":null,"zero":0,"nested":{"year":1954}}"#;
    document.original = db.put_original(original).unwrap();
    document.media_type = MediaType::Json;
    let source = SourceRef {
        revision: "json-r1".into(),
        locator: Locator::Json {
            pointer: "".into(),
            record_id: Some(json!("007")),
        },
    };
    document.blocks[0].sources = vec![source.clone()];
    document.blocks[0].kind = BlockKind::JsonSubtree;
    document.chunks[0].sources = vec![source.clone()];
    document.chunks[0].representation = Representation::JsonSerialization;
    document.chunks[0]
        .generated_context
        .as_mut()
        .unwrap()
        .source_scope = vec![source.clone()];
    let values: BTreeMap<String, Value> = serde_json::from_slice(original).unwrap();
    document.chunks[0].attributes = values
        .into_iter()
        .map(|(key, value)| {
            (
                key,
                Attribute {
                    value,
                    sources: vec![source.clone()],
                    derivation: Derivation::Deterministic {
                        version: "json-v1".into(),
                    },
                },
            )
        })
        .collect();
    let vector = vec![0.6_f32, 0.8_f32, -0.0_f32];
    document.chunks[0]
        .vectors
        .insert(space(3).id(), vector.clone());
    db.commit(batch("exact", document.clone(), None)).unwrap();
    for checkpoint in [false, true] {
        if checkpoint {
            db.checkpoint().unwrap();
        }
        drop(db);
        db = Database::open(dir.path()).unwrap();
        let snapshot = db.snapshot();
        let stored = snapshot.document("structured").unwrap();
        assert_eq!(stored, &document);
        let attributes = &stored.chunks[0].attributes;
        assert_eq!(
            attributes["n"].value.to_string(),
            "123456789012345678901234567890"
        );
        assert_eq!(
            attributes["decimal"].value.to_string(),
            "0.12345678901234567890123456789"
        );
        assert_eq!(attributes["id"].value, json!("007"));
        assert!(attributes["null"].value.is_null());
        assert!(!attributes.contains_key("missing"));
        assert_eq!(attributes["zero"].value, json!(0));
        assert_eq!(
            stored.chunks[0].vectors[&space(3).id()]
                .iter()
                .map(|f| f.to_bits())
                .collect::<Vec<_>>(),
            vector.iter().map(|f| f.to_bits()).collect::<Vec<_>>()
        );
        assert_eq!(db.originals().get(&stored.original).unwrap(), original);
    }
}

#[test]
fn pdf_multiple_pages_and_provenance_round_trip() {
    let dir = TempDir::new().unwrap();
    let mut db = Database::open(dir.path()).unwrap();
    let mut document = fixture(&mut db, "pdf", "p1", 2);
    document.media_type = MediaType::Pdf;
    document.original = db
        .put_original(b"synthetic placeholder; parser is outside T03")
        .unwrap();
    let sources: Vec<_> = [1, 2]
        .into_iter()
        .map(|page| SourceRef {
            revision: "p1".into(),
            locator: Locator::Pdf {
                page,
                bbox: [20.0, 30.5, 200.0, 100.0],
                extraction: if page == 1 {
                    PdfExtraction::Native
                } else {
                    PdfExtraction::Ocr
                },
                diagnostics: BTreeMap::from([("confidence".into(), json!(0.8))]),
            },
        })
        .collect();
    document.blocks[0].sources = sources.clone();
    let chunk = &mut document.chunks[0];
    chunk.sources = sources.clone();
    chunk.representation = Representation::PdfText;
    chunk.attributes.get_mut("goals").unwrap().sources = sources.clone();
    chunk.generated_context.as_mut().unwrap().source_scope = sources;
    db.commit(batch("pdf", document.clone(), None)).unwrap();
    drop(db);
    let db = Database::open(dir.path()).unwrap();
    assert_eq!(db.snapshot().document("pdf").unwrap(), &document);
}

#[test]
fn replacement_and_delete_keep_reader_generations_atomic() {
    let (_dir, mut db, _) = seed();
    let before = db.snapshot();
    let replacement = fixture(&mut db, "match", "r2", 384);
    let extra = fixture(&mut db, "second", "s1", 384);
    let mut change = batch("replace-and-add", replacement, Some("r1"));
    change.mutations.push(Mutation::Replace {
        expected_revision: None,
        document: Box::new(extra),
    });
    db.commit(change).unwrap();
    let after = db.snapshot();
    std::thread::spawn(move || {
        assert_eq!(before.generation(), 1);
        assert_eq!(before.document("match").unwrap().revision, "r1");
        assert_eq!(before.documents().count(), 1);
    })
    .join()
    .unwrap();
    assert_eq!(after.generation(), 2);
    assert_eq!(after.document("match").unwrap().revision, "r2");
    assert_eq!(after.documents().count(), 2);
    db.commit(delete("delete", "match", "r2")).unwrap();
    assert!(db.snapshot().document("match").is_none());
    assert!(after.document("match").is_some());
    assert_eq!(db.snapshot().generation(), 3);
}

#[test]
fn retries_conflicts_and_revision_tombstones_survive_checkpoints() {
    let (dir, mut db, first) = seed();
    let bytes = fs::metadata(dir.path().join("journal.bin")).unwrap().len();
    let receipt = db.commit(first.clone()).unwrap();
    assert_eq!(receipt.generation, 1);
    assert_eq!(
        bytes,
        fs::metadata(dir.path().join("journal.bin")).unwrap().len()
    );
    let mut different = first.clone();
    different.spaces[0].query_prefix = "changed".into();
    assert!(matches!(db.commit(different), Err(Error::RetryConflict)));
    let newer = fixture(&mut db, "match", "r2", 384);
    assert!(matches!(
        db.commit(batch("stale", newer, Some("wrong"))),
        Err(Error::Conflict(_))
    ));
    db.commit(delete("delete", "match", "r1")).unwrap();
    db.checkpoint().unwrap();
    drop(db);
    let mut db = Database::open(dir.path()).unwrap();
    assert_eq!(db.commit(first).unwrap(), receipt);
    assert!(db.snapshot().document("match").is_none());
    assert_eq!(
        db.commit(delete("delete", "match", "r1"))
            .unwrap()
            .generation,
        2
    );
    assert!(matches!(
        db.commit(delete("missing", "match", "r1")),
        Err(Error::Conflict(_))
    ));
    let reused = fixture(&mut db, "match", "r1", 384);
    assert!(matches!(
        db.commit(batch("reuse", reused, None)),
        Err(Error::Invalid(_))
    ));
    let recreated = fixture(&mut db, "match", "r3", 384);
    db.commit(batch("recreate", recreated, None)).unwrap();
}

#[test]
fn invalid_batch_never_partially_publishes() {
    let (_dir, mut db, _) = seed();
    let good = fixture(&mut db, "match", "r2", 384);
    let mut bad = fixture(&mut db, "broken", "r1", 384);
    bad.chunks[0].vectors.clear();
    let mut change = batch("atomic", good, Some("r1"));
    change.mutations.push(Mutation::Replace {
        expected_revision: None,
        document: Box::new(bad),
    });
    assert!(db.commit(change).is_err());
    assert_eq!(db.snapshot().generation(), 1);
    assert_eq!(db.snapshot().document("match").unwrap().revision, "r1");
    assert!(db.snapshot().document("broken").is_none());
    assert!(db.snapshot().receipt("atomic").is_none());
}

#[test]
fn incompatible_spaces_vectors_and_changed_preprocessing_are_explicit() {
    let (_dir, mut db, _) = seed();
    let mut other = space(384);
    other.query_prefix = "query: ".into();
    assert_ne!(space(384).id(), other.id());
    assert!(
        db.snapshot()
            .validate_query_vector(&other.id(), &vec![1.0; 384])
            .is_err()
    );
    let mut invalid = fixture(&mut db, "bad", "r1", 384);
    invalid.required_spaces = BTreeSet::from([other.id()]);
    invalid.chunks[0].vectors = BTreeMap::from([(other.id(), vec![1.0; 384])]);
    assert!(db.commit(batch("unknown", invalid, None)).is_err());
    for vector in [
        vec![1.0],
        vec![0.0; 384],
        vec![f32::NAN; 384],
        vec![f32::INFINITY; 384],
        vec![1.0; 384],
    ] {
        let mut invalid = fixture(&mut db, "bad", "r1", 384);
        invalid.chunks[0].vectors.insert(space(384).id(), vector);
        assert!(db.commit(batch("bad-vector", invalid, None)).is_err());
    }
    let different_dimension = fixture(&mut db, "two", "r1", 2);
    db.commit(batch("two", different_dimension, None)).unwrap();
    assert!(db.snapshot().space(&space(384).id()).is_some());
    assert!(db.snapshot().space(&space(2).id()).is_some());
    db.snapshot()
        .validate_query_vector(&space(2).id(), &[0.6, 0.8])
        .unwrap();
    assert!(
        db.snapshot()
            .validate_query_vector(&space(384).id(), &[0.6, 0.8])
            .is_err()
    );
}

#[test]
fn bad_provenance_spans_hierarchy_and_duplicate_ids_are_rejected() {
    let (_dir, mut db, _) = seed();
    let base = fixture(&mut db, "bad", "r1", 384);
    let mut cases = vec![];
    let mut d = base.clone();
    d.chunks[0].sources[0].revision = "other".into();
    cases.push(d);
    let mut d = base.clone();
    d.chunks[0].spans[0].bytes.start = 4;
    cases.push(d); // inside é
    let mut d = base.clone();
    d.blocks[0].parent = Some("b1".into());
    cases.push(d);
    let mut d = base.clone();
    d.chunks[0].parent = Some("missing".into());
    cases.push(d);
    let mut d = base.clone();
    d.chunks.push(d.chunks[0].clone());
    cases.push(d);
    let mut d = base.clone();
    d.chunks[0]
        .attributes
        .get_mut("goals")
        .unwrap()
        .sources
        .clear();
    cases.push(d);
    let mut d = base.clone();
    d.original.sha256 = "../unsafe".into();
    cases.push(d);
    let mut d = base.clone();
    d.chunks[0].sources[0].locator = Locator::Json {
        pointer: "/bad~2".into(),
        record_id: None,
    };
    cases.push(d);
    let mut d = base.clone();
    d.blocks[0].sources[0].locator = Locator::Pdf {
        page: 0,
        bbox: [0.0, 0.0, f64::NAN, 4.0],
        extraction: PdfExtraction::Native,
        diagnostics: BTreeMap::new(),
    };
    cases.push(d);
    for invalid in cases {
        assert!(db.commit(batch("invalid", invalid, None)).is_err());
    }
    let mut duplicate = batch("duplicate", base, None);
    duplicate.mutations.push(duplicate.mutations[0].clone());
    assert!(db.commit(duplicate).is_err());
    assert_eq!(db.snapshot().generation(), 1);
}

#[test]
fn every_byte_truncation_recovers_only_committed_batches_then_accepts_retry() {
    let (dir, mut db, _) = seed();
    let first_end = db.committed_offset as usize;
    let replacement = fixture(&mut db, "match", "r2", 384);
    let second = batch("replace", replacement, Some("r1"));
    db.commit(second.clone()).unwrap();
    drop(db);
    let wal_path = dir.path().join("journal.bin");
    let complete = fs::read(&wal_path).unwrap();
    for end in first_end..=complete.len() {
        fs::write(&wal_path, &complete[..end]).unwrap();
        let mut recovered = Database::open(dir.path()).unwrap();
        let expected = if end == complete.len() { 2 } else { 1 };
        assert_eq!(recovered.snapshot().generation(), expected, "cut at {end}");
        assert_eq!(
            recovered.committed_offset,
            if expected == 2 {
                complete.len() as u64
            } else {
                first_end as u64
            }
        );
        // Retry a sample of torn writes, including complete prepare and almost-complete commit.
        if end % 97 == 0 || end >= complete.len() - 4 {
            assert_eq!(recovered.commit(second.clone()).unwrap().generation, 2);
        }
    }
    // Truncations of the first batch also recover to a genuinely empty database.
    for end in 0..first_end {
        fs::write(&wal_path, &complete[..end]).unwrap();
        let recovered = Database::open(dir.path()).unwrap();
        assert_eq!(recovered.snapshot().generation(), 0, "first cut at {end}");
        assert_eq!(fs::metadata(&wal_path).unwrap().len(), 0);
    }
}

#[test]
fn complete_corruption_is_never_discarded_as_a_torn_tail() {
    let (dir, db, _) = seed();
    drop(db);
    let wal = dir.path().join("journal.bin");
    let original = fs::read(&wal).unwrap();
    for position in [0, 8, 10, 12, 20, 24, original.len() / 2, original.len() - 1] {
        let mut corrupt = original.clone();
        corrupt[position] ^= 0x80;
        fs::write(&wal, &corrupt).unwrap();
        assert!(
            matches!(Database::open(dir.path()), Err(Error::Corrupt(_))),
            "at {position}"
        );
        assert_eq!(fs::read(&wal).unwrap(), corrupt);
    }
    fs::write(&wal, &original).unwrap();
}

#[test]
fn complete_but_mismatched_commits_and_repeated_sequences_fail() {
    let (dir, db, _) = seed();
    drop(db);
    let wal = dir.path().join("journal.bin");
    let original = fs::read(&wal).unwrap();
    let mut reader = Cursor::new(&original);
    let ReadFrame::Complete { payload, .. } = frame::read(&mut reader).unwrap() else {
        panic!()
    };
    let prepare = frame::encode(frame::PREPARE, &payload).unwrap();
    for commit in [
        Commit {
            generation: 2,
            prepare_sha256: sha256(&payload),
        },
        Commit {
            generation: 1,
            prepare_sha256: "b".repeat(64),
        },
    ] {
        let mut changed = prepare.clone();
        changed
            .extend(frame::encode(frame::COMMIT, &serde_json::to_vec(&commit).unwrap()).unwrap());
        fs::write(&wal, changed).unwrap();
        assert!(Database::open(dir.path()).is_err());
    }
    let mut duplicate = original.clone();
    duplicate.extend(&original);
    fs::write(&wal, duplicate).unwrap();
    assert!(Database::open(dir.path()).is_err());
}

#[test]
fn journal_failures_poison_writer_and_preserve_old_readers() {
    for fault in [
        Fault::PrepareWrite,
        Fault::PrepareSync,
        Fault::CommitWrite,
        Fault::CommitSync,
    ] {
        let (dir, mut db, _) = seed();
        let old = db.snapshot();
        let replacement = fixture(&mut db, "match", "r2", 384);
        let second = batch("replace", replacement, Some("r1"));
        db.fail_at = Some(fault);
        assert!(db.commit(second.clone()).is_err());
        assert_eq!(db.snapshot().generation(), 1);
        assert_eq!(old.document("match").unwrap().revision, "r1");
        assert!(matches!(db.commit(second.clone()), Err(Error::Poisoned)));
        assert!(matches!(db.checkpoint(), Err(Error::Poisoned)));
        assert!(matches!(db.put_original(b"new"), Err(Error::Poisoned)));
        drop(db);
        let mut recovered = Database::open(dir.path()).unwrap();
        let expected = if matches!(fault, Fault::CommitWrite | Fault::CommitSync) {
            2
        } else {
            1
        };
        assert_eq!(recovered.snapshot().generation(), expected);
        assert_eq!(recovered.commit(second).unwrap().generation, 2);
    }
}

#[test]
fn actual_write_errors_poison_without_publishing() {
    let (dir, mut db, _) = seed();
    let replacement = fixture(&mut db, "match", "r2", 384);
    let second = batch("replace", replacement, Some("r1"));
    // A read-only descriptor produces an actual OS write error before any bytes append.
    db.journal = File::open(dir.path().join("journal.bin")).unwrap();
    assert!(matches!(db.commit(second.clone()), Err(Error::Io(_))));
    assert_eq!(db.snapshot().generation(), 1);
    assert!(matches!(db.commit(second.clone()), Err(Error::Poisoned)));
    drop(db);
    let mut recovered = Database::open(dir.path()).unwrap();
    assert_eq!(recovered.commit(second).unwrap().generation, 2);
    // An unusable temporary checkpoint path must not change committed state.
    fs::create_dir(dir.path().join("snapshot.pending")).unwrap();
    assert!(matches!(recovered.checkpoint(), Err(Error::Io(_))));
    assert!(matches!(recovered.checkpoint(), Err(Error::Poisoned)));
    drop(recovered);
    assert_eq!(
        Database::open(dir.path()).unwrap().snapshot().generation(),
        2
    );
}

#[test]
fn snapshot_failures_recover_old_or_new_checkpoint_plus_journal() {
    for fault in [
        Fault::SnapshotChunk,
        Fault::SnapshotWrite,
        Fault::SnapshotSync,
        Fault::SnapshotRename,
        Fault::SnapshotDirSync,
    ] {
        let (dir, mut db, first) = seed();
        db.checkpoint().unwrap();
        let document = fixture(&mut db, "match", "r2", 384);
        let second = batch("replace", document, Some("r1"));
        db.commit(second.clone()).unwrap();
        db.fail_at = Some(fault);
        assert!(db.checkpoint().is_err());
        assert!(matches!(db.commit(first.clone()), Err(Error::Poisoned)));
        drop(db);
        let mut recovered = Database::open(dir.path()).unwrap();
        assert_eq!(recovered.snapshot().generation(), 2);
        assert_eq!(recovered.commit(first).unwrap().generation, 1);
        assert_eq!(recovered.commit(second).unwrap().generation, 2);
        let third = fixture(&mut recovered, "match", "r3", 384);
        recovered.commit(batch("third", third, Some("r2"))).unwrap();
        recovered.checkpoint().unwrap();
        drop(recovered);
        assert_eq!(
            Database::open(dir.path()).unwrap().snapshot().generation(),
            3
        );
    }
}

#[test]
fn legacy_checkpoint_upgrades_with_suffix_receipts_and_tombstones() {
    let (dir, mut db, first) = seed();
    db.commit(delete("remove", "match", "r1")).unwrap();
    let legacy = Checkpoint {
        journal_offset: db.committed_offset,
        journal_sha256: prefix_hash(&mut db.journal, db.committed_offset).unwrap(),
        state: db.state.as_ref().clone(),
    };
    fs::write(
        dir.path().join("snapshot.bin"),
        frame::encode(frame::SNAPSHOT, &serde_json::to_vec(&legacy).unwrap()).unwrap(),
    )
    .unwrap();
    let replacement = fixture(&mut db, "match", "r2", 384);
    db.commit(batch("new-revision", replacement, None)).unwrap();
    let expected = serde_json::to_vec(&db.state).unwrap();
    drop(db);
    let mut upgraded = Database::open(dir.path()).unwrap();
    assert_eq!(serde_json::to_vec(&upgraded.state).unwrap(), expected);
    assert_eq!(upgraded.commit(first.clone()).unwrap().generation, 1);
    upgraded.checkpoint().unwrap();
    let mut checkpoint_file = File::open(dir.path().join("snapshot.bin")).unwrap();
    assert!(matches!(
        frame::read(&mut checkpoint_file).unwrap(),
        ReadFrame::Complete {
            kind: frame::SNAPSHOT_HEADER,
            ..
        }
    ));
    drop(upgraded);
    let mut reopened = Database::open(dir.path()).unwrap();
    assert_eq!(serde_json::to_vec(&reopened.state).unwrap(), expected);
    assert_eq!(reopened.commit(first).unwrap().generation, 1);
    let reused = fixture(&mut reopened, "match", "r1", 384);
    assert!(reopened.commit(batch("reuse", reused, Some("r2"))).is_err());
}

#[test]
fn checkpoint_export_restore_above_legacy_frame_limit() {
    let root = TempDir::new().unwrap();
    let mut db = Database::open(root.path().join("db")).unwrap();
    for i in 0..33 {
        let id = format!("large-{i}");
        let mut document = fixture(&mut db, &id, "r1", 3);
        document
            .processing
            .insert("padding".into(), json!("x".repeat(2 * 1024 * 1024)));
        document.processing.insert(
            "exact".into(),
            serde_json::from_str::<Value>(
                r#"[9007199254740993.00000000000001,123456789012345678901234567890,null,0]"#,
            )
            .unwrap(),
        );
        db.commit(batch(&id, document, None)).unwrap();
    }
    let before = db.snapshot();
    let destination = root.path().join("export");
    let manifest = db.export(&destination).unwrap();
    assert!(manifest.files["snapshot.bin"].bytes > frame::MAX_PAYLOAD);
    let restored = root.path().join("restored");
    crate::backup::restore(&destination, &restored).unwrap();
    let mut recovered = Database::open(restored).unwrap();
    assert_eq!(before.generation(), recovered.snapshot().generation());
    for document in before.documents() {
        assert_eq!(
            recovered
                .snapshot()
                .document(&document.document_id)
                .unwrap(),
            document
        );
        assert_eq!(
            recovered
                .commit(batch(&document.document_id, document.clone(), None))
                .unwrap(),
            *before.receipt(&document.document_id).unwrap()
        );
    }
}

#[test]
fn failed_segment_write_keeps_published_checkpoint_and_replays_suffix() {
    let (dir, mut db, first) = seed();
    db.checkpoint().unwrap();
    let published = fs::read(dir.path().join("snapshot.bin")).unwrap();
    let mut document = fixture(&mut db, "match", "r2", 384);
    document
        .processing
        .insert("padding".into(), json!("雪".repeat(800_000)));
    let second = batch("large-revision", document, Some("r1"));
    db.commit(second.clone()).unwrap();
    let expected = serde_json::to_vec(&db.state).unwrap();
    db.fail_at = Some(Fault::SnapshotChunk);
    assert!(db.checkpoint().is_err());
    assert_eq!(
        fs::read(dir.path().join("snapshot.bin")).unwrap(),
        published
    );
    assert!(
        fs::metadata(dir.path().join("snapshot.pending"))
            .unwrap()
            .len()
            > 1024 * 1024
    );
    assert!(matches!(db.commit(second.clone()), Err(Error::Poisoned)));
    drop(db);
    let mut recovered = Database::open(dir.path()).unwrap();
    assert_eq!(serde_json::to_vec(&recovered.state).unwrap(), expected);
    assert_eq!(recovered.commit(first).unwrap().generation, 1);
    assert_eq!(recovered.commit(second).unwrap().generation, 2);
    recovered.checkpoint().unwrap();
    drop(recovered);
    assert_eq!(
        serde_json::to_vec(&Database::open(dir.path()).unwrap().state).unwrap(),
        expected
    );
}

#[test]
fn checkpoints_replay_suffix_and_reject_corruption_missing_prefix_and_blobs() {
    let (dir, mut db, _) = seed();
    let original_ref = db.snapshot().document("match").unwrap().original.clone();
    db.checkpoint().unwrap();
    let second = fixture(&mut db, "match", "r2", 384);
    db.commit(batch("second", second, Some("r1"))).unwrap();
    drop(db);
    let snapshot_path = dir.path().join("snapshot.bin");
    let snapshot = fs::read(&snapshot_path).unwrap();
    let wal_path = dir.path().join("journal.bin");
    let wal = fs::read(&wal_path).unwrap();
    assert_eq!(
        Database::open(dir.path()).unwrap().snapshot().generation(),
        2
    );
    fs::write(
        dir.path().join("snapshot.pending"),
        b"partial temporary data",
    )
    .unwrap();
    assert!(Database::open(dir.path()).is_ok());
    for end in [0, 12, snapshot.len() - 1] {
        fs::write(&snapshot_path, &snapshot[..end]).unwrap();
        assert!(Database::open(dir.path()).is_err());
    }
    let mut corrupt = snapshot.clone();
    corrupt[30] ^= 1;
    fs::write(&snapshot_path, corrupt).unwrap();
    assert!(Database::open(dir.path()).is_err());
    fs::write(&snapshot_path, &snapshot).unwrap();
    fs::write(&wal_path, &wal[..10]).unwrap();
    assert!(Database::open(dir.path()).is_err());
    let mut corrupt = wal.clone();
    corrupt[30] ^= 1;
    fs::write(&wal_path, corrupt).unwrap();
    assert!(Database::open(dir.path()).is_err());
    fs::write(&wal_path, &wal).unwrap();
    fs::write(
        dir.path().join("blobs").join(&original_ref.sha256),
        b"corrupt",
    )
    .unwrap();
    assert!(Database::open(dir.path()).is_err());
    fs::remove_file(dir.path().join("blobs").join(&original_ref.sha256)).unwrap();
    assert!(Database::open(dir.path()).is_err());
}

#[test]
fn missing_journal_or_format_is_not_treated_as_an_empty_database() {
    for name in ["journal.bin", "FORMAT"] {
        let (dir, db, _) = seed();
        drop(db);
        fs::remove_file(dir.path().join(name)).unwrap();
        assert!(matches!(Database::open(dir.path()), Err(Error::Corrupt(_))));
    }
}

#[test]
fn blobs_are_content_addressed_verified_and_required_before_commit() {
    let (_dir, mut db, _) = seed();
    let first = db.put_original(b"same bytes").unwrap();
    assert_eq!(first, db.put_original(b"same bytes").unwrap());
    assert_eq!(db.originals().get(&first).unwrap(), b"same bytes");
    let mut doc = fixture(&mut db, "new", "r1", 384);
    doc.original.sha256 = "f".repeat(64);
    assert!(db.commit(batch("missing-blob", doc, None)).is_err());
    assert_eq!(db.snapshot().generation(), 1);
}

#[test]
fn frame_limits_and_unknown_version_are_rejected_before_allocation() {
    let mut bytes = frame::encode(frame::PREPARE, b"{}").unwrap();
    bytes[12..20].copy_from_slice(&(frame::MAX_PAYLOAD + 1).to_le_bytes());
    let crc = crc32fast::hash(&bytes[..20]);
    bytes[20..24].copy_from_slice(&crc.to_le_bytes());
    assert!(matches!(
        frame::read(&mut Cursor::new(bytes)),
        Err(Error::Corrupt(_))
    ));
    let mut bytes = frame::encode(frame::PREPARE, b"{}").unwrap();
    bytes[8] = 2;
    let crc = crc32fast::hash(&bytes[..20]);
    bytes[20..24].copy_from_slice(&crc.to_le_bytes());
    assert!(matches!(
        frame::read(&mut Cursor::new(bytes)),
        Err(Error::Corrupt(_))
    ));
}

#[test]
#[ignore = "subprocess helper, invoked by the process termination test"]
fn child_process() {
    let path = std::env::var("VECTORNEXT_TEST_DIR").unwrap();
    let mode = std::env::var("VECTORNEXT_TEST_MODE").unwrap();
    if mode == "locked" {
        assert!(matches!(Database::open(path), Err(Error::Locked)));
        return;
    }
    let mut db = Database::open(&path).unwrap();
    let document = fixture(&mut db, "match", "r2", 384);
    if mode == "uncommitted" {
        db.fail_at = Some(Fault::PrepareSync);
    }
    let result = db.commit(batch("child-replace", document, Some("r1")));
    if mode == "committed" {
        result.unwrap();
    } else {
        assert!(result.is_err());
    }
    fs::write(Path::new(&path).join("child-ready"), b"ready").unwrap();
    loop {
        std::thread::sleep(Duration::from_millis(100));
    }
}

fn child(path: &Path, mode: &str) -> Command {
    let mut command = Command::new(std::env::current_exe().unwrap());
    command
        .args([
            "--exact",
            "storage::tests::child_process",
            "--ignored",
            "--nocapture",
        ])
        .env("VECTORNEXT_TEST_DIR", path)
        .env("VECTORNEXT_TEST_MODE", mode)
        .stdin(Stdio::null());
    command
}

#[test]
fn process_lock_and_forced_termination_recover_without_destructors() {
    let (dir, db, _) = seed();
    assert!(matches!(Database::open(dir.path()), Err(Error::Locked)));
    assert!(child(dir.path(), "locked").status().unwrap().success());
    drop(db);
    for mode in ["uncommitted", "committed"] {
        let ready = dir.path().join("child-ready");
        if ready.exists() {
            fs::remove_file(&ready).unwrap();
        }
        let mut process = child(dir.path(), mode).spawn().unwrap();
        let start = Instant::now();
        while !ready.exists() && start.elapsed() < Duration::from_secs(10) {
            if let Some(status) = process.try_wait().unwrap() {
                panic!("child exited early: {status}");
            }
            std::thread::sleep(Duration::from_millis(10));
        }
        process.kill().unwrap();
        process.wait().unwrap();
        assert!(ready.exists(), "child timed out");
        let recovered = Database::open(dir.path()).unwrap();
        assert_eq!(
            recovered.snapshot().generation(),
            if mode == "committed" { 2 } else { 1 }
        );
    }
}
