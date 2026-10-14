use crate::{
    Error, Result,
    contracts::{BlobRef, hash_valid},
    require, sha256,
};
use std::{
    fs::{self, File, OpenOptions},
    io::Write,
    path::{Path, PathBuf},
};

/// Boundary for original-byte storage. Implementations must make successful puts durable.
pub trait BlobStore {
    fn put(&mut self, bytes: &[u8]) -> Result<BlobRef>;
    fn get(&self, reference: &BlobRef) -> Result<Vec<u8>>;
}

pub struct LocalBlobStore {
    root: PathBuf,
}

pub(crate) fn sync_dir(path: &Path) -> Result<()> {
    File::open(path)?.sync_all()?;
    Ok(())
}

pub(crate) fn ensure_dir(path: &Path) -> Result<()> {
    if path.is_dir() {
        return Ok(());
    }
    if let Some(parent) = path.parent().filter(|p| !p.as_os_str().is_empty()) {
        ensure_dir(parent)?;
    }
    match fs::create_dir(path) {
        Ok(()) => (),
        Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists && path.is_dir() => (),
        Err(e) => return Err(e.into()),
    }
    sync_dir(path)?;
    sync_dir(path.parent().unwrap_or_else(|| Path::new(".")))
}

impl LocalBlobStore {
    pub(crate) fn new(root: PathBuf) -> Result<Self> {
        ensure_dir(&root)?;
        Ok(Self { root })
    }
}

impl BlobStore for LocalBlobStore {
    fn put(&mut self, bytes: &[u8]) -> Result<BlobRef> {
        let reference = BlobRef {
            sha256: sha256(bytes),
            bytes: bytes.len() as u64,
        };
        let destination = self.root.join(&reference.sha256);
        if destination.exists() {
            self.get(&reference)?;
            File::open(&destination)?.sync_all()?;
            sync_dir(&self.root)?;
            return Ok(reference);
        }
        // Only the locked database writer can construct this store and call put.
        let pending = self.root.join("original.pending");
        let mut file = OpenOptions::new()
            .create(true)
            .truncate(true)
            .write(true)
            .open(&pending)?;
        file.write_all(bytes)?;
        file.sync_all()?;
        drop(file);
        fs::rename(&pending, destination)?;
        sync_dir(&self.root)?;
        Ok(reference)
    }

    fn get(&self, reference: &BlobRef) -> Result<Vec<u8>> {
        require(hash_valid(&reference.sha256), "invalid original hash")?;
        let bytes = fs::read(self.root.join(&reference.sha256))?;
        if bytes.len() as u64 != reference.bytes || sha256(&bytes) != reference.sha256 {
            return Err(Error::Corrupt("original size/hash mismatch".into()));
        }
        Ok(bytes)
    }
}
