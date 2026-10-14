#![cfg(target_os = "linux")]
use std::{collections::BTreeSet, fs};
use vectornext::{Database, contracts::*, ingestion::pdf::*, ingestion::*, search::*};

fn artifact(name: &str) -> Artifact {
    Artifact::from_slice(&fs::read(format!("tests/fixtures/pdf/{name}.json")).unwrap()).unwrap()
}
fn original(name: &str) -> Vec<u8> {
    let root = if matches!(name, "equipment_guide" | "scanned_note") {
        "evals/fixtures"
    } else {
        "processor/fixtures"
    };
    fs::read(format!("{root}/{name}.pdf")).unwrap()
}
fn setup(
    name: &str,
    allow: bool,
    max_tokens: usize,
) -> (tempfile::TempDir, Database, PdfProcessor<TestEncoder>) {
    let dir = tempfile::tempdir().unwrap();
    let mut db = Database::open(dir.path()).unwrap();
    let p = PdfProcessor {
        local: LocalProcessor {
            encoder: TestEncoder {
                max_tokens,
                document_prefix: "doc: ".into(),
            },
        },
        artifact: artifact(name),
    };
    let mut config = p.artifact.config(p.local.encoder.space(), allow).unwrap();
    config.target_tokens = max_tokens;
    db.submit_ingestion(
        IngestRequest {
            job_id: "pdf".into(),
            document_id: "doc".into(),
            expected_revision: None,
            media_type: MediaType::Pdf,
            config,
        },
        &original(name),
    )
    .unwrap();
    (dir, db, p)
}
fn finish(db: &mut Database, p: &impl Processor) -> IngestJob {
    for _ in 0..6 {
        let job = db.advance_ingestion("pdf", p).unwrap();
        if job.stage == Stage::Committed {
            return job;
        }
    }
    panic!("job did not finish")
}

#[test]
fn native_pdf_preserves_cross_page_passage_table_context_and_search_sources() {
    let (_dir, mut db, p) = setup("equipment_guide", false, 256);
    let job = finish(&mut db, &p);
    let d = &job.draft.document;
    let cross = d
        .chunks
        .iter()
        .find(|c| c.evidence.starts_with("When the Harbor"))
        .unwrap();
    assert!(cross.evidence.contains("wait 8 minutes"));
    assert_eq!(cross.spans.len(), 2);
    let pages: BTreeSet<_> = cross
        .sources
        .iter()
        .map(|s| match s.locator {
            Locator::Pdf { page, .. } => page,
            _ => panic!(),
        })
        .collect();
    assert_eq!(pages, BTreeSet::from([1, 2]));
    assert_eq!(cross.structural_context, "C7 restart procedure");
    assert!(cross.parent.is_some());
    assert!(d.blocks.iter().any(|b| b.text.contains("continued")));
    assert!(!d.chunks.iter().any(|c| c.evidence.contains("continued") || c.evidence.contains("SYNTHETIC TEST DATA")));
    let row = d
        .chunks
        .iter()
        .find(|c| c.evidence == "H2 | 12 | 20")
        .unwrap();
    assert!(row.structural_context.contains("Flow (L/min)"));
    assert_eq!(row.attributes["pdf_table_row"].value["row"], 2);
    assert!(row.attributes["pdf_context"].sources.len() >= 4);
    assert_eq!(
        db.originals().get(&d.original).unwrap(),
        original("equipment_guide")
    );
    let index = SearchIndex::build(
        db.snapshot(),
        p.local.encoder.space().id(),
        KeywordConfig::default(),
    )
    .unwrap();
    let results = index
        .search(&SearchRequest::keyword("C7 wait 8 minutes"))
        .unwrap();
    assert!(!results.results.is_empty());
    assert!(
        results
            .results
            .iter()
            .any(|h| index.resolve(&h.key).unwrap().1.id == cross.id)
    );
}

