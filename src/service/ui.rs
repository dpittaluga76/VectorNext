//! Browser projections never expose authoritative numbers as JavaScript numbers.
use super::*;
use crate::answers::{FieldSpec, Role, Turn};
use std::collections::BTreeSet;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct UploadMetadata {
    pub upload_id: String,
    pub filename: String,
    pub document_id: Option<String>,
    pub expected_revision: Option<String>,
    #[serde(default)]
    pub record_pointer: String,
    #[serde(default)]
    pub allow_partial: bool,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct UiQuestion {
    pub question: String,
    pub document_ids: BTreeSet<String>,
    #[serde(default)]
    pub history: Vec<Turn>,
    pub fields: Option<BTreeMap<String, FieldSpec>>,
    pub template: Option<String>,
    #[serde(default)]
    pub prose: bool,
    #[serde(default)]
    pub options: AnswerOptions,
}

fn identity(id: &str) -> Result<()> {
    require(
        (16..=64).contains(&id.len()) && id.bytes().all(|c| c.is_ascii_alphanumeric() || c == b'-'),
        "invalid upload identity",
    )
}
struct Preparing<'a> {
    app: &'a Application,
    id: String,
}
impl Drop for Preparing<'_> {
    fn drop(&mut self) {
        if let Ok(mut uploads) = self.app.uploads.lock() {
            uploads.remove(&self.id);
        }
    }
}

