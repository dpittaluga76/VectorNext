#![cfg(target_os = "linux")]
use serde_json::{Value, json};
use std::{collections::BTreeMap, fs};
use vectornext::{Database, Error, Result, contracts::*, ingestion::*, search::*};

fn setup(max_tokens: usize) -> (tempfile::TempDir, Database, LocalProcessor<TestEncoder>) {
    let dir = tempfile::tempdir().unwrap();
    let db = Database::open(dir.path()).unwrap();
    let processor = LocalProcessor {
        encoder: TestEncoder {
            max_tokens,
            document_prefix: "doc: ".into(),
        },
    };
    (dir, db, processor)
}
fn request(
    id: &str,
    media_type: MediaType,
    processor: &LocalProcessor<TestEncoder>,
) -> IngestRequest {
    IngestRequest {
        job_id: id.into(),
        document_id: "document".into(),
        expected_revision: None,
        media_type,
        config: IngestConfig::new(processor.encoder.space()),
    }
}
fn finish(db: &mut Database, id: &str, processor: &impl Processor) -> IngestJob {
    for _ in 0..6 {
        let job = db.advance_ingestion(id, processor).unwrap();
        if job.stage == Stage::Committed {
            return job;
        }
    }
    panic!("job failed to finish")
}

#[test]
fn text_mapping_survives_bom_crlf_unicode_sections_lists_and_forced_splits() {
    let (_dir, mut db, p) = setup(74);
    let text = "\u{feff}# First\r\n\r\nPelé 😀 scored three goals. This sentence has accented café and many more words.\r\nA wrapped line.\r\n\r\n- first item\r\n- second item\r\n\r\n## Child\r\nChild facts.\r\n\r\n# Second\rOther section.";
    let normalized = text
        .trim_start_matches('\u{feff}')
        .replace("\r\n", "\n")
        .replace('\r', "\n");
    db.submit_ingestion(request("txt", MediaType::Txt, &p), text.as_bytes())
        .unwrap();
    let job = finish(&mut db, "txt", &p);
    let doc = job.draft.document;
    assert_eq!(db.originals().get(&doc.original).unwrap(), text.as_bytes());
    assert!(doc.blocks.iter().any(|b| b.kind == BlockKind::List));
    assert!(
        doc.chunks
            .iter()
            .any(|c| c.structural_context == "First > Child" && c.parent.is_some())
    );
    let mut coverage: BTreeMap<String, Vec<(u64, u64)>> = BTreeMap::new();
    for chunk in &doc.chunks {
        assert!(
            p.encoder
                .count_tokens(&embedding_input(&p.encoder.space(), chunk))
                .unwrap()
                <= 74
        );
        assert!(chunk.generated_context.is_none());
        let evidence = chunk
            .spans
            .iter()
            .map(|span| {
                coverage
                    .entry(span.block_id.clone())
                    .or_default()
                    .push((span.bytes.start, span.bytes.end));
                let block = doc.blocks.iter().find(|b| b.id == span.block_id).unwrap();
                block.text[span.bytes.start as usize..span.bytes.end as usize].to_owned()
            })
            .collect::<Vec<_>>()
            .join("\n\n");
        assert_eq!(evidence, chunk.evidence);
        for source in &chunk.sources {
            assert_eq!(source.revision, doc.revision);
            let Locator::Text {
                encoding,
                bytes,
                line_start,
                line_end,
                mappings,
            } = &source.locator
            else {
                panic!()
            };
            assert_eq!(encoding, "UTF-8");
            assert_eq!(bytes.start, mappings.first().unwrap().original.start);
            assert_eq!(bytes.end, mappings.last().unwrap().original.end);
            let lo = mappings.first().unwrap().normalized.start as usize;
            let hi = mappings.last().unwrap().normalized.end as usize;
            assert_eq!(
                *line_start,
                normalized[..lo].bytes().filter(|b| *b == b'\n').count() as u64 + 1
            );
            assert_eq!(
                *line_end,
                normalized[..hi - 1].bytes().filter(|b| *b == b'\n').count() as u64 + 1
            );
            for mapping in mappings {
                let original =
                    &text[mapping.original.start as usize..mapping.original.end as usize];
                assert_eq!(
                    original.replace("\r\n", "\n").replace('\r', "\n"),
                    normalized[mapping.normalized.start as usize..mapping.normalized.end as usize]
                );
            }
        }
    }
    for block in &doc.blocks {
        let spans = coverage.get_mut(&block.id).unwrap();
        spans.sort();
        let mut end = 0;
        for &(lo, hi) in spans.iter() {
            assert_eq!(lo, end);
            end = hi;
        }
        assert_eq!(end, block.text.len() as u64);
    }
}

