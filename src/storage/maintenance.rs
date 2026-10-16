//! Explicit offline compaction. No history expiry and no in-place journal rotation.
use super::{Database, checkpoint};
use crate::{Error, Result, blob::sync_dir, contracts::hash_valid, require, sha256};
use serde::Serialize;
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs::{self, File, OpenOptions},
    io::{Read, Write},
    path::{Path, PathBuf},
    time::{SystemTime, UNIX_EPOCH},
};

const RESERVE_BYTES: u64 = 64 * 1024 * 1024;

#[derive(Clone, Debug, Serialize, PartialEq, Eq)]
pub struct FileSummary {
    pub files: usize,
    pub bytes: u64,
}

#[derive(Clone, Debug, Serialize)]
pub struct Report {
    pub policy: &'static str,
    pub status: String,
    pub database: PathBuf,
    pub generation: u64,
    pub documents: usize,
    pub retained_receipts: usize,
    pub retained_revision_ids: usize,
    pub retained_ingestion_jobs: FileSummary,
    pub document_blobs: FileSummary,
    pub history_only_blobs: FileSummary,
    pub unreferenced_blobs: FileSummary,
    pub journal_bytes: u64,
    pub uncommitted_tail_bytes: u64,
    pub old_checkpoint_bytes: u64,
    pub disposable_pending_bytes: u64,
    pub store_bytes_before: u64,
    pub replacement_bytes: u64,
    pub estimated_reclaimed_bytes: u64,
    pub estimated_growth_bytes: u64,
    pub temporary_bytes_required: u64,
    pub available_bytes: u64,
    pub enough_space: bool,
    pub actual_reclaimed_bytes: Option<u64>,
    pub leftover_workspaces: Vec<PathBuf>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct Entry {
    bytes: u64,
    hash: String,
}

#[derive(Default)]
struct Measure {
    bytes: u64,
    hash: Sha256,
}
impl Write for Measure {
    fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
        self.bytes = self
            .bytes
            .checked_add(bytes.len() as u64)
            .ok_or_else(|| std::io::Error::other("maintenance size overflow"))?;
        self.hash.update(bytes);
        Ok(bytes.len())
    }
    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}
impl Measure {
    fn entry(self) -> Entry {
        Entry {
            bytes: self.bytes,
            hash: format!("{:x}", self.hash.finalize()),
        }
    }
}

fn measure_file(path: &Path) -> Result<Entry> {
    require(
        fs::symlink_metadata(path)?.is_file(),
        "maintenance requires regular files",
    )?;
    let mut input = File::open(path)?;
    let mut measure = Measure::default();
    std::io::copy(&mut input, &mut measure)?;
    Ok(measure.entry())
}

// Do not follow symlinked roots, parents, namespaces or files. Unknown entries
// are not garbage: reject the operation instead of discarding them.
fn root_path(path: &Path) -> Result<PathBuf> {
    if !cfg!(target_os = "linux") {
        return Err(Error::UnsupportedPlatform);
    }
    let absolute = std::path::absolute(path)?;
    for ancestor in absolute.ancestors() {
        require(
            fs::symlink_metadata(ancestor)?.is_dir(),
            "maintenance path must contain only real directories",
        )?;
    }
    let root = absolute.canonicalize()?;
    require(
        root.parent().is_some() && root.file_name().is_some(),
        "cannot compact a filesystem root",
    )?;
    Ok(root)
}

fn layout(root: &Path) -> Result<BTreeSet<String>> {
    let mut files = BTreeSet::new();
    for entry in fs::read_dir(root)? {
        let entry = entry?;
        let name = entry
            .file_name()
            .into_string()
            .map_err(|_| Error::Invalid("invalid store filename".into()))?;
        let kind = entry.file_type()?;
        if matches!(name.as_str(), "blobs" | "jobs") && kind.is_dir() {
            for child in fs::read_dir(entry.path())? {
                let child = child?;
                let leaf = child
                    .file_name()
                    .into_string()
                    .map_err(|_| Error::Invalid("invalid store filename".into()))?;
                let allowed = match name.as_str() {
                    "blobs" => hash_valid(&leaf) || leaf == "original.pending",
                    _ => {
                        leaf.strip_suffix(".job").is_some_and(hash_valid) || leaf == "stage.pending"
                    }
                };
                require(
                    allowed && child.file_type()?.is_file(),
                    "unexpected maintenance store entry",
                )?;
                files.insert(format!("{name}/{leaf}"));
            }
        } else {
            require(
                kind.is_file()
                    && matches!(
                        name.as_str(),
                        "FORMAT"
                            | "writer.lock"
                            | "journal.bin"
                            | "snapshot.bin"
                            | "snapshot.pending"
                    ),
                "unexpected maintenance store entry",
            )?;
            files.insert(name);
        }
    }
    require(
        ["FORMAT", "writer.lock", "journal.bin"]
            .iter()
            .all(|n| files.contains(*n))
            && fs::symlink_metadata(root.join("blobs"))?.is_dir(),
        "maintenance requires an initialized database",
    )?;
    Ok(files)
}