impl Application {
    // Call while holding the background lane. This also serializes legacy uploads.
    pub(super) fn check_document_change(&self, id: &str, expected: Option<&str>) -> Result<()> {
        let db = lock(&self.db)?;
        if db
            .ingestion_jobs()?
            .iter()
            .any(|j| j.request.document_id == id && j.stage != Stage::Committed)
        {
            return Err(Error::Conflict(
                "document has unfinished ingestion; resolve its job first".into(),
            ));
        }
        let snapshot = db.snapshot();
        if snapshot.document(id).map(|d| d.revision.as_str()) != expected {
            return Err(Error::Conflict(
                "document revision changed; refresh the library".into(),
            ));
        }
        Ok(())
    }
    pub fn ui_library(&self) -> Result<Value> {
        let db = lock(&self.db)?;
        let snapshot = db.snapshot();
        let jobs = db.ingestion_jobs()?;
        Ok(json!({"generation":snapshot.generation().to_string(),
            "documents":snapshot.documents().map(|d| json!({"document_id":d.document_id,"revision":d.revision,
                "filename":d.processing.get("ingestion").and_then(|v| v.get("source_name")).and_then(Value::as_str).unwrap_or(&d.document_id),
                "media_type":format!("{:?}",d.media_type).to_lowercase(),"chunks":d.chunks.len(),"bytes":d.original.bytes.to_string(),
                "processing":jobs.iter().any(|j| j.request.document_id == d.document_id && j.stage != Stage::Committed)})).collect::<Vec<_>>(),
            "jobs":jobs.iter().filter(|j| j.stage != Stage::Committed).map(|j| {
                let mut summary=job_summary(j); summary["filename"]=json!(j.request.config.source_name); summary
            }).collect::<Vec<_>>() }))
    }
    pub fn ui_upload(&self, metadata: UploadMetadata, bytes: Vec<u8>) -> Result<Value> {
        identity(&metadata.upload_id)?;
        require(
            !metadata.filename.is_empty()
                && metadata.filename.len() <= 255
                && !metadata.filename.chars().any(char::is_control)
                && !metadata.filename.contains(['/', '\\']),
            "invalid filename",
        )?;
        require(
            metadata.document_id.is_some() == metadata.expected_revision.is_some(),
            "replacement requires document_id and expected_revision",
        )?;
        let extension = metadata
            .filename
            .rsplit('.')
            .next()
            .unwrap_or("")
            .to_lowercase();
        let media_type = match extension.as_str() {
            "txt" => MediaType::Txt,
            "json" => MediaType::Json,
            "pdf" => MediaType::Pdf,
            _ => return Err(Error::Invalid("choose a TXT, PDF or JSON file".into())),
        };
        let id = metadata.upload_id.clone();
        let fingerprint = crate::sha256(&serde_json::to_vec(&json!([
            metadata.filename,
            metadata.document_id,
            metadata.expected_revision,
            metadata.record_pointer,
            metadata.allow_partial,
            crate::sha256(&bytes)
        ]))?);
        {
            let mut active = lock(&self.uploads)?;
            if let Some(existing) = active.get(&id) {
                if *existing != fingerprint {
                    return Err(Error::Conflict(
                        "upload identity belongs to different content".into(),
                    ));
                }
                return Err(Error::Busy(
                    "this upload is still being prepared; check its status".into(),
                ));
            }
            require(active.len() < 16, "too many preparing uploads")?;
            active.insert(id.clone(), fingerprint);
        }
        let _preparing = Preparing {
            app: self,
            id: id.clone(),
        };
        self.upload_named(
            Upload {
                job_id: format!("ui-{id}"),
                document_id: metadata.document_id.unwrap_or_else(|| format!("doc-{id}")),
                expected_revision: metadata.expected_revision,
                media_type,
                policy: Policy::Structural,
                record_pointer: metadata.record_pointer,
                allow_partial: metadata.allow_partial,
                source_base64: STANDARD.encode(bytes),
            },
            Some(metadata.filename),
        )
    }
    pub fn ui_upload_status(&self, id: &str) -> Result<Value> {
        identity(id)?;
        // Register before preparation; keep registration through durable submission.
        let active = lock(&self.uploads)?;
        if let Some(job) = lock(&self.db)?.ingestion_job(&format!("ui-{id}"))? {
            return Ok(json!({"state":"acknowledged","job":job_summary(&job)}));
        }
        Ok(json!({"state":if active.contains_key(id) {"preparing"} else {"absent"}}))
    }
    pub fn ui_remove(&self, id: &str, revision: &str) -> Result<Value> {
        require(!revision.is_empty(), "current revision required")?;
        let _background = busy(&self.background)?;
        self.check_document_change(id, Some(revision))?;
        let receipt = lock(&self.db)?.commit(Batch {
            operation_id: format!(
                "ui-remove-{}",
                crate::sha256(&serde_json::to_vec(&(id, revision))?)
            ),
            spaces: vec![],
            mutations: vec![Mutation::Delete {
                document_id: id.into(),
                expected_revision: revision.into(),
            }],
        })?;
        Ok(json!({"removed":true,"receipt_text":serde_json::to_string(&receipt)?}))
    }
    pub fn ui_source(&self, id: &str, revision: &str) -> Result<Value> {
        let snapshot = self.snapshot()?;
        let document = snapshot
            .document(id)
            .filter(|d| d.revision == revision)
            .ok_or_else(|| {
                Error::Conflict(
                    "this captured source is historical: the document was replaced or removed"
                        .into(),
                )
            })?;
        Ok(
            json!({"document_id":id,"revision":revision,"media_type":format!("{:?}",document.media_type).to_lowercase(),
            "processing_text":serde_json::to_string(&document.processing)?,
            "chunks":document.chunks.iter().map(|c|json!({"id":c.id,"text":c.evidence,"sources":source_view(&serde_json::to_value(&c.sources).unwrap_or(Value::Null))})).collect::<Vec<_>>()}),
        )
    }
    pub fn ui_original(&self, id: &str, revision: &str) -> Result<Vec<u8>> {
        let db = lock(&self.db)?;
        let snapshot = db.snapshot();
        let doc = snapshot
            .document(id)
            .filter(|d| d.revision == revision && d.media_type == MediaType::Pdf)
            .ok_or_else(|| Error::Conflict("original PDF revision is no longer current".into()))?;
        db.originals().get(&doc.original)
    }
    pub fn ui_ask(&self, input: UiQuestion) -> Result<Value> {
        require(
            !input.document_ids.is_empty() && input.document_ids.len() <= 400,
            "select 1..400 documents",
        )?;
        require(
            input.history.len() % 2 == 0
                && input.history.chunks_exact(2).all(|pair| {
                    matches!(pair[0].role, Role::User) && matches!(pair[1].role, Role::Assistant)
                }),
            "history requires complete question/answer exchanges",
        )?;
        // Validate all non-planning bounds before consuming inference capacity.
        let automatic = input.fields.is_none();
        let mut request = AskRequest {
            question: input.question,
            history: input.history,
            fields: input.fields.unwrap_or_else(|| {
                BTreeMap::from([(
                    "answer".into(),
                    FieldSpec {
                        kind: answers::FieldKind::String,
                        nullable: false,
                        description: String::new(),
                        pointer: None,
                    },
                )])
            }),
            filter: Filter::DocumentIds(input.document_ids.clone()),
            scope: Scope::Passage,
            template: input.template,
            prose: input.prose,
        };
        answers::validate_request(&request)?;
        input.options.validate()?;
        let started = Instant::now();
        let (index, space) = self.index(None)?;
        let snapshot = self.snapshot()?;
        require(
            input
                .document_ids
                .iter()
                .all(|id| snapshot.document(id).is_some()),
            "selected document is no longer available; refresh scope",
        )?;
        let _interactive = busy(&self.interactive)?;
        let models = RemoteModels::connect(self.processor.clone(), "interactive")?;
        require(
            models.space() == space,
            "processor/index embedding spaces differ",
        )?;
        let mut planning = Value::Null;
        if automatic {
            planning = models.call(
                "plan_fields",
                json!({"question":request.question,"history":request.history}),
            )?;
            request.fields = parse_plan(&planning)?;
            answers::validate_request(&request)?;
        }
        let report = answers::ask_with_options(&index, &models, request, input.options);
        let mut raw = match report {
            Ok(report) => serde_json::to_value(report)?,
            Err(Error::AnswerRejected {
                message,
                diagnostics,
            }) => {
                let mut raw = *diagnostics;
                raw["planning"] = planning;
                return Ok(
                    json!({"outcome":"rejected","message":message,"fields":[],"evidence":evidence_view(&raw),"workflow":workflow(&raw),"raw_report":serde_json::to_string(&raw)?}),
                );
            }
            Err(error) => return Err(error),
        };
        raw["planning"] = planning;
        raw["timings_ms"]["application_total"] = json!(started.elapsed().as_secs_f64() * 1000.0);
        answer_view(&raw)
    }
}

