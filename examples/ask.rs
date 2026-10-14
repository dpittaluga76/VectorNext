//! Local T08 CLI; the integrated service is T09.
use std::{env, fs};
use vectornext::{
    Database, Error, Result,
    answers::{AskRequest, ask},
    ingestion::{Encoder, worker::ModelWorker},
    search::{KeywordConfig, SearchIndex},
};
fn run() -> Result<()> {
    let args: Vec<_> = env::args().skip(1).collect();
    if args.len() != 2 {
        return Err(Error::Invalid(
            "usage: ask <database> <request.json>".into(),
        ));
    }
    let bytes = fs::read(&args[1])?;
    if bytes.len() > 64 * 1024 {
        return Err(Error::Invalid("request exceeds 64 KiB".into()));
    }
    let request: AskRequest = serde_json::from_slice(&bytes)?;
    let snapshot = {
        let db = Database::open(&args[0])?;
        db.snapshot()
    };
    // Release the writer lock before any model work; the committed snapshot owns its data.
    let worker =
        ModelWorker::start(&env::var("VECTORNEXT_PYTHON").unwrap_or_else(|_| "python".into()))?;
    let index = SearchIndex::build(
        snapshot,
        worker.space().id(),
        KeywordConfig {
            generated_weight: 1.0,
            ..Default::default()
        },
    )?;
    println!(
        "{}",
        serde_json::to_string(&ask(&index, &worker, request)?)?
    );
    Ok(())
}
fn main() {
    if let Err(e) = run() {
        eprintln!("{e}");
        std::process::exit(1);
    }
}
