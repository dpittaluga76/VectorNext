//! T07 local model ingestion tool. A production API/scheduler belongs to T08/T09.
use std::{env, fs, path::Path};
use vectornext::{
    Database, Error, Result,
    contracts::MediaType,
    ingestion::{context::*, worker::*, *},
    search::{KeywordConfig, QueryVector, SearchIndex, SearchRequest},
};

fn run() -> Result<()> {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.len() == 4 && args[0] == "probe" {
        let db = Database::open(&args[1])?;
        let worker =
            ModelWorker::start(&env::var("VECTORNEXT_PYTHON").unwrap_or_else(|_| "python".into()))?;
        let mut weights = KeywordConfig::default();
        match args[3].as_str() {
            "plain" => weights.structural_weight = 0.0,
            "structural" => (),
            "generated" => weights.generated_weight = 1.0,
            _ => return Err(Error::Invalid("unknown probe policy".into())),
        }
        let index = SearchIndex::build(db.snapshot(), worker.space().id(), weights)?;
        let query = QueryVector {
            space_id: worker.space().id(),
            values: worker.embed(&format!("{}{}", worker.space().query_prefix, args[2]))?,
        };
        let result = index.search(&SearchRequest::hybrid(&args[2], query))?;
        let passages: Vec<_> = result
            .results
            .iter()
            .take(3)
            .map(|hit| {
                let (_, chunk) = index.resolve(&hit.key).unwrap();
                serde_json::json!({"key":hit.key,"evidence":chunk.evidence,"sources":chunk.sources})
            })
            .collect();
        println!(
            "{}",
            serde_json::to_string(&serde_json::json!({"trace":result,"passages":passages}))?
        );
        return Ok(());
    }
    if args.len() == 2 && args[0] == "inspect" {
        let db = Database::open(&args[1])?;
        println!(
            "{}",
            serde_json::to_string(&serde_json::json!({"generation":db.snapshot().generation(),
            "jobs":db.ingestion_jobs()?.iter().map(|j| serde_json::json!({"id":j.request.job_id,"stage":j.stage,"failure_count":j.failure_count,"last_failure":j.last_failure})).collect::<Vec<_>>(),
            "documents":db.snapshot().documents().collect::<Vec<_>>() }))?
        );
        return Ok(());
    }
    if !(5..=7).contains(&args.len()) {
        return Err(Error::Invalid("usage: model_ingest <db> <doc> <source> <job> <plain|structural|generated> [pdf-artifact|-] [record-pointer]; or inspect <db>".into()));
    }
    let policy = match args[4].as_str() {
        "plain" => Policy::Plain,
        "structural" => Policy::Structural,
        "generated" => Policy::Generated,
        _ => return Err(Error::Invalid("unknown context policy".into())),
    };
    let media = match Path::new(&args[2]).extension().and_then(|s| s.to_str()) {
        Some("txt") => MediaType::Txt,
        Some("json") => MediaType::Json,
        Some("pdf") => MediaType::Pdf,
        _ => return Err(Error::Invalid("expected TXT/PDF/JSON source".into())),
    };
    let mut db = Database::open(&args[0])?;
    let worker =
        ModelWorker::start(&env::var("VECTORNEXT_PYTHON").unwrap_or_else(|_| "python".into()))?;
    let artifact: Option<pdf::Artifact> = if media == MediaType::Pdf {
        Some(serde_json::from_slice(&fs::read(
            args.get(5)
                .ok_or_else(|| Error::Invalid("PDF artifact required".into()))?,
        )?)?)
    } else {
        None
    };
    let mut config = if let Some(a) = &artifact {
        a.config(worker.space(), false)?
    } else {
        IngestConfig::new(worker.space())
    };
    config.context = Some(ContextConfig::new(
        policy.clone(),
        (policy == Policy::Generated).then(|| worker.profile().generator.clone()),
    ));
    config.target_tokens = 180.min(config.chunk_limit());
    config.record_pointer = args.get(6).cloned().unwrap_or_default();
    let base: Box<dyn Processor + '_> = if let Some(artifact) = artifact {
        Box::new(pdf::PdfProcessor {
            local: LocalProcessor { encoder: &worker },
            artifact,
        })
    } else {
        Box::new(LocalProcessor { encoder: &worker })
    };
    let processor = ContextProcessor {
        base,
        generator: &worker,
    };
    let expected_revision = match db.ingestion_job(&args[3])? {
        Some(job) => job.request.expected_revision,
        None => db.snapshot().document(&args[1]).map(|d| d.revision.clone()),
    };
    let mut job = db.submit_ingestion(
        IngestRequest {
            job_id: args[3].clone(),
            document_id: args[1].clone(),
            expected_revision,
            media_type: media,
            config,
        },
        &fs::read(&args[2])?,
    )?;
    let started = std::time::Instant::now();
    while job.stage != Stage::Committed {
        eprintln!("{}: {:?}", job.request.job_id, job.stage);
        job = db.advance_ingestion(&args[3], &processor)?;
    }
    println!(
        "{}",
        serde_json::to_string(
            &serde_json::json!({"job":job.request.job_id,"stage":job.stage,
        "generation":db.snapshot().generation(), "revision":job.input_sha256,"space":worker.space().id(),
        "chunks":job.draft.document.chunks.len(),"generated":job.draft.document.chunks.iter().filter(|c| c.generated_context.is_some()).count(),
        "seconds":started.elapsed().as_secs_f64(),"worker":worker.stats()?,"receipt":job.receipt})
        )?
    );
    Ok(())
}
fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(1);
    }
}