pub fn parse_plan(value: &Value) -> Result<BTreeMap<String, FieldSpec>> {
    #[derive(Deserialize)]
    #[serde(deny_unknown_fields)]
    struct Planned {
        name: String,
        kind: answers::FieldKind,
        nullable: bool,
        description: String,
    }
    #[derive(Deserialize)]
    #[serde(deny_unknown_fields)]
    struct Plan {
        status: String,
        fields: Vec<Planned>,
    }
    let plan:Plan=serde_json::from_value(value.get("plan").cloned().unwrap_or(Value::Null))
        .map_err(|_|Error::Invalid("the model could not plan valid answer fields; rephrase or specify fields in Advanced".into()))?;
    match plan.status.as_str() {
        "ready" => require(
            (1..=12).contains(&plan.fields.len()),
            "invalid planned field count; use 1..12 fields",
        )?,
        "needs_clarification" | "unsupported" => {
            require(
                plan.fields.is_empty(),
                "invalid declined plan: fields must be empty",
            )?;
            return Err(Error::Invalid(if plan.status == "needs_clarification" {
                "question needs clarification: name the subject and requested fact, or specify fields in Advanced"
            } else {
                "automatic planning does not support calculations across records; ask for separately reported facts"
            }.into()));
        }
        _ => {
            return Err(Error::Invalid(
                "invalid planning status; rephrase or specify fields in Advanced".into(),
            ));
        }
    }
    let mut fields = BTreeMap::new();
    for f in plan.fields {
        require(
            !f.name.is_empty()
                && f.name.len() <= 64
                && f.name
                    .bytes()
                    .all(|b| b.is_ascii_alphanumeric() || b == b'_')
                && f.description.len() <= 256,
            "invalid planned field; rephrase the question",
        )?;
        require(
            fields
                .insert(
                    f.name,
                    FieldSpec {
                        kind: f.kind,
                        nullable: f.nullable,
                        description: f.description,
                        pointer: None,
                    },
                )
                .is_none(),
            "duplicate planned fields; rephrase the question",
        )?;
    }
    Ok(fields)
}
fn source_view(sources: &Value) -> Value {
    json!(
        sources
            .as_array()
            .into_iter()
            .flatten()
            .map(|s| {
                let locator = &s["locator"];
                let label = if let Some(v) = locator.get("Text") {
                    format!(
                        "TXT lines {}–{} · bytes {}–{}",
                        v["line_start"], v["line_end"], v["bytes"]["start"], v["bytes"]["end"]
                    )
                } else if let Some(v) = locator.get("Pdf") {
                    format!(
                        "PDF page {} · {} extraction",
                        v["page"],
                        v["extraction"].as_str().unwrap_or("unknown")
                    )
                } else if let Some(v) = locator.get("Json") {
                    format!("JSON pointer {}", v["pointer"].as_str().unwrap_or(""))
                } else {
                    "Source location".into()
                };
                json!({"label":label,"raw_text":s.to_string()})
            })
            .collect::<Vec<_>>()
    )
}
fn evidence_view(raw: &Value) -> Value {
    json!(raw["evidence"].as_array().into_iter().flatten().map(|e|json!({"id":e["id"],"key":e["key"],"text":e.get("text").unwrap_or(&e["text_preview"]),"sources":source_view(&e["sources"]),"labels":if e["text_truncated"]==true{json!(["Captured diagnostic preview is truncated"])}else{e.get("labels").cloned().unwrap_or(json!([]))},
        "record_text":if e["record"].is_null(){None}else{Some(e["record"].to_string())}})).collect::<Vec<_>>())
}
fn workflow(raw: &Value) -> Value {
    let mut view = json!({"timings_ms":raw["timings_ms"],"generation":raw["generation"].to_string(),"search_text":raw["search_text"],
        "planning":if raw["planning"].is_null(){"explicit fields; planning skipped"}else{"local field planning recorded"},
        "evidence_count":raw["evidence"].as_array().map(Vec::len),"validation":raw["validation"],
        "details":"Function references describe the implementation, not instrumented calls. answers::ask_with_options performs retrieval, evidence selection and validation; model_worker.answers.handle performs recorded model operations. See exported diagnostics for recorded timings, calls and skipped steps."});
    if raw["selection"]["strategy"] == "facet_coverage_v1" {
        let selection = &raw["selection"];
        view["selection_summary"] = json!(format!(
            "Facet coverage: {} field queries, {} candidates, {} planned and {} admitted primary passages. Relevance is a heuristic, not a correctness guarantee.",
            selection["facet_queries"].as_array().map_or(0, Vec::len),
            selection["candidate_keys"].as_array().map_or(0, Vec::len),
            selection["planned_primary_keys"]
                .as_array()
                .map_or(0, Vec::len),
            selection["admitted_primary_keys"]
                .as_array()
                .map_or(0, Vec::len)
        ));
        view["facet_queries"] = selection["facet_queries"].clone();
        view["selection_functions"] = json!(
            "answers::facets::retrieve(), answers::facets::select(), answers::final_selection::select(); implementation references, not instrumented calls"
        );
    }
    view
}
pub fn answer_view(raw: &Value) -> Result<Value> {
    let fields=raw["answer"]["fields"].as_object().into_iter().flatten().map(|(name,f)|json!({"name":name,
        "value_text":f["value"].as_str().map(String::from).unwrap_or_else(||f["value"].to_string()),
        "kind":if f["value"].is_null(){json!("null")}else{raw["request"]["fields"][name]["kind"].clone()},
        "evidence_id":f["evidence_id"],"quote":f["quote"],"pointer":f["pointer"]})).collect::<Vec<_>>();
    Ok(
        json!({"outcome":raw["answer"]["status"],"fields":fields,"evidence":evidence_view(raw),"formatted":raw["formatted"],
        "draft_text":if raw["presentation_draft"].is_null(){None}else{Some(raw["presentation_draft"].to_string())},
        "workflow":workflow(raw),"raw_report":serde_json::to_string(raw)?}),
    )
}
