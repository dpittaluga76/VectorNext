//! Offline, create-only diagnostic output. This never calls a model.
use std::{fs, io::Write};
use vectornext::answers::{Answer, AnswerInput, measurement::compare_candidate};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    if args.len() != 3 {
        return Err(
            "usage: measurement_candidate INPUT.json CANDIDATE.json NEW_OUTPUT.json".into(),
        );
    }
    let input: AnswerInput = serde_json::from_slice(&fs::read(&args[0])?)?;
    let captured: serde_json::Value = serde_json::from_slice(&fs::read(&args[1])?)?;
    // Accept the complete immutable processor reply without a Python numeric
    // round trip when extracting the candidate from its transport envelope.
    let value = captured
        .get("result")
        .and_then(|v| v.get("answer"))
        .or_else(|| captured.get("answer"))
        .unwrap_or(&captured);
    let candidate: Answer = serde_json::from_value(value.clone())?;
    let result = compare_candidate(&input, &candidate);
    let mut file = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&args[2])?;
    file.write_all(&serde_json::to_vec_pretty(&result)?)?;
    file.sync_all()?;
    Ok(())
}
