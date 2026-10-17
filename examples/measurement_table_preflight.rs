//! Operational budget probe only. Real CPU encoders; no LLM generation or scoring.
use serde_json::{Value, json};
use std::{cell::RefCell, collections::BTreeMap, fs, io::Write, path::Path};
use vectornext::{
    Database, Error, Result,
    answers::*,
    contracts::*,
    ingestion::{context::*, *},
    search::{Filter, KeywordConfig, SearchIndex},
    service::remote::{Client, RemoteModels},
};

const STOP: &str = "measurement preflight stopped before generation";

fn save(path: &Path, value: &Value) -> Result<()> {
    let mut file = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(path)?;
    file.write_all(&serde_json::to_vec_pretty(value)?)?;
    file.sync_all()?;
    Ok(())
}

struct Probe<'a> {
    models: &'a RemoteModels,
    events: RefCell<Vec<Value>>,
}
impl Encoder for Probe<'_> {
    fn space(&self) -> EmbeddingSpace {
        self.models.space()
    }
    fn count_tokens(&self, text: &str) -> Result<usize> {
        self.models.count_tokens(text)
    }
    fn embed(&self, text: &str) -> Result<Vec<f32>> {
        self.models.embed(text)
    }
}
impl AnswerModels for Probe<'_> {
    fn rerank(&self, question: &str, passages: &[String]) -> Result<Rerank> {
        let reply = self.models.rerank(question, passages);
        self.events
            .borrow_mut()
            .push(json!({"operation":"rerank", "question":question,
            "passages":passages, "result":reply.as_ref().ok(),
            "error":reply.as_ref().err().map(ToString::to_string)}));
        reply
    }
    fn answer_tokens(&self, input: &AnswerInput) -> Result<usize> {
        let reply = self.models.answer_tokens(input);
        self.events
            .borrow_mut()
            .push(json!({"operation":"answer_tokens", "input":input,
            "tokens":reply.as_ref().ok(), "error":reply.as_ref().err().map(ToString::to_string)}));
        reply
    }
    fn extract(&self, input: &AnswerInput) -> Result<Extraction> {
        self.events
            .borrow_mut()
            .push(json!({"operation":"stopped_before_generation", "input":input}));
        Err(Error::Invalid(STOP.into()))
    }
    fn rewrite(&self, _: &str, _: &Answer) -> Result<Value> {
        Err(Error::Invalid("preflight never generates prose".into()))
    }
}

