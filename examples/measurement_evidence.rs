//! Offline evidence inventory from one immutable ingestion snapshot.
use std::{fs, io::Write};
use vectornext::{answers::measurement::document_evidence, contracts::DocumentRevision};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    if args.len() != 2 {
        return Err("usage: measurement_evidence SNAPSHOT.json NEW_OUTPUT.json".into());
    }
    let document: DocumentRevision = serde_json::from_slice(&fs::read(&args[0])?)?;
    let mut file = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&args[1])?;
    file.write_all(&serde_json::to_vec_pretty(&document_evidence(&document))?)?;
    file.sync_all()?;
    Ok(())
}
