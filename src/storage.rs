use crate::{
    BlobStore, Error, LocalBlobStore, Result,
    blob::{ensure_dir, sync_dir},
    contracts::*,
    frame::{self, ReadFrame},
    require, sha256,
};
use fs2::FileExt;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs::{self, File, OpenOptions},
    io::{Read, Seek, SeekFrom, Write},
    path::{Path, PathBuf},
    sync::Arc,
};

mod checkpoint;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct Receipt {
    pub generation: u64,
    pub request_sha256: String,
}

#[derive(Clone, Default, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct State {
    generation: u64,
    spaces: BTreeMap<String, EmbeddingSpace>,
    documents: BTreeMap<String, Arc<DocumentRevision>>,
    receipts: BTreeMap<String, Receipt>,
    /// Tombstoned and replaced revisions remain reserved forever in format 1.
    revisions: BTreeMap<String, BTreeSet<String>>,
}

#[derive(Clone)]
pub struct ReadSnapshot(Arc<State>);

impl ReadSnapshot {
    pub fn generation(&self) -> u64 {
        self.0.generation
    }
    pub fn document(&self, id: &str) -> Option<&DocumentRevision> {
        self.0.documents.get(id).map(Arc::as_ref)
    }
    pub fn documents(&self) -> impl Iterator<Item = &DocumentRevision> {
        self.0.documents.values().map(Arc::as_ref)
    }
    pub(crate) fn shared_documents(&self) -> impl Iterator<Item = Arc<DocumentRevision>> + '_ {
        self.0.documents.values().cloned()
    }
    pub fn space(&self, id: &str) -> Option<&EmbeddingSpace> {
        self.0.spaces.get(id)
    }
    pub fn spaces(&self) -> impl Iterator<Item = (&String, &EmbeddingSpace)> {
        self.0.spaces.iter()
    }
    pub fn receipt(&self, operation_id: &str) -> Option<&Receipt> {
        self.0.receipts.get(operation_id)
    }
    pub fn validate_query_vector(&self, space_id: &str, vector: &[f32]) -> Result<()> {
        self.space(space_id)
            .ok_or_else(|| Error::Invalid("unknown query embedding space".into()))?
            .validate_vector(vector)
    }
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Prepared {
    generation: u64,
    batch: Batch,
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Commit {
    generation: u64,
    prepare_sha256: String,
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Checkpoint {
    journal_offset: u64,
    journal_sha256: String,
    state: State,
}

pub struct Database {
    pub(crate) root: PathBuf,
    // The OS releases this lock even on process termination. Never unlink the lock file.
    _lock: WriterLock,
    journal: File,
    blobs: LocalBlobStore,
    state: Arc<State>,
    committed_offset: u64,
    pub(crate) poisoned: bool,
    #[cfg(test)]
    fail_at: Option<Fault>,
    #[cfg(test)]
    pub(crate) job_fail_at: Option<crate::ingestion::JobFault>,
}

struct WriterLock(File);

impl Drop for WriterLock {
    fn drop(&mut self) {
        // fork() can briefly inherit descriptors before exec closes them. Explicit
        // unlock prevents a child from extending this writer's lock lifetime.
        let _ = FileExt::unlock(&self.0);
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Fault {
    PrepareWrite,
    PrepareSync,
    CommitWrite,
    CommitSync,
    SnapshotChunk,
    SnapshotWrite,
    SnapshotSync,
    SnapshotRename,
    SnapshotDirSync,
}

fn request_hash(batch: &Batch) -> Result<String> {
    Ok(sha256(&serde_json::to_vec(batch)?))
}

impl State {
    fn apply(&self, batch: &Batch) -> Result<(Self, Receipt)> {
        require(!batch.operation_id.is_empty(), "empty operation ID")?;
        require(
            !batch.mutations.is_empty() || !batch.spaces.is_empty(),
            "empty batch",
        )?;
        let digest = request_hash(batch)?;
        if let Some(receipt) = self.receipts.get(&batch.operation_id) {
            if receipt.request_sha256 != digest {
                return Err(Error::RetryConflict);
            }
            return Ok((self.clone(), receipt.clone()));
        }
        let mut next = self.clone();
        for space in &batch.spaces {
            space.validate()?;
            let id = space.id();
            if let Some(existing) = next.spaces.get(&id) {
                require(existing == space, "embedding identity collision")?;
            }
            next.spaces.insert(id, space.clone());
        }
        let mut changed = BTreeSet::new();
        for mutation in &batch.mutations {
            let (id, expected) = match mutation {
                Mutation::Replace {
                    document,
                    expected_revision,
                } => (&document.document_id, expected_revision.as_deref()),
                Mutation::Delete {
                    document_id,
                    expected_revision,
                } => (document_id, Some(expected_revision.as_str())),
            };
            require(
                !id.is_empty() && changed.insert(id),
                "empty or duplicate document in batch",
            )?;
            if self.documents.get(id).map(|d| d.revision.as_str()) != expected {
                return Err(Error::Conflict(id.clone()));
            }
            match mutation {
                Mutation::Replace { document, .. } => {
                    document.validate(&next.spaces)?;
                    let revisions = next.revisions.entry(id.clone()).or_default();
                    require(
                        revisions.insert(document.revision.clone()),
                        "document revision ID was already used",
                    )?;
                    next.documents
                        .insert(id.clone(), Arc::new(document.as_ref().clone()));
                }
                Mutation::Delete { .. } => {
                    next.documents.remove(id);
                }
            }
        }
        next.generation = self
            .generation
            .checked_add(1)
            .ok_or_else(|| Error::Invalid("generation overflow".into()))?;
        let receipt = Receipt {
            generation: next.generation,
            request_sha256: digest,
        };
        next.receipts
            .insert(batch.operation_id.clone(), receipt.clone());
        Ok((next, receipt))
    }

    fn validate(&self, blobs: &LocalBlobStore) -> Result<()> {
        for (id, space) in &self.spaces {
            space.validate()?;
            require(*id == space.id(), "space identity mismatch")?;
        }
        require(
            self.receipts.len() as u64 == self.generation,
            "receipt/generation count mismatch",
        )?;
        let generations: BTreeSet<_> = self.receipts.values().map(|r| r.generation).collect();
        require(
            generations.len() == self.receipts.len()
                && generations.iter().copied().eq(1..=self.generation),
            "invalid receipt generations",
        )?;
        for (id, receipt) in &self.receipts {
            require(
                !id.is_empty() && hash_valid(&receipt.request_sha256),
                "invalid receipt",
            )?;
        }
        for (id, document) in &self.documents {
            require(
                id == &document.document_id
                    && self
                        .revisions
                        .get(id)
                        .is_some_and(|r| r.contains(&document.revision)),
                "document revision history mismatch",
            )?;
            document.validate(&self.spaces)?;
            blobs.get(&document.original)?;
        }
        Ok(())
    }
}

fn prefix_hash(file: &mut File, length: u64) -> Result<String> {
    require(
        file.metadata()?.len() >= length,
        "journal shorter than checkpoint",
    )?;
    file.seek(SeekFrom::Start(0))?;
    let mut hash = Sha256::new();
    let mut reader = file.take(length);
    let mut buffer = [0_u8; 64 * 1024];
    loop {
        let count = reader.read(&mut buffer)?;
        if count == 0 {
            break;
        }
        hash.update(&buffer[..count]);
    }
    Ok(format!("{:x}", hash.finalize()))
}

impl Database {
    pub fn open(path: impl AsRef<Path>) -> Result<Self> {
        if !cfg!(target_os = "linux") {
            return Err(Error::UnsupportedPlatform);
        }
        let root = std::path::absolute(path)?;
        ensure_dir(&root)?;
        if let Some(parent) = root.parent() {
            sync_dir(parent)?;
        }
        let lock = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .open(root.join("writer.lock"))?;
        lock.try_lock_exclusive().map_err(|e| {
            if e.kind() == std::io::ErrorKind::WouldBlock {
                Error::Locked
            } else {
                e.into()
            }
        })?;
        let lock = WriterLock(lock);
        let manifest = root.join("FORMAT");
        if manifest.exists() {
            if fs::read(&manifest)? != b"VNXSTORE1\n" || !root.join("journal.bin").is_file() {
                return Err(Error::Corrupt("invalid format or missing journal".into()));
            }
        } else if root.join("snapshot.bin").exists()
            || fs::metadata(root.join("journal.bin")).is_ok_and(|m| m.len() > 0)
        {
            return Err(Error::Corrupt("missing storage format marker".into()));
        }
        let blobs = LocalBlobStore::new(root.join("blobs"))?;
        let mut journal = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .open(root.join("journal.bin"))?;
        journal.sync_all()?;
        sync_dir(&root)?;
        if !manifest.exists() {
            let mut file = OpenOptions::new()
                .create_new(true)
                .write(true)
                .open(&manifest)?;
            file.write_all(b"VNXSTORE1\n")?;
            file.sync_all()?;
            sync_dir(&root)?;
        }
        let mut state = State::default();
        let mut offset = 0;
        let checkpoint_path = root.join("snapshot.bin");
        if checkpoint_path.exists() {
            let mut file = File::open(checkpoint_path)?;
            let checkpoint = checkpoint::read(&mut file)?;
            if prefix_hash(&mut journal, checkpoint.journal_offset)? != checkpoint.journal_sha256 {
                return Err(Error::Corrupt("checkpoint journal prefix mismatch".into()));
            }
            offset = checkpoint.journal_offset;
            state = checkpoint.state;
        }
        journal.seek(SeekFrom::Start(offset))?;
        loop {
            let payload = match frame::read(&mut journal)? {
                ReadFrame::End | ReadFrame::Incomplete => break,
                ReadFrame::Complete {
                    kind: frame::PREPARE,
                    payload,
                } => payload,
                _ => return Err(Error::Corrupt("expected prepare".into())),
            };
            let prepared: Prepared = serde_json::from_slice(&payload)?;
            let commit = match frame::read(&mut journal)? {
                ReadFrame::End | ReadFrame::Incomplete => break,
                ReadFrame::Complete {
                    kind: frame::COMMIT,
                    payload,
                } => serde_json::from_slice::<Commit>(&payload)?,
                _ => return Err(Error::Corrupt("expected commit".into())),
            };
            if commit.generation != prepared.generation
                || commit.prepare_sha256 != sha256(&payload)
                || state.generation.checked_add(1) != Some(prepared.generation)
                || state.receipts.contains_key(&prepared.batch.operation_id)
            {
                return Err(Error::Corrupt(
                    "commit/prepare sequence or digest mismatch".into(),
                ));
            }
            state = state.apply(&prepared.batch)?.0;
            offset = journal.stream_position()?;
        }
        // Validate before repairing: do not modify a store whose committed data is invalid.
        state.validate(&blobs)?;
        if journal.metadata()?.len() != offset {
            journal.set_len(offset)?;
            journal.sync_all()?;
        }
        journal.seek(SeekFrom::Start(offset))?;
        let database = Self {
            root,
            _lock: lock,
            journal,
            blobs,
            state: Arc::new(state),
            committed_offset: offset,
            poisoned: false,
            #[cfg(test)]
            fail_at: None,
            #[cfg(test)]
            job_fail_at: None,
        };
        database.validate_jobs()?;
        Ok(database)
    }

    pub fn snapshot(&self) -> ReadSnapshot {
        ReadSnapshot(self.state.clone())
    }
    pub fn originals(&self) -> &dyn BlobStore {
        &self.blobs
    }
    pub fn put_original(&mut self, bytes: &[u8]) -> Result<BlobRef> {
        self.writable()?;
        self.blobs.put(bytes)
    }
    pub(crate) fn writable(&self) -> Result<()> {
        if self.poisoned {
            Err(Error::Poisoned)
        } else {
            Ok(())
        }
    }
    fn fault(&self, point: Fault) -> Result<()> {
        #[cfg(test)]
        if self.fail_at == Some(point) {
            return Err(std::io::Error::other(format!("injected {point:?}")).into());
        }
        let _ = point;
        Ok(())
    }

    pub fn commit(&mut self, batch: Batch) -> Result<Receipt> {
        self.writable()?;
        let digest = request_hash(&batch)?;
        if let Some(receipt) = self.state.receipts.get(&batch.operation_id) {
            return if receipt.request_sha256 == digest {
                Ok(receipt.clone())
            } else {
                Err(Error::RetryConflict)
            };
        }
        let (next, receipt) = self.state.apply(&batch)?;
        for mutation in &batch.mutations {
            if let Mutation::Replace { document, .. } = mutation {
                self.blobs.get(&document.original)?;
            }
        }
        let payload = serde_json::to_vec(&Prepared {
            generation: receipt.generation,
            batch,
        })?;
        let prepare = frame::encode(frame::PREPARE, &payload)?;
        let commit = frame::encode(
            frame::COMMIT,
            &serde_json::to_vec(&Commit {
                generation: receipt.generation,
                prepare_sha256: sha256(&payload),
            })?,
        )?;
        let write_result = (|| -> Result<()> {
            self.journal.write_all(&prepare)?;
            self.fault(Fault::PrepareWrite)?;
            self.journal.sync_all()?;
            self.fault(Fault::PrepareSync)?;
            self.journal.write_all(&commit)?;
            self.fault(Fault::CommitWrite)?;
            self.journal.sync_all()?;
            self.fault(Fault::CommitSync)?;
            Ok(())
        })();
        if let Err(error) = write_result {
            self.poisoned = true;
            return Err(error);
        }
        self.committed_offset += (prepare.len() + commit.len()) as u64;
        self.state = Arc::new(next);
        Ok(receipt)
    }

    pub fn checkpoint(&mut self) -> Result<u64> {
        self.writable()?;
        let result = (|| -> Result<()> {
            let journal_sha256 = prefix_hash(&mut self.journal, self.committed_offset)?;
            let pending = self.root.join("snapshot.pending");
            let mut file = OpenOptions::new()
                .create(true)
                .truncate(true)
                .write(true)
                .open(&pending)?;
            checkpoint::write(
                &mut file,
                self.committed_offset,
                &journal_sha256,
                &self.state,
                || self.fault(Fault::SnapshotChunk),
            )?;
            self.fault(Fault::SnapshotWrite)?;
            file.sync_all()?;
            self.fault(Fault::SnapshotSync)?;
            drop(file);
            fs::rename(pending, self.root.join("snapshot.bin"))?;
            self.fault(Fault::SnapshotRename)?;
            sync_dir(&self.root)?;
            self.fault(Fault::SnapshotDirSync)?;
            Ok(())
        })();
        if let Err(error) = result {
            self.poisoned = true;
            return Err(error);
        }
        Ok(self.state.generation)
    }
}

#[cfg(all(test, target_os = "linux"))]
mod tests;