fn inventory(root: &Path) -> Result<BTreeMap<String, Entry>> {
    layout(root)?
        .into_iter()
        .map(|name| {
            let info = measure_file(&root.join(&name))?;
            if let Some(hash) = name.strip_prefix("blobs/").filter(|h| hash_valid(h)) {
                require(info.hash == hash, "blob filename/content hash mismatch")?;
            }
            Ok((name, info))
        })
        .collect()
}

fn sum<'a>(mut entries: impl Iterator<Item = &'a Entry>) -> Result<u64> {
    entries.try_fold(0u64, |total, entry| {
        total
            .checked_add(entry.bytes)
            .ok_or_else(|| Error::Invalid("maintenance size overflow".into()))
    })
}
fn summary(files: &BTreeMap<String, Entry>, names: &BTreeSet<String>) -> Result<FileSummary> {
    Ok(FileSummary {
        files: names.len(),
        bytes: sum(names.iter().map(|name| &files[name]))?,
    })
}

// Conservative roots: any stored hash string in current documents or saved job
// data pins a matching blob. This includes PDF artifact/configuration hashes,
// and permits arbitrary processing metadata without deleting its artifacts.
fn hashes(value: &Value, result: &mut BTreeSet<String>) {
    match value {
        Value::String(s) if hash_valid(s) => {
            result.insert(format!("blobs/{s}"));
        }
        Value::Array(values) => {
            for v in values {
                hashes(v, result);
            }
        }
        Value::Object(values) => {
            for (key, v) in values {
                if hash_valid(key) {
                    result.insert(format!("blobs/{key}"));
                }
                hashes(v, result);
            }
        }
        _ => (),
    }
}

fn workspace_prefix(root: &Path) -> String {
    format!(
        ".vnx-compact-{}-",
        &sha256(root.as_os_str().as_encoded_bytes())[..16]
    )
}

struct Plan {
    report: Report,
    files: BTreeMap<String, Entry>,
    retained: BTreeSet<String>,
    checkpoint: Entry,
}
fn plan(db: &Database) -> Result<Plan> {
    let files = inventory(&db.root)?;
    let mut document_roots = BTreeSet::new();
    for document in db.snapshot().documents() {
        hashes(&serde_json::to_value(document)?, &mut document_roots);
    }
    document_roots.retain(|name| files.contains_key(name));
    let mut roots = document_roots.clone();
    for job in db.ingestion_jobs()? {
        hashes(&serde_json::to_value(job)?, &mut roots);
    }
    roots.retain(|name| files.contains_key(name));
    let history: BTreeSet<_> = roots.difference(&document_roots).cloned().collect();
    let garbage: BTreeSet<_> = files
        .keys()
        .filter(|name| {
            name.strip_prefix("blobs/").is_some_and(hash_valid) && !roots.contains(*name)
        })
        .cloned()
        .collect();
    let jobs: BTreeSet<_> = files
        .keys()
        .filter(|name| name.starts_with("jobs/") && name.ends_with(".job"))
        .cloned()
        .collect();
    let mut retained = roots;
    retained.extend(jobs.iter().cloned());
    retained.insert("FORMAT".into());
    let mut measured = Measure::default();
    checkpoint::write(&mut measured, 0, &sha256(b""), &db.state, || Ok(()))?;
    let checkpoint = measured.entry();
    let replacement_bytes = sum(retained.iter().map(|n| &files[n]))?
        .checked_add(checkpoint.bytes)
        .and_then(|n| n.checked_add(files["writer.lock"].bytes))
        .ok_or_else(|| Error::Invalid("maintenance size overflow".into()))?;
    let before = sum(files.values())?;
    let temporary = replacement_bytes
        .checked_add(RESERVE_BYTES)
        .ok_or_else(|| Error::Invalid("maintenance size overflow".into()))?;
    let parent = db.root.parent().unwrap();
    let available = available_bytes(parent)?;
    let prefix = workspace_prefix(&db.root);
    let mut leftovers = vec![];
    for entry in fs::read_dir(parent)? {
        let entry = entry?;
        if entry.file_name().to_string_lossy().starts_with(&prefix) {
            leftovers.push(entry.path());
        }
    }
    leftovers.sort();
    let size = |name: &str| files.get(name).map_or(0, |e| e.bytes);
    let report = Report {
        policy: "preserve-history-v1",
        status: "dry_run".into(),
        database: db.root.clone(),
        generation: db.state.generation,
        documents: db.state.documents.len(),
        retained_receipts: db.state.receipts.len(),
        retained_revision_ids: db.state.revisions.values().map(BTreeSet::len).sum(),
        retained_ingestion_jobs: summary(&files, &jobs)?,
        document_blobs: summary(&files, &document_roots)?,
        history_only_blobs: summary(&files, &history)?,
        unreferenced_blobs: summary(&files, &garbage)?,
        journal_bytes: size("journal.bin"),
        uncommitted_tail_bytes: size("journal.bin").saturating_sub(db.committed_offset),
        old_checkpoint_bytes: size("snapshot.bin"),
        disposable_pending_bytes: size("snapshot.pending")
            + size("blobs/original.pending")
            + size("jobs/stage.pending"),
        store_bytes_before: before,
        replacement_bytes,
        estimated_reclaimed_bytes: before.saturating_sub(replacement_bytes),
        estimated_growth_bytes: replacement_bytes.saturating_sub(before),
        temporary_bytes_required: temporary,
        available_bytes: available,
        enough_space: available >= temporary,
        actual_reclaimed_bytes: None,
        leftover_workspaces: leftovers,
    };
    Ok(Plan {
        report,
        files,
        retained,
        checkpoint,
    })
}

