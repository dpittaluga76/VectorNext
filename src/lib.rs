//! Local, single-writer storage. See docs/storage.md for the format and durability contract.
pub mod answers;
pub mod backup;
mod blob;
pub mod contracts;
mod frame;
pub mod ingestion;
pub mod search;
pub mod service;
mod storage;

pub use blob::{BlobStore, LocalBlobStore};
pub use storage::{Database, ReadSnapshot, Receipt};

pub type Result<T> = std::result::Result<T, Error>;

#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error("admission busy: {0}")]
    Busy(String),
    #[error("answer rejected: {message}")]
    AnswerRejected {
        message: String,
        diagnostics: Box<serde_json::Value>,
    },
    #[error("capability unavailable: {0}")]
    Unavailable(String),
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),
    #[error("serialization error: {0}")]
    Json(#[from] serde_json::Error),
    #[error("invalid record: {0}")]
    Invalid(String),
    #[error("revision conflict: {0}")]
    Conflict(String),
    #[error("operation ID was already used with different contents")]
    RetryConflict,
    #[error("corrupt storage: {0}")]
    Corrupt(String),
    #[error("another writer holds this database")]
    Locked,
    #[error("write outcome is uncertain; reopen the database and retry the operation ID")]
    Poisoned,
    #[error("durable storage requires Linux; on Windows use the Docker container")]
    UnsupportedPlatform,
}

pub(crate) fn sha256(bytes: &[u8]) -> String {
    use sha2::{Digest, Sha256};
    format!("{:x}", Sha256::digest(bytes))
}

pub(crate) fn require(ok: bool, message: &str) -> Result<()> {
    if ok {
        Ok(())
    } else {
        Err(Error::Invalid(message.into()))
    }
}
