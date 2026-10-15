use crate::{Error, Result};
use std::io::Read;

pub(crate) const HEADER: usize = 24;
pub(crate) const MAX_PAYLOAD: u64 = 64 * 1024 * 1024;
pub(crate) const PREPARE: u16 = 1;
pub(crate) const COMMIT: u16 = 2;
pub(crate) const SNAPSHOT: u16 = 3;
pub(crate) const JOB: u16 = 4;
pub(crate) const SNAPSHOT_HEADER: u16 = 5;
pub(crate) const SNAPSHOT_DATA: u16 = 6;
pub(crate) const SNAPSHOT_END: u16 = 7;

pub(crate) enum ReadFrame {
    Complete { kind: u16, payload: Vec<u8> },
    End,
    Incomplete,
}

pub(crate) fn encode(kind: u16, payload: &[u8]) -> Result<Vec<u8>> {
    crate::require(
        payload.len() as u64 <= MAX_PAYLOAD,
        "frame exceeds 64 MiB limit",
    )?;
    let mut bytes = Vec::with_capacity(HEADER + payload.len() + 4);
    bytes.extend_from_slice(b"VNXFRAME");
    bytes.extend_from_slice(&1_u16.to_le_bytes());
    bytes.extend_from_slice(&kind.to_le_bytes());
    bytes.extend_from_slice(&(payload.len() as u64).to_le_bytes());
    bytes.extend_from_slice(&crc32fast::hash(&bytes).to_le_bytes());
    bytes.extend_from_slice(payload);
    bytes.extend_from_slice(&crc32fast::hash(&bytes).to_le_bytes());
    Ok(bytes)
}

fn read_fully(input: &mut impl Read, bytes: &mut [u8]) -> std::io::Result<usize> {
    let mut count = 0;
    while count < bytes.len() {
        match input.read(&mut bytes[count..]) {
            Ok(0) => break,
            Ok(n) => count += n,
            Err(e) if e.kind() == std::io::ErrorKind::Interrupted => continue,
            Err(e) => return Err(e),
        }
    }
    Ok(count)
}

pub(crate) fn read(input: &mut impl Read) -> Result<ReadFrame> {
    read_bounded(input, |_| MAX_PAYLOAD)
}

/// Apply a stream-specific bound before allocating an untrusted payload.
pub(crate) fn read_bounded(
    input: &mut impl Read,
    limit: impl FnOnce(u16) -> u64,
) -> Result<ReadFrame> {
    let mut header = [0_u8; HEADER];
    let count = read_fully(input, &mut header)?;
    if count == 0 {
        return Ok(ReadFrame::End);
    }
    if count < HEADER {
        return Ok(ReadFrame::Incomplete);
    }
    if &header[..8] != b"VNXFRAME"
        || header[8..10] != 1_u16.to_le_bytes()
        || crc32fast::hash(&header[..20]) != u32::from_le_bytes(header[20..24].try_into().unwrap())
    {
        return Err(Error::Corrupt("frame header/version/checksum".into()));
    }
    let kind = u16::from_le_bytes(header[10..12].try_into().unwrap());
    if !(PREPARE..=SNAPSHOT_END).contains(&kind) {
        return Err(Error::Corrupt("unknown frame kind".into()));
    }
    let len = u64::from_le_bytes(header[12..20].try_into().unwrap());
    if len > MAX_PAYLOAD.min(limit(kind)) {
        return Err(Error::Corrupt("oversized frame".into()));
    }
    let mut payload = vec![0_u8; len as usize];
    if read_fully(input, &mut payload)? < payload.len() {
        return Ok(ReadFrame::Incomplete);
    }
    let mut checksum = [0_u8; 4];
    if read_fully(input, &mut checksum)? < 4 {
        return Ok(ReadFrame::Incomplete);
    }
    let mut hash = crc32fast::Hasher::new();
    hash.update(&header);
    hash.update(&payload);
    if hash.finalize() != u32::from_le_bytes(checksum) {
        return Err(Error::Corrupt("frame payload checksum".into()));
    }
    Ok(ReadFrame::Complete { kind, payload })
}