#[test]
fn scanned_mixed_and_overlay_preserve_extraction_method_without_duplicates() {
    for name in ["scanned_note", "mixed_regions", "mixed_overlay"] {
        let (_dir, mut db, p) = setup(name, false, 256);
        let job = finish(&mut db, &p);
        let d = &job.draft.document;
        assert!(
            d.chunks
                .iter()
                .any(|c| c.representation == Representation::OcrText)
        );
        for c in &d.chunks {
            assert!(
                p.local
                    .encoder
                    .count_tokens(&embedding_input(&p.local.encoder.space(), c))
                    .unwrap()
                    <= 256
            );
            assert!(c.generated_context.is_none());
            assert!(c.sources.iter().all(|s| s.revision == d.revision));
            assert_eq!(
                c.evidence,
                c.spans
                    .iter()
                    .map(|s| {
                        let b = d.blocks.iter().find(|b| b.id == s.block_id).unwrap();
                        &b.text[s.bytes.start as usize..s.bytes.end as usize]
                    })
                    .collect::<Vec<_>>()
                    .join("\n\n")
            );
        }
        if name == "mixed_overlay" {
            assert_eq!(
                d.chunks
                    .iter()
                    .map(|c| c.evidence.matches("valve V5").count())
                    .sum::<usize>(),
                1
            );
        }
    }
}

#[test]
fn strict_partial_failure_is_durable_and_explicit_partial_retains_diagnostics() {
    let (dir, mut db, p) = setup("uninterpreted_graphic", false, 256);
    assert!(
        db.advance_ingestion("pdf", &p)
            .unwrap_err()
            .to_string()
            .contains("partial PDF")
    );
    assert_eq!(db.snapshot().generation(), 0);
    drop(db);
    let db = Database::open(dir.path()).unwrap();
    let failed = db.ingestion_job("pdf").unwrap().unwrap();
    assert_eq!(failed.stage, Stage::Uploaded);
    assert_eq!(failed.failure_count, 1);
    assert!(failed.last_failure.is_some());
    let (_dir, mut allowed, p) = setup("uninterpreted_graphic", true, 256);
    let job = finish(&mut allowed, &p);
    assert_eq!(job.draft.document.processing["pdf"]["status"], "partial");
    assert_eq!(
        job.draft.document.processing["pdf"]["warnings"][0]["code"],
        "uninterpreted_picture"
    );
}

#[test]
fn pdf_job_resumes_each_stage_and_receipts_survive_checkpoint_without_parser() {
    let (dir, mut db, p) = setup("equipment_guide", false, 256);
    for stage in [
        Stage::Parsed,
        Stage::Chunked,
        Stage::Contextualized,
        Stage::Embedded,
        Stage::Committed,
    ] {
        let job = db.advance_ingestion("pdf", &p).unwrap();
        assert_eq!(job.stage, stage);
        drop(db);
        db = Database::open(dir.path()).unwrap();
        assert_eq!(db.ingestion_job("pdf").unwrap().unwrap(), job);
    }
    let saved = db.ingestion_job("pdf").unwrap().unwrap();
    db.checkpoint().unwrap();
    drop(db);
    let mut db = Database::open(dir.path()).unwrap();
    // Already published: no PDF artifact or model invocation is needed to retry.
    let repeat = db.advance_ingestion("pdf", &p.local).unwrap();
    assert_eq!(repeat.receipt, saved.receipt);
    assert_eq!(db.snapshot().generation(), 1);
    assert_eq!(
        db.snapshot().document("doc").unwrap().processing,
        saved.draft.document.processing
    );
}

#[test]
fn changed_artifact_profile_original_and_stale_stage_cannot_publish() {
    let (_dir, mut db, mut p) = setup("equipment_guide", false, 256);
    let original_artifact = p.artifact.clone();
    p.artifact.profile_sha256 = "0".repeat(64);
    assert!(db.advance_ingestion("pdf", &p).is_err());
    p.artifact = original_artifact.clone();
    p.artifact.items[1].text.push_str(" forged");
    assert!(db.advance_ingestion("pdf", &p).is_err());
    p.artifact = original_artifact;
    let mut request = db.ingestion_stage_request("pdf").unwrap();
    request.original.as_mut().unwrap()[0] ^= 1;
    assert!(p.process(&request).is_err());
    let request = db.ingestion_stage_request("pdf").unwrap();
    let result = p.process(&request).unwrap();
    db.accept_ingestion_stage("pdf", result.clone()).unwrap();
    db.accept_ingestion_stage("pdf", result.clone()).unwrap();
    db.advance_ingestion("pdf", &p).unwrap();
    assert!(db.accept_ingestion_stage("pdf", result).is_err());
    assert_eq!(db.snapshot().generation(), 0);
}

