//! Offline TXT/JSON ingestion inspector. Explicit synthetic encoder, no answers/LLM.
use std::{env, fs, path::Path};
use vectornext::{Database, Error, Result, contracts::MediaType, ingestion::*};

fn run() -> Result<()> {
    let args: Vec<String> = env::args().skip(1).collect();
    if !(4..=5).contains(&args.len()) {
        return Err(Error::Invalid("usage: ingest <database-directory> <document-id> <TXT-or-JSON-file> <job-id> [record-pointer]".into()));
    }
    let media_type = match Path::new(&args[2])
        .extension()
        .and_then(|s| s.to_str())
        .map(str::to_ascii_lowercase)
        .as_deref()
    {
        Some("txt") => MediaType::Txt,
        Some("json") => MediaType::Json,
        _ => {
            return Err(Error::Invalid(
                "input extension must be .txt or .json".into(),
            ));
        }
    };
    let mut db = Database::open(&args[0])?;
    let processor = LocalProcessor {
        encoder: TestEncoder::default(),
    };
    let mut config = IngestConfig::new(processor.encoder.space());
    config.record_pointer = args.get(4).cloned().unwrap_or_default();
    let expected_revision = match db.ingestion_job(&args[3])? {
        Some(job) => job.request.expected_revision,
        None => db.snapshot().document(&args[1]).map(|d| d.revision.clone()),
    };
    let mut job = db.submit_ingestion(
        IngestRequest {
            job_id: args[3].clone(),
            document_id: args[1].clone(),
            expected_revision,
            media_type,
            config,
        },
        &fs::read(&args[2])?,
    )?;
    eprintln!("Synthetic test encoder; vectors do not measure semantic relevance.");
    loop {
        eprintln!("Job {}: {:?}", job.request.job_id, job.stage);
        if job.stage == Stage::Committed {
            break;
        }
        job = db.advance_ingestion(&args[3], &processor)?;
    }
    println!(
        "{}",
        serde_json::to_string_pretty(&serde_json::json!({
            "job_id":job.request.job_id,"stage":job.stage,"revision":job.input_sha256,
            "receipt":job.receipt,"database_generation":db.snapshot().generation(),
            "blocks":job.draft.document.blocks.len(),"chunks":job.draft.document.chunks.len(),
            "original":job.draft.document.original,"space_id":processor.encoder.space().id(),
            "encoder":"synthetic; semantic model integration is T07"
        }))?
    );
    Ok(())
}
fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(1);
    }
}