#[test]
fn adjacent_paragraphs_merge_only_within_sections() {
    let (_dir, mut db, p) = setup(300);
    db.submit_ingestion(
        request("merge", MediaType::Txt, &p),
        b"# A\nFirst.\n\nSecond.\n\n# B\nThird.",
    )
    .unwrap();
    let doc = finish(&mut db, "merge", &p).draft.document;
    let merged = doc
        .chunks
        .iter()
        .find(|c| c.evidence == "First.\n\nSecond.")
        .unwrap();
    assert_eq!(merged.spans.len(), 2);
    assert_eq!(merged.sources.len(), 2);
    assert_eq!(merged.structural_context, "A");
    assert!(
        !doc.chunks
            .iter()
            .any(|c| c.evidence.contains("Second") && c.evidence.contains("Third"))
    );
}

#[test]
fn typed_json_retains_exact_numbers_nested_meaning_and_null_missing() {
    let (_dir, mut db, p) = setup(2048);
    let raw = br#"{"id":"007","publication":{"year":2026},"match":{"year":1954},"goals":0,"assists":null,"active":false,"huge":9007199254740993123456789,"decimal":1.2300000000000000000001,"exponent":1e400,"labels":{"home/away":"away","review~state":"checked"}}"#;
    db.submit_ingestion(request("json", MediaType::Json, &p), raw)
        .unwrap();
    let job = finish(&mut db, "json", &p);
    let chunks = &job.draft.document.chunks;
    assert_eq!(chunks.len(), 1);
    let record = &chunks[0].attributes["record"].value;
    assert_eq!(record, &serde_json::from_slice::<Value>(raw).unwrap());
    assert_eq!(record["huge"].to_string(), "9007199254740993123456789");
    assert_eq!(record["decimal"].to_string(), "1.2300000000000000000001");
    assert_eq!(record["exponent"].to_string(), "1e400");
    assert!(record["assists"].is_null());
    assert!(record.get("missing").is_none());
    let index = SearchIndex::build(
        db.snapshot(),
        p.encoder.space().id(),
        KeywordConfig::default(),
    )
    .unwrap();
    let mut search = SearchRequest::keyword("1954");
    search.filter = Filter::Attribute {
        key: "record".into(),
        pointer: "/match/year".into(),
        predicate: Predicate::Eq(json!(1954)),
        trust: AttributeTrust::default(),
    };
    assert_eq!(index.search(&search).unwrap().results.len(), 1);
    search.filter = Filter::Attribute {
        key: "record".into(),
        pointer: "/publication/year".into(),
        predicate: Predicate::Eq(json!(1954)),
        trust: AttributeTrust::default(),
    };
    assert!(index.search(&search).unwrap().results.is_empty());
}

#[test]
fn narrative_splitting_preserves_record_identity_pointer_and_all_characters() {
    let (_dir, mut db, p) = setup(110);
    let narrative = "The player returned to the field. Café 😀 goals followed. ".repeat(15);
    let value = json!({"publication":{"year":2026},"matches":[{"id":"m1","notes":narrative,"stats":{"goals":0,"assists":null},"labels":{"home/away":"away ".repeat(30),"review~state":"checked"}}]});
    let mut req = request("narrative", MediaType::Json, &p);
    req.config.record_pointer = "/matches".into();
    db.submit_ingestion(req, &serde_json::to_vec(&value).unwrap())
        .unwrap();
    let doc = finish(&mut db, "narrative", &p).draft.document;
    let notes: Vec<_> = doc.chunks.iter().filter(|c| matches!(&c.sources[0].locator,Locator::Json {pointer,..} if pointer == "/matches/0/notes")).collect();
    assert!(notes.len() > 5);
    assert_eq!(
        notes
            .iter()
            .map(|c| c.evidence.as_str())
            .collect::<String>(),
        narrative
    );
    for chunk in &notes {
        assert_eq!(chunk.attributes["record"].value, value["matches"][0]);
        assert_eq!(chunk.attributes["value"].value, narrative);
        assert!(
            matches!(&chunk.sources[0].locator,Locator::Json {record_id:Some(Value::String(id)),..} if id == "m1")
        );
        assert!(chunk.previous.is_some() || chunk.next.is_some());
    }
    assert!(
        doc.chunks
            .iter()
            .any(|c| c.structural_context.contains("/publication")
                && !c.attributes.contains_key("record"))
    );
    assert!(doc.blocks.iter().any(|b| matches!(&b.sources[0].locator,Locator::Json {pointer,..} if pointer == "/matches/0/labels/home~1away")));
    for c in &doc.chunks {
        assert!(
            p.encoder
                .count_tokens(&embedding_input(&p.encoder.space(), c))
                .unwrap()
                <= 110
        );
    }
}