#[test]
fn malformed_geometry_utf8_mapping_hierarchy_and_false_quality_fail_closed() {
    for case in 0..7 {
        let (_dir, mut db, p) = setup("equipment_guide", false, 256);
        let mut request = db.ingestion_stage_request("pdf").unwrap();
        let mut p = PdfProcessor {
            local: p.local,
            artifact: p.artifact,
        };
        match case {
            0 => p.artifact.items[1].sources[0].bbox[2] = 900.,
            1 => p.artifact.items[1].sources[0].page = 32,
            2 => p.artifact.items[1].sources[0].bytes.end = 2,
            3 => p.artifact.items[1].parent = Some(p.artifact.items[1].id.clone()),
            4 => p.artifact.items[0].indexed = true,
            5 => p.artifact.warnings.push(Warning {
                code: "missing".into(),
                page: None,
                message: "lost data".into(),
                bbox: None,
            }),
            _ => p.artifact.items[1].sources[0].confidence = Some(2.),
        }
        // Even if the producer explicitly binds the changed artifact, reject invalid structure.
        request.config = p.artifact.config(p.local.encoder.space(), false).unwrap();
        assert!(p.process(&request).is_err(), "case {case}");
        assert_eq!(db.snapshot().generation(), 0);
        // Also exercise accept-stage validation (a producer bypassing PdfProcessor).
        let valid = db.ingestion_stage_request("pdf").unwrap();
        let p = PdfProcessor {
            local: p.local,
            artifact: artifact("equipment_guide"),
        };
        let mut result = p.process(&valid).unwrap();
        result.draft.document.processing.get_mut("pdf").unwrap()["profile_sha256"] =
            "0".repeat(64).into();
        assert!(db.accept_ingestion_stage("pdf", result).is_err());
    }
}

#[test]
fn page_spans_are_clipped_when_a_multibyte_multipage_block_is_split() {
    let (_dir, db, mut p) = setup("equipment_guide", false, 256);
    let mut request = db.ingestion_stage_request("pdf").unwrap();
    let text = "Pelé scored three. ".repeat(5) + &"Then the next page continues. ".repeat(5);
    let midpoint = "Pelé scored three. ".repeat(5).len();
    let mut item = p.artifact.items[1].clone();
    item.kind = BlockKind::Paragraph;
    item.context = String::new();
    item.context_sources.clear();
    item.section = None;
    item.parent = None;
    item.text = text;
    item.sources[0].bytes = ByteRange {
        start: 0,
        end: midpoint as u64,
    };
    let mut second = item.sources[0].clone();
    second.page = 2;
    second.bytes = ByteRange {
        start: midpoint as u64,
        end: item.text.len() as u64,
    };
    item.sources.push(second);
    p.artifact.items = vec![item];
    p.local.encoder.max_tokens = 64;
    request.config = p.artifact.config(p.local.encoder.space(), false).unwrap();
    request.config.target_tokens = 64;
    let parsed = p.process(&request).unwrap();
    request.stage = Stage::Parsed;
    request.draft = parsed.draft;
    request.original = None;
    let chunked = p.process(&request).unwrap();
    for c in &chunked.draft.document.chunks {
        let span = &c.spans[0].bytes;
        let expected = if span.end <= midpoint as u64 {
            vec![1]
        } else if span.start >= midpoint as u64 {
            vec![2]
        } else {
            vec![1, 2]
        };
        assert_eq!(
            c.sources
                .iter()
                .map(|s| match s.locator {
                    Locator::Pdf { page, .. } => page,
                    _ => panic!(),
                })
                .collect::<Vec<_>>(),
            expected
        );
        assert!(
            p.local
                .encoder
                .count_tokens(&embedding_input(&p.local.encoder.space(), c))
                .unwrap()
                <= 64
        );
    }
    assert!(chunked.draft.document.chunks.len() > 3);
}

#[test]
fn pdf_options_do_not_change_legacy_txt_json_request_serialization() {
    let config = IngestConfig::new(TestEncoder::default().space());
    let encoded = serde_json::to_value(&config).unwrap();
    assert!(encoded.get("pdf").is_none());
    assert_eq!(
        serde_json::from_value::<IngestConfig>(encoded).unwrap(),
        config
    );
}
