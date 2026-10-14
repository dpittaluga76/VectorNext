//! Offline, lock-protected exports; verified restoration only into a new destination.
use crate::{Database, Error, Result, blob::sync_dir, contracts::hash_valid, require};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeMap,
    fs::{self, File, OpenOptions},
    io::{Read, Write},
    path::{Path, PathBuf},
};

const MAX_TOTAL: u64 = 8 * 1024 * 1024 * 1024;
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Entry {
    pub bytes: u64,
    pub sha256: String,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Manifest {
    pub format: u32,
    pub generation: u64,
    pub jobs: usize,
    pub files: BTreeMap<String, Entry>,
}
fn allowed(name: &str) -> bool {
    matches!(name, "FORMAT" | "journal.bin" | "snapshot.bin")
        || name.strip_prefix("blobs/").is_some_and(hash_valid)
        || name
            .strip_prefix("jobs/")
            .and_then(|s| s.strip_suffix(".job"))
            .is_some_and(hash_valid)
}
fn files(root: &Path, exported: bool) -> Result<Vec<String>> {
    let mut result = vec![];
    for entry in fs::read_dir(root)? {
        let entry = entry?;
        let name = entry
            .file_name()
            .into_string()
            .map_err(|_| Error::Invalid("invalid store filename".into()))?;
        let kind = entry.file_type()?;
        require(!kind.is_symlink(), "store contains a symlink")?;
        if exported && name == "backup.json" {
            require(kind.is_file(), "backup manifest is not a regular file")?;
            continue;
        }
        if !exported && (name == "writer.lock" || matches!(name.as_str(), "snapshot.pending")) {
            continue;
        }
        if matches!(name.as_str(), "blobs" | "jobs") && kind.is_dir() {
            for child in fs::read_dir(entry.path())? {
                let child = child?;
                let leaf = child
                    .file_name()
                    .into_string()
                    .map_err(|_| Error::Invalid("invalid store filename".into()))?;
                require(child.file_type()?.is_file(), "store contains a non-file")?;
                if !exported
                    && matches!(
                        (name.as_str(), leaf.as_str()),
                        ("blobs", "original.pending") | ("jobs", "stage.pending")
                    )
                {
                    continue;
                }
                let path = format!("{name}/{leaf}");
                require(allowed(&path), "unexpected store file")?;
                result.push(path);
            }
        } else {
            require(kind.is_file() && allowed(&name), "unexpected store entry")?;
            result.push(name);
        }
    }
    require(result.len() <= 100_000, "too many backup files")?;
    result.sort();
    Ok(result)
}
fn copy_checked(from: &Path, to: &Path, expected: Option<&Entry>) -> Result<Entry> {
    require(
        fs::symlink_metadata(from)?.is_file(),
        "backup source must be a regular file",
    )?;
    let mut input = File::open(from)?;
    let mut output = OpenOptions::new().create_new(true).write(true).open(to)?;
    let mut hash = Sha256::new();
    let mut buffer = [0u8; 65536];
    let mut bytes = 0u64;
    loop {
        let count = input.read(&mut buffer)?;
        if count == 0 {
            break;
        }
        bytes += count as u64;
        require(
            bytes <= MAX_TOTAL && expected.is_none_or(|e| bytes <= e.bytes),
            "backup file exceeds size limit",
        )?;
        output.write_all(&buffer[..count])?;
        hash.update(&buffer[..count]);
    }
    let result = Entry {
        bytes,
        sha256: format!("{:x}", hash.finalize()),
    };
    require(
        expected.is_none_or(|e| e.bytes == result.bytes && e.sha256 == result.sha256),
        "backup size/hash mismatch",
    )?;
    output.sync_all()?;
    Ok(result)
}
fn prepare_new(path: &Path) -> Result<()> {
    require(
        !path.exists(),
        "destination already exists; choose a new directory",
    )?;
    fs::create_dir(path)?;
    fs::create_dir(path.join("blobs"))?;
    fs::create_dir(path.join("jobs"))?;
    Ok(())
}
impl Database {
    /// The caller holds the sole writer for the entire checkpoint and copy.
    pub fn export(&mut self, destination: &Path) -> Result<Manifest> {
        let parent = destination.parent().unwrap_or(Path::new("."));
        let resolved = parent.canonicalize()?.join(
            destination
                .file_name()
                .ok_or_else(|| Error::Invalid("invalid export destination".into()))?,
        );
        require(
            !resolved.starts_with(self.root.canonicalize()?),
            "export destination must be outside the database",
        )?;
        self.checkpoint()?;
        let names = files(&self.root, false)?;
        prepare_new(destination)?;
        let mut manifest = Manifest {
            format: 1,
            generation: self.snapshot().generation(),
            jobs: self.ingestion_jobs()?.len(),
            files: BTreeMap::new(),
        };
        let mut total = 0u64;
        for name in names {
            let entry = copy_checked(&self.root.join(&name), &destination.join(&name), None)?;
            total += entry.bytes;
            require(total <= MAX_TOTAL, "backup exceeds 8 GiB limit")?;
            manifest.files.insert(name, entry);
        }
        sync_dir(&destination.join("blobs"))?;
        sync_dir(&destination.join("jobs"))?;
        let mut file = OpenOptions::new()
            .create_new(true)
            .write(true)
            .open(destination.join("backup.json"))?;
        file.write_all(&serde_json::to_vec_pretty(&manifest)?)?;
        file.sync_all()?;
        sync_dir(destination)?;
        sync_dir(destination.parent().unwrap_or(Path::new(".")))?;
        Ok(manifest)
    }
}
pub fn restore(source: &Path, destination: &Path) -> Result<Manifest> {
    if !cfg!(target_os = "linux") {
        return Err(Error::UnsupportedPlatform);
    }
    require(
        !destination.exists(),
        "destination already exists; restore never overwrites",
    )?;
    require(
        fs::symlink_metadata(source)?.is_dir(),
        "backup root must be a directory, not a symlink",
    )?;
    let mut bytes = vec![];
    File::open(source.join("backup.json"))?
        .take(16 * 1024 * 1024 + 1)
        .read_to_end(&mut bytes)?;
    require(bytes.len() <= 16 * 1024 * 1024, "backup manifest too large")?;
    let manifest: Manifest = serde_json::from_slice(&bytes)?;
    require(
        manifest.format == 1 && manifest.files.len() <= 100_000,
        "unsupported backup manifest",
    )?;
    require(
        manifest.files.contains_key("FORMAT") && manifest.files.contains_key("journal.bin"),
        "incomplete backup manifest",
    )?;
    require(
        files(source, true)? == manifest.files.keys().cloned().collect::<Vec<_>>(),
        "backup file set differs from manifest",
    )?;
    let mut total = 0u64;
    for (name, entry) in &manifest.files {
        require(
            allowed(name) && hash_valid(&entry.sha256),
            "invalid backup path/hash",
        )?;
        total = total
            .checked_add(entry.bytes)
            .ok_or_else(|| Error::Invalid("backup size overflow".into()))?;
        require(total <= MAX_TOTAL, "backup exceeds 8 GiB limit")?;
        // Prevent symlinked parent directories as well as symlinked leaf files.
        if let Some(parent) = Path::new(name)
            .parent()
            .filter(|p| !p.as_os_str().is_empty())
        {
            require(
                fs::symlink_metadata(source.join(parent))?.is_dir(),
                "backup parent is not a regular directory",
            )?;
        }
    }
    let parent = destination.parent().unwrap_or(Path::new("."));
    let stamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let staging: PathBuf = parent.join(format!(
        ".vectornext-restore-{}-{stamp}",
        std::process::id()
    ));
    prepare_new(&staging)?;
    let outcome = (|| {
        for (name, entry) in &manifest.files {
            copy_checked(&source.join(name), &staging.join(name), Some(entry))?;
        }
        sync_dir(&staging.join("blobs"))?;
        sync_dir(&staging.join("jobs"))?;
        {
            let db = Database::open(&staging)?;
            require(
                db.snapshot().generation() == manifest.generation
                    && db.ingestion_jobs()?.len() == manifest.jobs,
                "restored state differs from backup manifest",
            )?;
        }
        sync_dir(&staging)?;
        publish_new(&staging, destination)?;
        sync_dir(parent)?;
        Ok(manifest)
    })();
    if outcome.is_err() && staging.exists() {
        let _ = fs::remove_dir_all(&staging);
    }
    outcome
}
#[cfg(target_os = "linux")]
fn publish_new(from: &Path, to: &Path) -> Result<()> {
    use std::os::unix::ffi::OsStrExt;
    let from = std::ffi::CString::new(from.as_os_str().as_bytes())
        .map_err(|_| Error::Invalid("invalid path".into()))?;
    let to = std::ffi::CString::new(to.as_os_str().as_bytes())
        .map_err(|_| Error::Invalid("invalid path".into()))?;
    // Valid NUL-terminated path pointers; RENAME_NOREPLACE closes the destination race.
    let result = unsafe {
        libc::renameat2(
            libc::AT_FDCWD,
            from.as_ptr(),
            libc::AT_FDCWD,
            to.as_ptr(),
            libc::RENAME_NOREPLACE,
        )
    };
    if result != 0 {
        return Err(std::io::Error::last_os_error().into());
    }
    Ok(())
}
#[cfg(not(target_os = "linux"))]
fn publish_new(_: &Path, _: &Path) -> Result<()> {
    Err(Error::UnsupportedPlatform)
}
