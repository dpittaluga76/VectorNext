#![cfg(target_os = "linux")]
use sha2::{Digest, Sha256};
use std::cell::Cell;
use vectornext::{
    Database, Error, Result,
    contracts::*,
    ingestion::{context::*, *},
};

fn generation() -> GenerationConfig {
    GenerationConfig {
        model: "test-generator".into(),
        revision: "v1".into(),
        artifact_sha256: "1".repeat(64),
        runtime: "test-v1".into(),
        prompt: "test prompt".into(),
        prompt_version: format!("{:x}", Sha256::digest(b"test prompt")),
        temperature: 0,
        seed: 42,
        context_window: 4096,
        output_tokens: 256,
        annotation_tokens: 60,
    }
}
struct Gen {
    fail: Cell<bool>,
    text: Option<String>,
}
impl Generator for Gen {
    fn generate(&self, _: &ContextInput) -> Result<Option<String>> {
        if self.fail.replace(false) {
            Err(Error::Invalid("injected generator outage".into()))
        } else {
            Ok(self.text.clone())
        }
    }
}
fn config(policy: Policy) -> IngestConfig {
    let mut c = IngestConfig::new(TestEncoder::default().space());
    c.target_tokens = 170;
    c.context = Some(ContextConfig::new(
        policy.clone(),
        (policy == Policy::Generated).then(generation),
    ));
    c
}
fn submit(db: &mut Database, id: &str, policy: Policy, media_type: MediaType, bytes: &[u8]) {
    db.submit_ingestion(
        IngestRequest {
            job_id: id.into(),
            document_id: id.into(),
            expected_revision: None,
            media_type,
            config: config(policy),
        },
        bytes,
    )
    .unwrap();
}
fn processor(text: Option<&str>) -> ContextProcessor<LocalProcessor<TestEncoder>, Gen> {
    ContextProcessor {
        base: LocalProcessor {
            encoder: TestEncoder::default(),
        },
        generator: Gen {
            fail: Cell::new(false),
            text: text.map(str::to_owned),
        },
    }
}
fn finish(db: &mut Database, id: &str, p: &impl Processor) -> IngestJob {
    for _ in 0..5 {
        let j = db.advance_ingestion(id, p).unwrap();
        if j.stage == Stage::Committed {
            return j;
        }
    }
    panic!("did not commit")
}
#[test]
fn policies_keep_evidence_and_embed_the_selected_representation() {
    for policy in [Policy::Plain, Policy::Structural, Policy::Generated] {
        let dir = tempfile::tempdir().unwrap();
        let mut db = Database::open(dir.path()).unwrap();
        let p = processor(Some("A section about the cup."));
        submit(
            &mut db,
            "p",
            policy.clone(),
            MediaType::Txt,
            b"# Cup\n\nHe scored three goals.",
        );
        let j = finish(&mut db, "p", &p);
        let c = j
            .draft
            .document
            .chunks
            .iter()
            .find(|c| c.evidence.contains("scored"))
            .unwrap();
        assert_eq!(c.evidence, "He scored three goals.");
        assert!(!c.structural_context.is_empty());
        let input = configured_input(&j.request.config, c);
        assert_eq!(input.contains("Cup"), policy != Policy::Plain);
        assert_eq!(c.generated_context.is_some(), policy == Policy::Generated);
        assert_eq!(
            c.vectors[&j.request.config.space.id()],
            p.base.encoder.embed(&input).unwrap()
        );
        drop(db);
        let db = Database::open(dir.path()).unwrap();
        assert_eq!(db.snapshot().generation(), 1);
    }
}
#[test]
fn generator_failure_restart_and_committed_retry_preserve_atomicity() {
    let dir = tempfile::tempdir().unwrap();
    let mut db = Database::open(dir.path()).unwrap();
    let p = processor(Some("The cup record."));
    submit(
        &mut db,
        "p",
        Policy::Generated,
        MediaType::Txt,
        b"# Cup\n\nHe scored three goals.",
    );
    db.advance_ingestion("p", &p).unwrap();
    db.advance_ingestion("p", &p).unwrap();
    p.generator.fail.set(true);
    assert!(db.advance_ingestion("p", &p).is_err());
    assert_eq!(db.snapshot().generation(), 0);
    drop(db);
    let mut db = Database::open(dir.path()).unwrap();
    let failed = db.ingestion_job("p").unwrap().unwrap();
    assert_eq!(failed.stage, Stage::Chunked);
    assert_eq!(failed.failure_count, 1);
    let done = finish(&mut db, "p", &p);
    p.generator.fail.set(true);
    assert_eq!(db.advance_ingestion("p", &p).unwrap(), done);
    assert_eq!(db.snapshot().generation(), 1);
}
#[test]
fn contextualization_cannot_change_evidence_or_forge_scope_model_or_input() {
    let dir = tempfile::tempdir().unwrap();
    let mut db = Database::open(dir.path()).unwrap();
    let p = processor(Some("The cup record."));
    submit(
        &mut db,
        "p",
        Policy::Generated,
        MediaType::Txt,
        b"# Cup\n\nHe scored three goals.",
    );
    db.advance_ingestion("p", &p).unwrap();
    db.advance_ingestion("p", &p).unwrap();
    let good = p
        .process(&db.ingestion_stage_request("p").unwrap())
        .unwrap();
    for mode in 0..5 {
        let mut bad = good.clone();
        let chunk = bad
            .draft
            .document
            .chunks
            .iter_mut()
            .find(|c| c.generated_context.is_some())
            .unwrap();
        match mode {
            0 => chunk.evidence.push('!'),
            1 => chunk.generated_context.as_mut().unwrap().model = "forged".into(),
            2 => chunk
                .generated_context
                .as_mut()
                .unwrap()
                .source_scope
                .clear(),
            3 => {
                bad.draft.document.processing.remove("context");
            }
            _ => {
                let report = bad
                    .draft
                    .document
                    .processing
                    .get_mut("context")
                    .unwrap()
                    .as_object_mut()
                    .unwrap();
                let key = report.keys().next().unwrap().clone();
                report[&key]["input_sha256"] = "forged".into();
            }
        }
        assert!(db.accept_ingestion_stage("p", bad).is_err());
        assert_eq!(
            db.ingestion_job("p").unwrap().unwrap().stage,
            Stage::Chunked
        );
    }
    db.accept_ingestion_stage("p", good).unwrap();
    finish(&mut db, "p", &p);
}
#[test]
fn explicit_json_needs_no_generation_and_retains_exact_values() {
    let dir = tempfile::tempdir().unwrap();
    let mut db = Database::open(dir.path()).unwrap();
    let p = processor(Some("must not run"));
    p.generator.fail.set(true);
    submit(
        &mut db,
        "p",
        Policy::Generated,
        MediaType::Json,
        br#"{"goals":0,"year":1954,"unknown":null}"#,
    );
    let j = finish(&mut db, "p", &p);
    assert!(p.generator.fail.get());
    assert!(
        j.draft
            .document
            .chunks
            .iter()
            .all(|c| c.generated_context.is_none())
    );
    assert_eq!(
        j.draft.document.processing["context"],
        serde_json::json!({})
    );
}
#[test]
fn oversized_annotation_never_publishes_and_resumes_at_embedding() {
    let dir = tempfile::tempdir().unwrap();
    let mut db = Database::open(dir.path()).unwrap();
    let p = processor(Some(&"oversize ".repeat(80)));
    submit(
        &mut db,
        "p",
        Policy::Generated,
        MediaType::Txt,
        b"Some evidence.",
    );
    for _ in 0..3 {
        db.advance_ingestion("p", &p).unwrap();
    }
    assert!(db.advance_ingestion("p", &p).is_err());
    assert_eq!(db.snapshot().generation(), 0);
    drop(db);
    let db = Database::open(dir.path()).unwrap();
    assert_eq!(
        db.ingestion_job("p").unwrap().unwrap().stage,
        Stage::Contextualized
    );
}
#[test]
fn input_digest_changes_with_heading_scope_prompt_model_and_embedding_space() {
    let dir = tempfile::tempdir().unwrap();
    let mut db = Database::open(dir.path()).unwrap();
    let p = processor(None);
    submit(
        &mut db,
        "p",
        Policy::Generated,
        MediaType::Txt,
        b"# Cup\n\nHe scored three goals.",
    );
    db.advance_ingestion("p", &p).unwrap();
    let j = db.advance_ingestion("p", &p).unwrap();
    let c = j
        .draft
        .document
        .chunks
        .iter()
        .find(|c| c.evidence.contains("scored"))
        .unwrap();
    let input = input_for(&j.draft, &j.request.config, c).unwrap().unwrap();
    let id = input.id().unwrap();
    for mode in 0..5 {
        let mut changed = input.clone();
        match mode {
            0 => changed.structural_context.push('!'),
            1 => changed.scope[0].text.push('!'),
            2 => changed.config.generator.as_mut().unwrap().prompt.push('!'),
            3 => changed
                .config
                .generator
                .as_mut()
                .unwrap()
                .revision
                .push('!'),
            _ => changed.space.preprocessing.push('!'),
        };
        assert_ne!(changed.id().unwrap(), id);
    }
    finish(&mut db, "p", &p);
}
#[test]
fn scope_is_bounded_and_contains_exact_spans_for_long_documents() {
    let dir = tempfile::tempdir().unwrap();
    let mut db = Database::open(dir.path()).unwrap();
    let p = processor(None);
    let source = format!(
        "# A long section\n\n{}",
        "This is a sentence about a team. ".repeat(260)
    );
    submit(
        &mut db,
        "p",
        Policy::Generated,
        MediaType::Txt,
        source.as_bytes(),
    );
    db.advance_ingestion("p", &p).unwrap();
    let j = db.advance_ingestion("p", &p).unwrap();
    for c in &j.draft.document.chunks {
        if let Some(input) = input_for(&j.draft, &j.request.config, c).unwrap() {
            assert!(input.scope.iter().map(|s| s.text.len()).sum::<usize>() <= 8000);
            for span in &c.spans {
                assert!(input.scope.iter().any(|s| s.span == *span));
            }
        }
    }
    let source = format!(
        "# Remote parent heading\n\n{}",
        (0..120)
            .map(|i| format!(
                "Paragraph {i}: {}",
                "This is background text about the team. ".repeat(4)
            ))
            .collect::<Vec<_>>()
            .join("\n\n")
    );
    submit(
        &mut db,
        "distant",
        Policy::Generated,
        MediaType::Txt,
        source.as_bytes(),
    );
    db.advance_ingestion("distant", &p).unwrap();
    let j = db.advance_ingestion("distant", &p).unwrap();
    let chunk = j.draft.document.chunks.last().unwrap();
    let input = input_for(&j.draft, &j.request.config, chunk)
        .unwrap()
        .unwrap();
    assert!(input.scope.iter().any(|s| s.span.block_id == "b0"));
    assert!(input.scope.iter().map(|s| s.text.len()).sum::<usize>() <= 8000);
}
