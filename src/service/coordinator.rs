use super::*;
use std::panic::{AssertUnwindSafe, catch_unwind};

#[derive(Serialize)]
pub(super) struct State {
    state: &'static str,
    last_error: Option<String>,
}
impl Default for State {
    fn default() -> Self {
        Self {
            state: "not_started",
            last_error: None,
        }
    }
}
impl Application {
    pub(super) fn coordinator_status(&self) -> Result<Value> {
        let state = lock(&self.coordinator)?;
        Ok(json!({"state":state.state,"last_error":state.last_error,
            "recovery":if state.state == "failed" { Some("Restart the API; unfinished jobs resume from durable stages. Explicitly retry saved job failures.") } else { None }}))
    }
    pub(super) fn require_coordinator(&self) -> Result<()> {
        if self.stopping.load(Ordering::Relaxed)
            || matches!(lock(&self.coordinator)?.state, "failed" | "stopped")
        {
            return Err(Error::Unavailable(
                "ingestion coordinator stopped; inspect readiness and restart the API".into(),
            ));
        }
        Ok(())
    }
    pub(super) fn start_coordinator<F>(self: &Arc<Self>, mut step: F) -> std::thread::JoinHandle<()>
    where
        F: FnMut(&Application) -> Result<bool> + Send + 'static,
    {
        let app = self.clone();
        // Set before spawning: duplicate starts cannot run a second coordinator.
        let start = if let Ok(mut state) = self.coordinator.lock() {
            if state.state == "not_started" {
                state.state = "running";
                true
            } else {
                false
            }
        } else {
            false
        };
        std::thread::spawn(move || {
            if !start {
                return;
            }
            let outcome = catch_unwind(AssertUnwindSafe(|| -> Result<()> {
                while !app.stopping.load(Ordering::Relaxed) {
                    if !step(&app)? {
                        std::thread::sleep(Duration::from_millis(500));
                    }
                }
                Ok(())
            }));
            let error = match outcome {
                Ok(Ok(())) => None,
                Ok(Err(error)) => Some(error.to_string()),
                Err(_) => Some("unexpected ingestion coordinator panic; restart required".into()),
            };
            if let Some(error) = &error {
                eprintln!("ingestion coordinator stopped: {error}");
            }
            if let Ok(mut state) = app.coordinator.lock() {
                state.state = if error.is_some() { "failed" } else { "stopped" };
                state.last_error = error.map(|e| e.chars().take(4096).collect());
            }
        })
    }
    pub(super) fn pdf_diagnostics(&self, job: &IngestJob) -> Result<Value> {
        let config = job.request.config.pdf.as_ref().unwrap();
        let raw = {
            let db = lock(&self.db)?;
            let size =
                std::fs::metadata(db.root.join("blobs").join(&config.artifact_sha256))?.len();
            require(size <= 16 * 1024 * 1024, "stored PDF artifact too large")?;
            db.originals().get(&BlobRef {
                sha256: config.artifact_sha256.clone(),
                bytes: size,
            })?
        };
        let artifact = pdf::Artifact::from_slice(&raw)?;
        require(
            artifact.id()? == config.artifact_sha256
                && artifact.source_sha256 == job.draft.document.original.sha256
                && artifact.profile_sha256 == config.profile_sha256,
            "PDF diagnostic identity mismatch",
        )?;
        let warnings: Vec<_> = artifact.warnings.iter().take(100).map(|w| json!({
            "code":w.code,"page":w.page,"bbox":w.bbox,"message":w.message.chars().take(1000).collect::<String>()
        })).collect();
        Ok(
            json!({"status":artifact.status,"allow_partial":config.allow_partial,
            "source_sha256":artifact.source_sha256,"artifact_sha256":config.artifact_sha256,
            "pages":artifact.pages,"items":artifact.items.len(),"warnings":warnings,
            "warning_count":artifact.warnings.len(),"warnings_truncated":artifact.warnings.len()>100,
            "next_action":if artifact.status == "partial" && !config.allow_partial {
                "Review page warnings. To accept recovered text explicitly, submit a new job ID with --allow-partial; the existing job policy is immutable."
            } else { "Review page warnings and extraction coverage; illustrations are not interpreted." }}),
        )
    }
}

#[cfg(all(test, target_os = "linux"))]
mod tests {
    use super::*;
    #[test]
    fn panic_is_visible_and_restart_preserves_committed_and_pending_jobs() {
        let root = tempfile::tempdir().unwrap();
        let mut db = Database::open(root.path()).unwrap();
        let encoder = TestEncoder::default();
        for id in ["committed", "pending"] {
            db.submit_ingestion(
                IngestRequest {
                    job_id: id.into(),
                    document_id: id.into(),
                    expected_revision: None,
                    media_type: MediaType::Txt,
                    config: IngestConfig::new(encoder.space()),
                },
                b"Original evidence.",
            )
            .unwrap();
            if id == "committed" {
                while db
                    .advance_ingestion(
                        id,
                        &LocalProcessor {
                            encoder: encoder.clone(),
                        },
                    )
                    .unwrap()
                    .stage
                    != Stage::Committed
                {}
            }
        }
        let before = serde_json::to_value(db.snapshot().document("committed")).unwrap();
        drop(db);
        let app = Application::open(root.path(), Client::new("http://127.0.0.1:1".into())).unwrap();
        app.start_coordinator(|app| {
            *lock(&app.active)? = Some("pending".into());
            let _lane = lock(&app.background)?;
            panic!("injected processing panic");
        })
        .join()
        .unwrap();
        assert_eq!(
            app.job("pending").unwrap()["coordinator"]["state"],
            "failed"
        );
        assert_eq!(app.ready().unwrap()["ready"], false);
        assert_eq!(app.storage_status().unwrap()["storage_ready"], true);
        assert!(app.retry("pending").is_err());
        drop(app);
        let mut db = Database::open(root.path()).unwrap();
        assert_eq!(
            serde_json::to_value(db.snapshot().document("committed")).unwrap(),
            before
        );
        while db
            .advance_ingestion(
                "pending",
                &LocalProcessor {
                    encoder: encoder.clone(),
                },
            )
            .unwrap()
            .stage
            != Stage::Committed
        {}
        let receipt = db.commit_ingestion("pending").unwrap().receipt;
        assert_eq!(db.commit_ingestion("pending").unwrap().receipt, receipt);
        assert_eq!(db.snapshot().generation(), 2);
    }
    #[test]
    fn fatal_error_stops_coordinator_and_duplicate_start_cannot_hide_failure() {
        let root = tempfile::tempdir().unwrap();
        let app = Application::open(root.path(), Client::new("http://127.0.0.1:1".into())).unwrap();
        app.start_coordinator(|_| Err(Error::Poisoned))
            .join()
            .unwrap();
        app.start_coordinator(|_| panic!("must not restart in place"))
            .join()
            .unwrap();
        assert_eq!(app.coordinator_status().unwrap()["state"], "failed");
    }
}