fn open(path: &Path) -> Result<Database> {
    let root = root_path(path)?;
    // Check the shape before normal recovery can follow any files. Repeat the
    // authoritative inventory after locking; a concurrent writer fails admission.
    layout(&root)?;
    Database::open_mode(&root, true)
}

/// Read-only accounting, including validation, under exclusive writer ownership.
pub fn inspect(path: &Path) -> Result<Report> {
    plan(&open(path)?).map(|p| p.report)
}

/// Compact only after explicit offline admission. Never expire retry/history data.
pub fn compact(path: &Path) -> Result<Report> {
    compact_with(path, |_| Ok(()))
}

fn copy(from: &Path, to: &Path, expected: &Entry) -> Result<()> {
    let mut input = File::open(from)?;
    let mut output = OpenOptions::new().create_new(true).write(true).open(to)?;
    let mut measure = Measure::default();
    let mut buffer = [0u8; 65536];
    loop {
        let n = input.read(&mut buffer)?;
        if n == 0 {
            break;
        }
        output.write_all(&buffer[..n])?;
        measure.write_all(&buffer[..n])?;
    }
    require(
        measure.entry() == *expected,
        "maintenance copy changed size/hash",
    )?;
    output.sync_all()?;
    Ok(())
}

fn compact_with(path: &Path, mut boundary: impl FnMut(&str) -> Result<()>) -> Result<Report> {
    let db = open(path)?;
    let mut p = plan(&db)?;
    require(
        p.report.enough_space,
        "insufficient free space for compacted copy plus 64 MiB reserve",
    )?;
    boundary("preflight")?;
    let parent = db.root.parent().unwrap();
    let stamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|_| Error::Invalid("invalid system clock".into()))?
        .as_nanos();
    let staging = parent.join(format!(
        "{}{}-{stamp}",
        workspace_prefix(&db.root),
        std::process::id()
    ));
    fs::create_dir(&staging)?;
    let mut published = false;
    let result = (|| -> Result<()> {
        fs::create_dir(staging.join("blobs"))?;
        fs::create_dir(staging.join("jobs"))?;
        sync_dir(parent)?;
        boundary("staging")?;
        for name in &p.retained {
            copy(&db.root.join(name), &staging.join(name), &p.files[name])?;
            boundary("copy")?;
        }
        let mut journal = OpenOptions::new()
            .create_new(true)
            .write(true)
            .open(staging.join("journal.bin"))?;
        journal.flush()?;
        journal.sync_all()?;
        let mut snapshot = OpenOptions::new()
            .create_new(true)
            .write(true)
            .open(staging.join("snapshot.bin"))?;
        checkpoint::write(&mut snapshot, 0, &sha256(b""), &db.state, || {
            boundary("checkpoint_segment")
        })?;
        boundary("checkpoint_write")?;
        snapshot.sync_all()?;
        drop(snapshot);
        boundary("checkpoint_sync")?;
        require(
            measure_file(&staging.join("snapshot.bin"))? == p.checkpoint,
            "replacement checkpoint hash mismatch",
        )?;
        // Reopen with the real recovery/validation path before publication.
        {
            let replacement = Database::open(&staging)?;
            let mut measured = Measure::default();
            checkpoint::write(
                &mut measured,
                0,
                &sha256(b""),
                &replacement.state,
                || Ok(()),
            )?;
            require(
                measured.entry() == p.checkpoint
                    && replacement.ingestion_jobs()?.len()
                        == p.report.retained_ingestion_jobs.files,
                "replacement logical state differs",
            )?;
        }
        boundary("verified")?;
        // Only the candidate's private, released lock is unlinked. The source
        // inode stays locked and is hard-linked into the replacement, closing
        // the open-old-lock / exchange / acquire-lock race across processes.
        fs::remove_file(staging.join("writer.lock"))?;
        fs::hard_link(db.root.join("writer.lock"), staging.join("writer.lock"))?;
        sync_dir(&staging.join("blobs"))?;
        sync_dir(&staging.join("jobs"))?;
        sync_dir(&staging)?;
        sync_dir(parent)?;
        boundary("before_exchange")?;
        exchange(&db.root, &staging)?;
        published = true;
        boundary("after_exchange")?;
        sync_dir(parent)?;
        boundary("published_sync")?;
        // Check the full displaced file set before unlinking anything. Unknown
        // files, symlinks or an externally modified old store fail closed.
        require(
            inventory(&staging)? == p.files,
            "displaced store changed; retained for inspection",
        )?;
        boundary("before_cleanup")?;
        for name in p.files.keys() {
            fs::remove_file(staging.join(name))?;
            boundary("cleanup_file")?;
        }
        for name in ["blobs", "jobs"] {
            let directory = staging.join(name);
            if directory.exists() {
                fs::remove_dir(&directory)?;
            }
        }
        fs::remove_dir(&staging)?;
        sync_dir(parent)?;
        boundary("cleanup_sync")?;
        Ok(())
    })();
    match result {
        Ok(()) => {
            p.report.status = "compacted".into();
            p.report.actual_reclaimed_bytes = Some(p.report.estimated_reclaimed_bytes);
            Ok(p.report)
        }
        Err(error) => {
            // No speculative cleanup on failure, especially after an uncertain
            // exchange sync. Both full stores (or a partial candidate) stay put.
            Err(Error::Invalid(format!(
                "offline compaction failed (directory exchanged: {published}); inspect {} and workspace location {} before retrying: {error}",
                db.root.display(),
                staging.display()
            )))
        }
    }
}

