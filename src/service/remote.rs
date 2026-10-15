use crate::{
    Error, Result,
    answers::*,
    contracts::*,
    ingestion::{Encoder, context::*, worker::ModelProfile},
    require,
};
use serde_json::{Value, json};
use std::{collections::BTreeMap, io::Read, time::Duration};

#[derive(Clone)]
pub struct Client {
    pub url: String,
}
impl Client {
    pub fn new(url: String) -> Self {
        Self {
            url: url.trim_end_matches('/').into(),
        }
    }
    pub fn request(
        &self,
        path: &str,
        body: Option<&[u8]>,
        seconds: u64,
        limit: usize,
    ) -> Result<Vec<u8>> {
        let agent = ureq::AgentBuilder::new()
            .timeout(Duration::from_secs(seconds))
            .timeout_connect(Duration::from_secs(3))
            .redirects(0)
            .try_proxy_from_env(false)
            .build();
        let url = format!("{}{path}", self.url);
        let reply = if let Some(body) = body {
            agent
                .post(&url)
                .set("Content-Type", "application/json")
                .send_bytes(body)
        } else {
            agent.get(&url).call()
        };
        let reply = match reply {
            Ok(reply) => reply,
            Err(ureq::Error::Status(503, response)) => {
                let mut raw = String::new();
                response.into_reader().take(4096).read_to_string(&mut raw)?;
                if serde_json::from_str::<Value>(&raw)
                    .ok()
                    .is_some_and(|v| v["code"] == "busy")
                {
                    return Err(Error::Busy(format!("processor {path}: CPU admission busy")));
                }
                return Err(Error::Unavailable(format!("processor {path}: HTTP 503")));
            }
            Err(error) => return Err(Error::Unavailable(format!("processor {path}: {error}"))),
        };
        let mut bytes = vec![];
        reply
            .into_reader()
            .take(limit as u64 + 1)
            .read_to_end(&mut bytes)?;
        require(bytes.len() <= limit, "processor reply exceeds limit")?;
        Ok(bytes)
    }
    pub fn health(&self) -> Result<Value> {
        Ok(serde_json::from_slice(
            &self.request("/health", None, 3, 65536)?,
        )?)
    }
    pub fn rpc(&self, lane: &str, value: Value) -> Result<Value> {
        let body = serde_json::to_vec(&value)?;
        require(body.len() <= 4 * 1024 * 1024, "model request exceeds 4 MiB")?;
        let seconds = if value["op"] == "answer" { 750 } else { 450 };
        let response: Value = serde_json::from_slice(&self.request(
            &format!("/rpc/{lane}"),
            Some(&body),
            seconds,
            4 * 1024 * 1024,
        )?)?;
        if let Some(error) = response.get("error") {
            return Err(Error::Unavailable(format!("model operation: {error}")));
        }
        response
            .get("result")
            .cloned()
            .ok_or_else(|| Error::Unavailable("invalid processor reply".into()))
    }
    pub fn pdf(&self, bytes: &[u8]) -> Result<crate::ingestion::pdf::Artifact> {
        crate::ingestion::pdf::Artifact::from_slice(&self.request(
            "/pdf",
            Some(bytes),
            210,
            16 * 1024 * 1024,
        )?)
    }
}
pub struct RemoteModels {
    pub client: Client,
    pub lane: &'static str,
    pub profile: ModelProfile,
}
impl RemoteModels {
    pub fn connect(client: Client, lane: &'static str) -> Result<Self> {
        let profile: ModelProfile =
            serde_json::from_value(client.rpc(lane, json!({"op":"profile"}))?)?;
        profile.space.validate()?;
        ContextConfig::new(Policy::Generated, Some(profile.generator.clone()))
            .validate(&profile.space)?;
        Ok(Self {
            client,
            lane,
            profile,
        })
    }
    pub(crate) fn call(&self, op: &str, input: Value) -> Result<Value> {
        self.client.rpc(self.lane, json!({"op":op,"input":input}))
    }
}
impl Encoder for RemoteModels {
    fn space(&self) -> EmbeddingSpace {
        self.profile.space.clone()
    }
    fn count_tokens(&self, input: &str) -> Result<usize> {
        Ok(serde_json::from_value(self.call("count", json!(input))?)?)
    }
    fn embed(&self, input: &str) -> Result<Vec<f32>> {
        let vector: Vec<f32> = serde_json::from_value(self.call("embed", json!(input))?)?;
        self.profile.space.validate_vector(&vector)?;
        Ok(vector)
    }
}
impl Generator for RemoteModels {
    fn generate(&self, input: &ContextInput) -> Result<Option<String>> {
        require(
            input.space == self.profile.space
                && input.config.generator.as_ref() == Some(&self.profile.generator),
            "processor generation identity mismatch",
        )?;
        Ok(serde_json::from_value(
            self.call("generate", serde_json::to_value(input)?)?,
        )?)
    }
}
impl AnswerModels for RemoteModels {
    fn rerank(&self, query: &str, passages: &[String]) -> Result<Rerank> {
        Ok(serde_json::from_value(self.call(
            "rerank",
            json!({"query":query,"passages":passages}),
        )?)?)
    }
    fn answer_tokens(&self, input: &AnswerInput) -> Result<usize> {
        Ok(serde_json::from_value(
            self.call("answer_tokens", serde_json::to_value(input)?)?,
        )?)
    }
    fn extract(&self, input: &AnswerInput) -> Result<Extraction> {
        Ok(serde_json::from_value(
            self.call("answer", serde_json::to_value(input)?)?,
        )?)
    }
    fn rewrite(&self, question: &str, answer: &Answer) -> Result<Value> {
        let literals: BTreeMap<_, _> = answer
            .fields
            .iter()
            .map(|(name, proof)| {
                (
                    name,
                    proof
                        .value
                        .as_str()
                        .map(String::from)
                        .unwrap_or_else(|| proof.value.to_string()),
                )
            })
            .collect();
        self.call(
            "rewrite",
            json!({"question":question,"field_literals":literals}),
        )
    }
}
/// Structured lookup requires neither CPU models nor generation.
pub struct SourceOnly(pub EmbeddingSpace);
impl Encoder for SourceOnly {
    fn space(&self) -> EmbeddingSpace {
        self.0.clone()
    }
    fn count_tokens(&self, _: &str) -> Result<usize> {
        Err(Error::Unavailable(
            "CPU models are not used by source lookup".into(),
        ))
    }
    fn embed(&self, _: &str) -> Result<Vec<f32>> {
        Err(Error::Unavailable(
            "CPU models are not used by source lookup".into(),
        ))
    }
}
impl AnswerModels for SourceOnly {
    fn rerank(&self, _: &str, _: &[String]) -> Result<Rerank> {
        Err(Error::Unavailable("reranking unavailable".into()))
    }
    fn answer_tokens(&self, _: &AnswerInput) -> Result<usize> {
        Err(Error::Unavailable("generation unavailable".into()))
    }
    fn extract(&self, _: &AnswerInput) -> Result<Extraction> {
        Err(Error::Unavailable("generation unavailable".into()))
    }
    fn rewrite(&self, _: &str, _: &Answer) -> Result<Value> {
        Err(Error::Unavailable("structured lookup supports deterministic templates; use passage scope for prose drafts".into()))
    }
}
