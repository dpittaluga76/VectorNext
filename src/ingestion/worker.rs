//! Bounded JSON-lines bridge to the local CPU model process. No database handles.
use super::{context::*, *};
use std::{
    io::{BufRead, BufReader, Read, Write},
    process::{Child, ChildStdin, Command, Stdio},
    sync::{Mutex, mpsc},
    time::Duration,
};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ModelProfile {
    pub space: EmbeddingSpace,
    pub generator: GenerationConfig,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub supported_generators: Vec<GenerationConfig>,
}
impl ModelProfile {
    pub fn supports(&self, generator: Option<&GenerationConfig>) -> bool {
        generator.is_some_and(|g| g == &self.generator || self.supported_generators.contains(g))
    }
}
struct Process {
    child: Child,
    stdin: ChildStdin,
    replies: mpsc::Receiver<std::io::Result<Vec<u8>>>,
    failed: bool,
}
impl Drop for Process {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}
pub struct ModelWorker {
    process: Mutex<Process>,
    profile: ModelProfile,
}
impl ModelWorker {
    pub fn start(python: &str) -> Result<Self> {
        let mut child = Command::new(python)
            .args(["-m", "model_worker.server"])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()?;
        let stdin = child.stdin.take().unwrap();
        let stdout = child.stdout.take().unwrap();
        let (tx, replies) = mpsc::sync_channel(1);
        std::thread::spawn(move || {
            let mut reader = BufReader::new(stdout);
            loop {
                let mut bytes = vec![];
                let result = reader
                    .by_ref()
                    .take(4 * 1024 * 1024 + 1)
                    .read_until(b'\n', &mut bytes);
                let stop = result
                    .as_ref()
                    .map_or(true, |n| *n == 0 || *n > 4 * 1024 * 1024);
                let result = result.and_then(|n| {
                    if stop {
                        Err(std::io::Error::other(
                            "worker closed or exceeded reply limit",
                        ))
                    } else {
                        Ok(bytes[..n].to_vec())
                    }
                });
                if tx.send(result).is_err() || stop {
                    break;
                }
            }
        });
        let process = Mutex::new(Process {
            child,
            stdin,
            replies,
            failed: false,
        });
        let profile: ModelProfile = serde_json::from_value(Self::call_process(
            &process,
            serde_json::json!({"op":"profile"}),
        )?)?;
        profile.space.validate()?;
        ContextConfig::new(Policy::Generated, Some(profile.generator.clone()))
            .validate(&profile.space)?;
        Ok(Self { process, profile })
    }
    fn call_process(process: &Mutex<Process>, request: Value) -> Result<Value> {
        let mut p = process
            .lock()
            .map_err(|_| crate::Error::Invalid("worker lock poisoned".into()))?;
        require(
            !p.failed,
            "worker unavailable; restart the processor and resume the job",
        )?;
        let timeout = if request.get("op").and_then(Value::as_str) == Some("answer") {
            720
        } else {
            420
        };
        let mut bytes = serde_json::to_vec(&request)?;
        require(bytes.len() <= 4 * 1024 * 1024, "worker request too large")?;
        bytes.push(b'\n');
        let operation = (|| -> Result<Value> {
            p.stdin.write_all(&bytes)?;
            p.stdin.flush()?;
            let bytes = p
                .replies
                .recv_timeout(Duration::from_secs(timeout))
                .map_err(|_| {
                    crate::Error::Invalid("model worker timed out/disconnected".into())
                })??;
            let response: Value = serde_json::from_slice(&bytes)?;
            if let Some(error) = response.get("error") {
                return Err(crate::Error::Invalid(format!("model worker: {error}")));
            }
            response
                .get("result")
                .cloned()
                .ok_or_else(|| crate::Error::Invalid("invalid worker response".into()))
        })();
        if operation.is_err() {
            p.failed = true;
            let _ = p.child.kill();
        }
        operation
    }
    pub fn profile(&self) -> &ModelProfile {
        &self.profile
    }
    pub(crate) fn call(&self, request: Value) -> Result<Value> {
        Self::call_process(&self.process, request)
    }
    pub fn stats(&self) -> Result<Value> {
        Self::call_process(&self.process, serde_json::json!({"op":"stats"}))
    }
}
impl Encoder for ModelWorker {
    fn space(&self) -> EmbeddingSpace {
        self.profile.space.clone()
    }
    fn count_tokens(&self, input: &str) -> Result<usize> {
        Ok(serde_json::from_value(Self::call_process(
            &self.process,
            serde_json::json!({"op":"count","input":input}),
        )?)?)
    }
    fn embed(&self, input: &str) -> Result<Vec<f32>> {
        let vector: Vec<f32> = serde_json::from_value(Self::call_process(
            &self.process,
            serde_json::json!({"op":"embed","input":input}),
        )?)?;
        self.profile.space.validate_vector(&vector)?;
        Ok(vector)
    }
}
impl Generator for ModelWorker {
    fn generate(&self, input: &ContextInput) -> Result<Option<String>> {
        require(
            input.space == self.profile.space
                && self.profile.supports(input.config.generator.as_ref()),
            "worker generation identity mismatch",
        )?;
        Ok(serde_json::from_value(Self::call_process(
            &self.process,
            serde_json::json!({"op":"generate","input":input}),
        )?)?)
    }
}