#[cfg(target_os = "linux")]
fn exchange(a: &Path, b: &Path) -> Result<()> {
    use std::os::unix::ffi::OsStrExt;
    let a = std::ffi::CString::new(a.as_os_str().as_bytes())
        .map_err(|_| Error::Invalid("invalid path".into()))?;
    let b = std::ffi::CString::new(b.as_os_str().as_bytes())
        .map_err(|_| Error::Invalid("invalid path".into()))?;
    // Paths are valid C strings on one filesystem; exchange is a single atomic
    // namespace operation. Do not fall back to sequential directory renames.
    let result = unsafe {
        libc::renameat2(
            libc::AT_FDCWD,
            a.as_ptr(),
            libc::AT_FDCWD,
            b.as_ptr(),
            libc::RENAME_EXCHANGE,
        )
    };
    if result == -1 {
        return Err(std::io::Error::last_os_error().into());
    }
    Ok(())
}
#[cfg(target_os = "linux")]
fn available_bytes(path: &Path) -> Result<u64> {
    use std::os::unix::ffi::OsStrExt;
    let path = std::ffi::CString::new(path.as_os_str().as_bytes())
        .map_err(|_| Error::Invalid("invalid path".into()))?;
    let mut stat = std::mem::MaybeUninit::<libc::statvfs>::uninit();
    // stat points at writable storage and is read only after a successful call.
    if unsafe { libc::statvfs(path.as_ptr(), stat.as_mut_ptr()) } != 0 {
        return Err(std::io::Error::last_os_error().into());
    }
    let stat = unsafe { stat.assume_init() };
    stat.f_bavail
        .checked_mul(stat.f_frsize)
        .ok_or_else(|| Error::Invalid("filesystem capacity overflow".into()))
}
#[cfg(not(target_os = "linux"))]
fn exchange(_: &Path, _: &Path) -> Result<()> {
    Err(Error::UnsupportedPlatform)
}
#[cfg(not(target_os = "linux"))]
fn available_bytes(_: &Path) -> Result<u64> {
    Err(Error::UnsupportedPlatform)
}

#[cfg(all(test, target_os = "linux"))]
mod tests;