fn main() -> std::result::Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    if args.len() != 3 || args[2] != "http://processor:8090" {
        return Err(
            "usage: measurement_table_preflight INPUT NEW_OUTPUT http://processor:8090".into(),
        );
    }
    let input: Value = serde_json::from_slice(&fs::read(&args[0])?)?;
    if input["kind"] != "t39_table_budget_preflight" || input["split"] != "development" {
        return Err("explicit development-only preflight input required".into());
    }
    let output = Path::new(&args[1]);
    fs::create_dir(output)?;
    let client = Client::new(args[2].clone());
    let mut models = RemoteModels::connect(client.clone(), "background")?;
    save(
        &output.join("profile.json"),
        &serde_json::to_value(&models.profile)?,
    )?;
    let temp = tempfile::tempdir()?; // Linux storage only; never a normal app mount.
    let mut db = Database::open(temp.path().join("db"))?;
    let mut documents = vec![];
    for (n, document) in input["documents"]
        .as_array()
        .ok_or("documents required")?
        .iter()
        .enumerate()
    {
        let id = document["name"].as_str().ok_or("name required")?;
        let source = document["source_text"]
            .as_str()
            .ok_or("source text required")?;
        let mut config = IngestConfig::new(models.space());
        config.target_tokens = 180;
        config.record_pointer = "/records".into();
        config.context = Some(ContextConfig::new(Policy::Structural, None));
        let job_id = format!("preflight-{n}");
        let mut job = db.submit_ingestion(
            IngestRequest {
                job_id: job_id.clone(),
                document_id: id.into(),
                expected_revision: None,
                media_type: MediaType::Json,
                config: config.clone(),
            },
            source.as_bytes(),
        )?;
        let processor = LocalProcessor { encoder: &models };
        let mut failure = None;
        for _ in 0..6 {
            if job.stage == Stage::Committed {
                break;
            }
            match db.advance_ingestion(&job_id, &processor) {
                Ok(next) => job = next,
                Err(error) => {
                    failure = Some(error.to_string());
                    break;
                }
            }
        }
        let mut chunks = vec![];
        for chunk in &job.draft.document.chunks {
            let text = configured_input(&config, chunk);
            chunks.push(json!({"chunk":chunk, "embedding_input":text,
                "embedding_tokens":models.count_tokens(&text)?}));
        }
        let record = json!({"document":id, "stage":job.stage, "revision":job.input_sha256,
            "config":config, "chunks":chunks, "error":failure, "receipt":job.receipt});
        save(&output.join(format!("document-{n}.json")), &record)?;
        documents.push(record);
    }
    // Tokenization uses the resident model's native template under a real lease.
    // It must not change models or invoke generation. Normal API storage is untouched.
    let health = Client::new("http://llm:8080".into()).health()?;
    save(&output.join("generation-health.json"), &health)?;
    if health["loaded_model"] != "nuextract"
        || !health["lease"].is_null()
        || health["active"] != false
        || health["interactive_waiting"] != 0
    {
        return Err("NuExtract must already be resident and idle for token-only preflight".into());
    }
    let token = format!(
        "table-preflight-{}",
        temp.path().file_name().unwrap().to_string_lossy()
    );
    // Answer template/tokenization operations carry interactive priority in the
    // unchanged worker; the lease must match even though no tokens are generated.
    let lease =
        json!({"model":"nuextract", "token":token, "owner":token, "priority":"interactive"});
    save(&output.join("lease-request.json"), &lease)?;
    let acquired = client.generation("acquire", lease.clone());
    let work = (|| -> Result<()> {
        let identity = acquired?;
        save(&output.join("lease-identity.json"), &identity)?;
        if identity["model"] != "nuextract" || identity["token"] != token {
            return Err(Error::Invalid("preflight lease identity mismatch".into()));
        }
        models.lease = Some(lease);
        let index =
            SearchIndex::build(db.snapshot(), models.space().id(), KeywordConfig::default())?;
        let mut case_failed = false;
        for case in input["cases"]
            .as_array()
            .ok_or_else(|| Error::Invalid("cases required".into()))?
        {
            let n = case["number"]
                .as_u64()
                .ok_or_else(|| Error::Invalid("case number required".into()))?;
            let document = case["document"]
                .as_str()
                .ok_or_else(|| Error::Invalid("case document required".into()))?;
            let probe = Probe {
                models: &models,
                events: RefCell::new(vec![]),
            };
            let request = AskRequest {
                question: case["question"].as_str().unwrap().into(),
                history: vec![],
                fields: BTreeMap::from([(
                    "answer".into(),
                    FieldSpec {
                        kind: FieldKind::String,
                        nullable: false,
                        description: "Return the requested source value as a string.".into(),
                        pointer: None,
                    },
                )]),
                filter: Filter::DocumentIds([document.into()].into()),
                scope: Scope::Passage,
                template: None,
                prose: false,
            };
            let result = ask(&index, &probe, request);
            let stopped = matches!(&result, Err(Error::Invalid(message)) if message == STOP);
            case_failed |= !stopped;
            save(
                &output.join(format!("case-{n}.json")),
                &json!({"number":n,
                "stopped_before_generation":stopped, "error":result.as_ref().err().map(ToString::to_string),
                "events":probe.events.into_inner(), "answer_scored":false}),
            )?;
        }
        if case_failed {
            return Err(Error::Invalid(
                "one or more budget probes did not reach the generation boundary".into(),
            ));
        }
        Ok(())
    })();
    // Also reconcile an uncertain acquire. Never leave the probe's lease behind.
    let release = client.generation("release", json!({"token":token}));
    save(
        &output.join("finished.json"),
        &json!({"generation_calls":0, "answer_scored":false,
        "work_error":work.as_ref().err().map(ToString::to_string),
        "release":release.as_ref().ok(), "release_error":release.as_ref().err().map(ToString::to_string)}),
    )?;
    work?;
    release?;
    Ok(())
}