#[test]
fn pointers_are_revision_scoped_and_ids_follow_array_reordering() {
    let (_dir, mut db, p) = setup(256);
    let before = br#"[{"id":"a","goals":3},{"id":"b","goals":1}]"#;
    db.submit_ingestion(request("v1", MediaType::Json, &p), before)
        .unwrap();
    let first = finish(&mut db, "v1", &p);
    let mut req = request("v2", MediaType::Json, &p);
    req.expected_revision = Some(first.input_sha256.clone());
    db.submit_ingestion(req, br#"[{"id":"b","goals":1},{"id":"a","goals":3}]"#)
        .unwrap();
    let second = finish(&mut db, "v2", &p);
    let locate = |job: &IngestJob| {
        job.draft
            .document
            .chunks
            .iter()
            .find(|c| c.attributes["record"].value["id"] == "a")
            .unwrap()
            .sources[0]
            .clone()
    };
    let a = locate(&first);
    let b = locate(&second);
    assert_ne!(a.revision, b.revision);
    assert!(
        matches!(a.locator,Locator::Json{pointer,record_id:Some(id)} if pointer=="/0" && id=="a")
    );
    assert!(
        matches!(b.locator,Locator::Json{pointer,record_id:Some(id)} if pointer=="/1" && id=="a")
    );
    assert_eq!(db.snapshot().documents().count(), 1);
}

#[test]
fn every_stage_restarts_and_staged_replacement_stays_hidden() {
    let (dir, mut db, p) = setup(256);
    let req = request("old", MediaType::Txt, &p);
    db.submit_ingestion(req.clone(), b"old searchable evidence")
        .unwrap();
    let old = finish(&mut db, "old", &p);
    let old_index = SearchIndex::build(
        db.snapshot(),
        p.encoder.space().id(),
        KeywordConfig::default(),
    )
    .unwrap();
    let mut replacement = request("new", MediaType::Txt, &p);
    replacement.expected_revision = Some(old.input_sha256.clone());
    let mut job = db
        .submit_ingestion(replacement.clone(), b"new replacement evidence")
        .unwrap();
    for stage in [
        Stage::Uploaded,
        Stage::Parsed,
        Stage::Chunked,
        Stage::Contextualized,
        Stage::Embedded,
    ] {
        assert_eq!(job.stage, stage);
        assert_eq!(db.snapshot().generation(), 1);
        assert_eq!(
            db.snapshot().document("document").unwrap().revision,
            old.input_sha256
        );
        drop(db);
        db = Database::open(dir.path()).unwrap();
        assert_eq!(
            db.submit_ingestion(replacement.clone(), b"new replacement evidence")
                .unwrap(),
            job
        );
        job = db.advance_ingestion("new", &p).unwrap();
    }
    assert_eq!(job.stage, Stage::Committed);
    assert_eq!(db.snapshot().generation(), 2);
    drop(db);
    db = Database::open(dir.path()).unwrap();
    assert_eq!(db.advance_ingestion("new", &p).unwrap(), job);
    assert_eq!(db.snapshot().generation(), 2);
    assert_eq!(
        old_index
            .search(&SearchRequest::keyword("old"))
            .unwrap()
            .results
            .len(),
        1
    );
    let fresh = SearchIndex::build(
        db.snapshot(),
        p.encoder.space().id(),
        KeywordConfig::default(),
    )
    .unwrap();
    assert!(
        fresh
            .search(&SearchRequest::keyword("old"))
            .unwrap()
            .results
            .is_empty()
    );
    assert_eq!(
        fresh
            .search(&SearchRequest::keyword("replacement"))
            .unwrap()
            .results
            .len(),
        1
    );
}

struct Never;
impl Processor for Never {
    fn process(&self, _: &StageRequest) -> Result<StageResult> {
        panic!("unexpected processor call")
    }
}
#[test]
fn publication_before_marker_retries_receipt_after_delete_without_resurrection() {
    let (dir, mut db, p) = setup(256);
    db.submit_ingestion(request("publish", MediaType::Txt, &p), b"visible once")
        .unwrap();
    let mut job = db.ingestion_job("publish").unwrap().unwrap();
    while job.stage != Stage::Embedded {
        job = db.advance_ingestion("publish", &p).unwrap();
    }
    let receipt = db.commit(job.publication_batch().unwrap()).unwrap();
    db.commit(Batch {
        operation_id: "delete-later".into(),
        spaces: vec![],
        mutations: vec![Mutation::Delete {
            document_id: "document".into(),
            expected_revision: job.input_sha256,
        }],
    })
    .unwrap();
    db.checkpoint().unwrap();
    drop(db);
    db = Database::open(dir.path()).unwrap();
    let done = db.advance_ingestion("publish", &Never).unwrap();
    assert_eq!(done.receipt, Some(receipt));
    assert_eq!(db.snapshot().generation(), 2);
    assert_eq!(db.snapshot().documents().count(), 0);
}

#[test]
fn request_binding_rejects_reused_ids_changed_context_and_space() {
    let (_dir, mut db, p) = setup(256);
    let req = request("../safe/id", MediaType::Txt, &p);
    db.submit_ingestion(req.clone(), b"first").unwrap();
    assert!(matches!(
        db.submit_ingestion(req.clone(), b"different"),
        Err(Error::RetryConflict)
    ));
    let mut changed = req.clone();
    changed.config.target_tokens -= 1;
    assert!(matches!(
        db.submit_ingestion(changed, b"first"),
        Err(Error::RetryConflict)
    ));
    let mut changed = req;
    changed.config.space.document_prefix = "other".into();
    assert!(matches!(
        db.submit_ingestion(changed, b"first"),
        Err(Error::RetryConflict)
    ));
    assert_eq!(db.ingestion_jobs().unwrap().len(), 1);
    assert_eq!(db.snapshot().generation(), 0);
}

#[test]
fn stage_results_are_bound_to_inputs_and_duplicate_acknowledgments_are_safe() {
    let (_dir, mut db, p) = setup(256);
    db.submit_ingestion(request("stage", MediaType::Txt, &p), b"traceable original")
        .unwrap();
    let input = db.ingestion_stage_request("stage").unwrap();
    // Exercise the serializable processor boundary.
    let input = serde_json::from_slice(&serde_json::to_vec(&input).unwrap()).unwrap();
    let result = p.process(&input).unwrap();
    let accepted = db.accept_ingestion_stage("stage", result.clone()).unwrap();
    assert_eq!(
        db.accept_ingestion_stage("stage", result.clone()).unwrap(),
        accepted
    );
    let mut stale = result.clone();
    stale.draft.document.blocks[0].text = "changed".into();
    assert!(db.accept_ingestion_stage("stage", stale).is_err());
    db.advance_ingestion("stage", &p).unwrap();
    assert!(db.accept_ingestion_stage("stage", result).is_err());
    db.advance_ingestion("stage", &p).unwrap();
    let mut embedding = p
        .process(&db.ingestion_stage_request("stage").unwrap())
        .unwrap();
    embedding.draft.document.chunks[0].evidence = "invented".into();
    assert!(db.accept_ingestion_stage("stage", embedding).is_err());
    assert_eq!(db.snapshot().generation(), 0);
}

struct Fails;
impl Processor for Fails {
    fn process(&self, _: &StageRequest) -> Result<StageResult> {
        Err(Error::Invalid("temporary processor outage".into()))
    }
}
#[test]
fn failures_survive_restart_and_resume_last_successful_stage() {
    let (dir, mut db, p) = setup(256);
    db.submit_ingestion(request("failure", MediaType::Txt, &p), b"persist the draft")
        .unwrap();
    db.advance_ingestion("failure", &p).unwrap();
    assert!(db.advance_ingestion("failure", &Fails).is_err());
    drop(db);
    db = Database::open(dir.path()).unwrap();
    let failed = db.ingestion_job("failure").unwrap().unwrap();
    assert_eq!(failed.stage, Stage::Parsed);
    assert_eq!(failed.failure_count, 1);
    assert_eq!(failed.last_failure.unwrap().stage, Stage::Parsed);
    let done = finish(&mut db, "failure", &p);
    assert_eq!(done.failure_count, 1);
    assert!(done.last_failure.is_none());
    assert_eq!(done.successful_stages, 4);
}

#[test]
fn invalid_documents_fail_visibly_without_publishing() {
    for (media, bytes) in [
        (MediaType::Txt, b"\xff bad UTF-8".as_slice()),
        (MediaType::Txt, b" \r\n\t"),
        (MediaType::Json, br#"{"a":1,"a":2}"#),
        (MediaType::Json, br#"{"a":{"x":1,"x":2}}"#),
        (MediaType::Json, br#"[{"id":"same"},{"id":"same"}]"#),
        (MediaType::Json, br#"[{"id":false}]"#),
        (MediaType::Json, b"{broken"),
        (MediaType::Json, br#"{"$serde_json::private::Number":"12"}"#),
        (
            MediaType::Json,
            br#"{"\u0024serde_json::private::Number":"12"}"#,
        ),
    ] {
        let (_dir, mut db, p) = setup(256);
        db.submit_ingestion(request("invalid", media, &p), bytes)
            .unwrap();
        assert!(db.advance_ingestion("invalid", &p).is_err());
        let job = db.ingestion_job("invalid").unwrap().unwrap();
        assert_eq!(job.stage, Stage::Uploaded);
        assert!(job.last_failure.is_some());
        assert_eq!(
            db.originals().get(&job.draft.document.original).unwrap(),
            bytes
        );
        assert_eq!(db.snapshot().generation(), 0);
    }
}

#[test]
fn token_budget_counts_prefix_context_specials_and_rejects_impossible_inputs() {
    let (_dir, mut db, p) = setup(20);
    db.submit_ingestion(
        request("budget", MediaType::Txt, &p),
        b"# A heading too long for context\nSome facts.",
    )
    .unwrap();
    db.advance_ingestion("budget", &p).unwrap();
    assert!(db.advance_ingestion("budget", &p).is_err());
    assert_eq!(
        db.ingestion_job("budget").unwrap().unwrap().stage,
        Stage::Parsed
    );
    assert_eq!(db.snapshot().generation(), 0);
    let (_dir, mut db, p) = setup(64);
    let huge_number = "9".repeat(100);
    db.submit_ingestion(
        request("number", MediaType::Json, &p),
        huge_number.as_bytes(),
    )
    .unwrap();
    db.advance_ingestion("number", &p).unwrap();
    assert!(db.advance_ingestion("number", &p).is_err());
    assert_eq!(db.snapshot().generation(), 0);
}

#[test]
fn escaped_record_paths_empty_containers_scalars_and_missing_ids_are_supported() {
    for raw in [
        "[]",
        "{}",
        "null",
        "0",
        "false",
        "\"\"",
        "\"string\"",
        "[{}, {\"id\":null}]",
    ] {
        let (_dir, mut db, p) = setup(256);
        db.submit_ingestion(request("small", MediaType::Json, &p), raw.as_bytes())
            .unwrap();
        assert!(
            !finish(&mut db, "small", &p)
                .draft
                .document
                .chunks
                .is_empty()
        );
    }
    let (_dir, mut db, p) = setup(256);
    let mut req = request("pointer", MediaType::Json, &p);
    req.config.record_pointer = "/a~1b/~0records".into();
    db.submit_ingestion(
        req,
        br#"{"a/b":{"~records":[{"id":7,"goals":3}],"metadata":true},"other":0}"#,
    )
    .unwrap();
    let doc = finish(&mut db, "pointer", &p).draft.document;
    assert!(doc.chunks.iter().any(|c| matches!(&c.sources[0].locator,Locator::Json{pointer,..} if pointer=="/a~1b/~0records/0")));
    assert!(doc.chunks.iter().any(
        |c| matches!(&c.sources[0].locator,Locator::Json{pointer,..} if pointer=="/a~1b/metadata")
    ));
}

#[test]
fn conflicting_jobs_leave_the_first_publication_intact() {
    let (_dir, mut db, p) = setup(256);
    db.submit_ingestion(request("one", MediaType::Txt, &p), b"first revision")
        .unwrap();
    db.submit_ingestion(request("two", MediaType::Txt, &p), b"second revision")
        .unwrap();
    let first = finish(&mut db, "one", &p);
    for _ in 0..4 {
        db.advance_ingestion("two", &p).unwrap();
    }
    assert!(matches!(
        db.advance_ingestion("two", &p),
        Err(Error::Conflict(_))
    ));
    assert_eq!(
        db.snapshot().document("document").unwrap().revision,
        first.input_sha256
    );
    assert_eq!(db.snapshot().generation(), 1);
    assert_eq!(
        db.ingestion_job("two")
            .unwrap()
            .unwrap()
            .last_failure
            .unwrap()
            .stage,
        Stage::Embedded
    );
}

#[test]
fn incomplete_pending_files_are_ignored_but_corrupt_saved_jobs_fail_closed() {
    let (dir, mut db, p) = setup(256);
    db.submit_ingestion(request("corrupt", MediaType::Txt, &p), b"original")
        .unwrap();
    fs::write(dir.path().join("jobs/stage.pending"), b"incomplete stage").unwrap();
    drop(db);
    db = Database::open(dir.path()).unwrap();
    assert_eq!(db.ingestion_jobs().unwrap().len(), 1);
    let path = fs::read_dir(dir.path().join("jobs"))
        .unwrap()
        .map(|e| e.unwrap().path())
        .find(|p| p.extension().is_some_and(|e| e == "job"))
        .unwrap();
    let original = fs::read(&path).unwrap();
    drop(db);
    for length in [0, 1, 23, 24, original.len() / 2, original.len() - 1] {
        fs::write(&path, &original[..length]).unwrap();
        assert!(Database::open(dir.path()).is_err());
    }
    let mut changed = original.clone();
    changed[40] ^= 1;
    fs::write(&path, changed).unwrap();
    assert!(Database::open(dir.path()).is_err());
    fs::write(&path, &original).unwrap();
    assert!(Database::open(dir.path()).is_ok());
}

#[test]
fn actual_job_write_error_poisons_writer_and_recovers_prior_stage() {
    let (dir, mut db, p) = setup(256);
    db.submit_ingestion(request("io", MediaType::Txt, &p), b"original")
        .unwrap();
    fs::create_dir(dir.path().join("jobs/stage.pending")).unwrap();
    assert!(db.advance_ingestion("io", &p).is_err());
    assert!(matches!(db.put_original(b"later"), Err(Error::Poisoned)));
    assert_eq!(db.snapshot().generation(), 0);
    drop(db);
    fs::remove_dir(dir.path().join("jobs/stage.pending")).unwrap();
    db = Database::open(dir.path()).unwrap();
    assert_eq!(
        db.ingestion_job("io").unwrap().unwrap().stage,
        Stage::Uploaded
    );
    finish(&mut db, "io", &p);
}

#[test]
fn actual_txt_json_fixtures_ingest_recover_and_search_offline() {
    let (dir, mut db, p) = setup(256);
    for (id, media, bytes, pointer) in [
        (
            "txt",
            MediaType::Txt,
            include_bytes!("../evals/fixtures/fictional_matches.txt").as_slice(),
            "",
        ),
        (
            "nested",
            MediaType::Json,
            include_bytes!("../evals/fixtures/nested_matches.json").as_slice(),
            "/matches",
        ),
        (
            "array",
            MediaType::Json,
            include_bytes!("../evals/fixtures/array_matches.json").as_slice(),
            "",
        ),
    ] {
        let mut req = request(id, media, &p);
        req.document_id = id.into();
        req.config.record_pointer = pointer.into();
        db.submit_ingestion(req, bytes).unwrap();
        finish(&mut db, id, &p);
    }
    db.checkpoint().unwrap();
    drop(db);
    db = Database::open(dir.path()).unwrap();
    assert_eq!(db.snapshot().documents().count(), 3);
    assert_eq!(db.snapshot().generation(), 3);
    assert!(
        db.ingestion_jobs()
            .unwrap()
            .iter()
            .all(|j| j.stage == Stage::Committed)
    );
    let index = SearchIndex::build(
        db.snapshot(),
        p.encoder.space().id(),
        KeywordConfig::default(),
    )
    .unwrap();
    for query in ["Pelé Argentina", "Iris Vega", "Sol Marin"] {
        assert!(
            !index
                .search(&SearchRequest::keyword(query))
                .unwrap()
                .results
                .is_empty()
        );
    }
}

#[test]
#[ignore = "subprocess helper, invoked by ingestion process termination test"]
fn ingestion_child() {
    let path = std::env::var("VECTORNEXT_INGEST_TEST_DIR").unwrap();
    let mode = std::env::var("VECTORNEXT_INGEST_TEST_MODE").unwrap();
    let p = LocalProcessor {
        encoder: TestEncoder::default(),
    };
    let mut db = Database::open(&path).unwrap();
    db.submit_ingestion(
        request("kill", MediaType::Txt, &p),
        b"survive process termination",
    )
    .unwrap();
    let mut job = db.advance_ingestion("kill", &p).unwrap();
    if mode == "published" {
        while job.stage != Stage::Embedded {
            job = db.advance_ingestion("kill", &p).unwrap();
        }
        db.commit(job.publication_batch().unwrap()).unwrap();
    }
    fs::write(std::path::Path::new(&path).join("ready"), b"ready").unwrap();
    loop {
        std::thread::sleep(std::time::Duration::from_millis(100));
    }
}

#[test]
fn killed_worker_recovers_parsed_draft_or_publication_without_rerunning_models() {
    use std::{
        process::{Command, Stdio},
        time::{Duration, Instant},
    };
    for mode in ["parsed", "published"] {
        let dir = tempfile::tempdir().unwrap();
        let mut child = Command::new(std::env::current_exe().unwrap())
            .args(["--exact", "ingestion_child", "--ignored", "--nocapture"])
            .env("VECTORNEXT_INGEST_TEST_DIR", dir.path())
            .env("VECTORNEXT_INGEST_TEST_MODE", mode)
            .stdin(Stdio::null())
            .spawn()
            .unwrap();
        let start = Instant::now();
        while !dir.path().join("ready").exists() && start.elapsed() < Duration::from_secs(10) {
            if let Some(status) = child.try_wait().unwrap() {
                panic!("ingestion child exited early: {status}");
            }
            std::thread::sleep(Duration::from_millis(10));
        }
        child.kill().unwrap();
        child.wait().unwrap();
        assert!(dir.path().join("ready").exists(), "child timed out");
        let mut db = Database::open(dir.path()).unwrap();
        if mode == "published" {
            assert_eq!(db.snapshot().generation(), 1);
            assert_eq!(
                db.advance_ingestion("kill", &Never).unwrap().stage,
                Stage::Committed
            );
        } else {
            assert_eq!(db.snapshot().generation(), 0);
            assert_eq!(
                db.ingestion_job("kill").unwrap().unwrap().stage,
                Stage::Parsed
            );
            finish(
                &mut db,
                "kill",
                &LocalProcessor {
                    encoder: TestEncoder::default(),
                },
            );
        }
        assert_eq!(db.snapshot().generation(), 1);
        assert_eq!(db.snapshot().documents().count(), 1);
    }
}

#[test]
fn oversized_derived_records_fail_before_unbounded_chunk_expansion() {
    let (_dir, mut db, p) = setup(128);
    let bytes = serde_json::to_vec(&json!({"id":"large","notes":"text ".repeat(80_000)})).unwrap();
    db.submit_ingestion(request("bounded", MediaType::Json, &p), &bytes)
        .unwrap();
    db.advance_ingestion("bounded", &p).unwrap();
    let error = db.advance_ingestion("bounded", &p).unwrap_err();
    assert!(error.to_string().contains("size limit"));
    let job = db.ingestion_job("bounded").unwrap().unwrap();
    assert_eq!(job.stage, Stage::Parsed);
    assert!(job.draft.document.chunks.is_empty());
    assert_eq!(db.snapshot().generation(), 0);
}
