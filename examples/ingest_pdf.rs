//! Offline PDF artifact → durable jobs → source-resolvable keyword search.
use std::{env, fs};
use vectornext::{Database, Error, Result, contracts::MediaType, ingestion::pdf::*, ingestion::*};

fn run() -> Result<()> {
    let args: Vec<String> = env::args().skip(1).collect();
    if !(5..=6).contains(&args.len()) || (args.len() == 6 && args[5] != "--allow-partial") {
        return Err(Error::Invalid("usage: ingest_pdf <db-directory> <document-id> <pdf-file> <job-id> <artifact.json> [--allow-partial]".into()));
    }
    for path in [&args[2], &args[4]] {
        if fs::metadata(path)?.len() > 16 * 1024 * 1024 {
            return Err(Error::Invalid("input exceeds 16 MiB".into()));
        }
    }
    let artifact = Artifact::from_slice(&fs::read(&args[4])?)?;
    let processor = PdfProcessor {
        local: LocalProcessor {
            encoder: TestEncoder::default(),
        },
        artifact,
    };
    let config = processor
        .artifact
        .config(processor.local.encoder.space(), args.len() == 6)?;
    let mut db = Database::open(&args[0])?;
    let expected_revision = match db.ingestion_job(&args[3])? {
        Some(job) => job.request.expected_revision,
        None => db.snapshot().document(&args[1]).map(|d| d.revision.clone()),
    };
    let mut job = db.submit_ingestion(
        IngestRequest {
            job_id: args[3].clone(),
            document_id: args[1].clone(),
            expected_revision,
            media_type: MediaType::Pdf,
            config,
        },
        &fs::read(&args[2])?,
    )?;
    while job.stage != Stage::Committed {
        job = db.advance_ingestion(&args[3], &processor)?;
    }
    eprintln!("Synthetic test encoder; real model integration remains T07.");
    println!(
        "{}",
        serde_json::to_string_pretty(&serde_json::json!({
            "job_id":job.request.job_id,"stage":job.stage,"receipt":job.receipt,
            "generation":db.snapshot().generation(),"blocks":job.draft.document.blocks.len(),
            "chunks":job.draft.document.chunks.len(),"extraction":job.draft.document.processing["pdf"]
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
