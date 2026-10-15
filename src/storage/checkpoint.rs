//! Version-2 checkpoint framing; the journal and serialized state are unchanged.
use super::{Checkpoint, State};
use crate::{
    Error, Result,
    frame::{self, ReadFrame},
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::io::{self, Read, Write};

const SEGMENT_BYTES: usize = 1024 * 1024;
const METADATA_BYTES: u64 = 4096;

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Header {
    version: u32,
    segment_bytes: usize,
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct End {
    segments: u64,
    json_bytes: u64,
    json_sha256: String,
}

#[derive(Serialize)]
struct CheckpointRef<'a> {
    journal_offset: u64,
    journal_sha256: &'a str,
    state: &'a State,
}

fn corrupt(message: &str) -> Error {
    Error::Corrupt(format!("checkpoint: {message}"))
}

fn write_frame(output: &mut impl Write, kind: u16, payload: &[u8]) -> Result<()> {
    output.write_all(&frame::encode(kind, payload)?)?;
    Ok(())
}

struct Segments<'a, W, F> {
    output: &'a mut W,
    buffer: Vec<u8>,
    segments: u64,
    bytes: u64,
    hash: Sha256,
    after_segment: F,
}

impl<W: Write, F: FnMut() -> Result<()>> Segments<'_, W, F> {
    fn emit(&mut self) -> Result<()> {
        if self.buffer.len() == 8 {
            return Ok(());
        }
        self.buffer[..8].copy_from_slice(&self.segments.to_le_bytes());
        write_frame(self.output, frame::SNAPSHOT_DATA, &self.buffer)?;
        self.hash.update(&self.buffer[8..]);
        self.bytes = self
            .bytes
            .checked_add((self.buffer.len() - 8) as u64)
            .ok_or_else(|| corrupt("byte count overflow"))?;
        self.segments = self
            .segments
            .checked_add(1)
            .ok_or_else(|| corrupt("segment count overflow"))?;
        self.buffer.truncate(8);
        (self.after_segment)()
    }

    fn finish(mut self) -> Result<()> {
        self.emit()?;
        let end = End {
            segments: self.segments,
            json_bytes: self.bytes,
            json_sha256: format!("{:x}", self.hash.finalize()),
        };
        write_frame(self.output, frame::SNAPSHOT_END, &serde_json::to_vec(&end)?)
    }
}

impl<W: Write, F: FnMut() -> Result<()>> Write for Segments<'_, W, F> {
    fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
        let count = bytes.len().min(SEGMENT_BYTES + 8 - self.buffer.len());
        self.buffer.extend_from_slice(&bytes[..count]);
        if self.buffer.len() == SEGMENT_BYTES + 8 {
            self.emit().map_err(io::Error::other)?;
        }
        Ok(count)
    }

    fn flush(&mut self) -> io::Result<()> {
        // A flush must not create an intermediate short segment.
        self.output.flush()
    }
}

pub(super) fn write(
    output: &mut impl Write,
    journal_offset: u64,
    journal_sha256: &str,
    state: &State,
    after_segment: impl FnMut() -> Result<()>,
) -> Result<()> {
    let header = Header {
        version: 2,
        segment_bytes: SEGMENT_BYTES,
    };
    write_frame(
        output,
        frame::SNAPSHOT_HEADER,
        &serde_json::to_vec(&header)?,
    )?;
    let mut writer = Segments {
        output,
        buffer: Vec::with_capacity(SEGMENT_BYTES + 8),
        segments: 0,
        bytes: 0,
        hash: Sha256::new(),
        after_segment,
    };
    writer.buffer.extend_from_slice(&0_u64.to_le_bytes());
    serde_json::to_writer(
        &mut writer,
        &CheckpointRef {
            journal_offset,
            journal_sha256,
            state,
        },
    )?;
    writer.finish()
}

struct SegmentReader<'a, R> {
    input: &'a mut R,
    payload: Vec<u8>,
    position: usize,
    segments: u64,
    bytes: u64,
    hash: Sha256,
    short_segment: bool,
    finished: bool,
}

impl<R: Read> SegmentReader<'_, R> {
    fn next(&mut self) -> Result<()> {
        match frame::read_bounded(self.input, |kind| {
            if kind == frame::SNAPSHOT_DATA {
                (SEGMENT_BYTES + 8) as u64
            } else {
                METADATA_BYTES
            }
        })? {
            ReadFrame::Complete {
                kind: frame::SNAPSHOT_DATA,
                payload,
            } => {
                if self.short_segment
                    || payload.len() <= 8
                    || u64::from_le_bytes(payload[..8].try_into().unwrap()) != self.segments
                {
                    return Err(corrupt("invalid segment length/order"));
                }
                self.segments = self
                    .segments
                    .checked_add(1)
                    .ok_or_else(|| corrupt("segment count overflow"))?;
                self.bytes = self
                    .bytes
                    .checked_add((payload.len() - 8) as u64)
                    .ok_or_else(|| corrupt("byte count overflow"))?;
                self.hash.update(&payload[8..]);
                self.short_segment = payload.len() < SEGMENT_BYTES + 8;
                self.payload = payload;
                self.position = 8;
                Ok(())
            }
            ReadFrame::Complete {
                kind: frame::SNAPSHOT_END,
                payload,
            } => {
                let end: End = serde_json::from_slice(&payload)?;
                if self.segments == 0
                    || end.segments != self.segments
                    || end.json_bytes != self.bytes
                    || end.json_sha256 != format!("{:x}", self.hash.clone().finalize())
                {
                    return Err(corrupt("terminal manifest mismatch"));
                }
                require_eof(self.input)?;
                self.finished = true;
                Ok(())
            }
            _ => Err(corrupt("missing segment/terminal manifest")),
        }
    }
}

impl<R: Read> Read for SegmentReader<'_, R> {
    fn read(&mut self, bytes: &mut [u8]) -> io::Result<usize> {
        if bytes.is_empty() || self.finished {
            return Ok(0);
        }
        if self.position == self.payload.len() {
            self.next().map_err(io::Error::other)?;
            if self.finished {
                return Ok(0);
            }
        }
        let count = bytes.len().min(self.payload.len() - self.position);
        bytes[..count].copy_from_slice(&self.payload[self.position..self.position + count]);
        self.position += count;
        Ok(count)
    }
}

fn require_eof(input: &mut impl Read) -> Result<()> {
    // Reject even a single trailing byte without allocating another frame.
    if input.read(&mut [0_u8; 1])? != 0 {
        return Err(corrupt("trailing bytes"));
    }
    Ok(())
}

pub(super) fn read(input: &mut impl Read) -> Result<Checkpoint> {
    match frame::read_bounded(input, |kind| {
        if kind == frame::SNAPSHOT {
            frame::MAX_PAYLOAD
        } else {
            METADATA_BYTES
        }
    })? {
        ReadFrame::Complete {
            kind: frame::SNAPSHOT,
            payload,
        } => {
            require_eof(input)?;
            Ok(serde_json::from_slice(&payload)?)
        }
        ReadFrame::Complete {
            kind: frame::SNAPSHOT_HEADER,
            payload,
        } => {
            let header: Header = serde_json::from_slice(&payload)?;
            if header.version != 2 || header.segment_bytes != SEGMENT_BYTES {
                return Err(corrupt("unsupported stream version/segment size"));
            }
            let mut reader = SegmentReader {
                input,
                payload: Vec::new(),
                position: 0,
                segments: 0,
                bytes: 0,
                hash: Sha256::new(),
                short_segment: false,
                finished: false,
            };
            // from_reader checks JSON EOF, which must consume and validate the footer.
            let checkpoint = serde_json::from_reader(&mut reader)?;
            if !reader.finished {
                return Err(corrupt("terminal manifest not consumed"));
            }
            Ok(checkpoint)
        }
        _ => Err(corrupt("incomplete/invalid header")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    fn state() -> State {
        let mut state = State::default();
        // Three segments with UTF-8 sequences split across segment boundaries.
        state
            .revisions
            .insert("unicode".into(), ["雪".repeat(800_000)].into());
        state
    }
    fn encoded(state: &State) -> Vec<u8> {
        let mut bytes = vec![];
        write(&mut bytes, 0, &crate::sha256(b""), state, || Ok(())).unwrap();
        bytes
    }
    fn frames(bytes: &[u8]) -> Vec<(u16, Vec<u8>)> {
        let mut input = Cursor::new(bytes);
        let mut result = vec![];
        while let ReadFrame::Complete { kind, payload } = frame::read(&mut input).unwrap() {
            result.push((kind, payload));
        }
        result
    }
    fn pack(frames: &[(u16, Vec<u8>)]) -> Vec<u8> {
        frames
            .iter()
            .flat_map(|(kind, payload)| frame::encode(*kind, payload).unwrap())
            .collect()
    }
    fn rejected(bytes: &[u8]) {
        assert!(read(&mut Cursor::new(bytes)).is_err());
    }

    #[test]
    fn stream_round_trips_unicode_and_uses_bounded_frames() {
        let original = state();
        let bytes = encoded(&original);
        let frames = frames(&bytes);
        assert_eq!(frames.len(), 5);
        for (kind, payload) in &frames {
            assert!(
                payload.len()
                    <= if *kind == frame::SNAPSHOT_DATA {
                        SEGMENT_BYTES + 8
                    } else {
                        METADATA_BYTES as usize
                    }
            );
        }
        let restored = read(&mut Cursor::new(bytes)).unwrap();
        assert_eq!(
            serde_json::to_vec(&restored.state).unwrap(),
            serde_json::to_vec(&original).unwrap()
        );
        assert_eq!(restored.journal_offset, 0);
        assert_eq!(restored.journal_sha256, crate::sha256(b""));
    }

    #[test]
    fn stream_rejects_every_truncation_and_trailing_data() {
        let bytes = encoded(&State::default());
        for end in 0..bytes.len() {
            rejected(&bytes[..end]);
        }
        let mut extra = bytes.clone();
        extra.push(0);
        rejected(&extra);
        let mut appended = bytes.clone();
        appended.extend(&bytes);
        rejected(&appended);
        for position in [0, 25, bytes.len() - 1] {
            let mut corrupt = bytes.clone();
            corrupt[position] ^= 1;
            rejected(&corrupt);
        }
    }

    #[test]
    fn exact_segment_boundaries_do_not_emit_empty_data_frames() {
        for target in [
            SEGMENT_BYTES - 1,
            SEGMENT_BYTES,
            SEGMENT_BYTES + 1,
            2 * SEGMENT_BYTES,
        ] {
            let mut state = State::default();
            state
                .revisions
                .insert("padding".into(), [String::new()].into());
            let base = serde_json::to_vec(&CheckpointRef {
                journal_offset: 0,
                journal_sha256: &crate::sha256(b""),
                state: &state,
            })
            .unwrap()
            .len();
            state
                .revisions
                .insert("padding".into(), ["x".repeat(target - base)].into());
            let bytes = encoded(&state);
            let segments = frames(&bytes);
            assert_eq!(segments.len(), target.div_ceil(SEGMENT_BYTES) + 2);
            let footer: End = serde_json::from_slice(&segments.last().unwrap().1).unwrap();
            assert_eq!(footer.json_bytes, target as u64);
            assert_eq!(
                serde_json::to_vec(&read(&mut Cursor::new(bytes)).unwrap().state).unwrap(),
                serde_json::to_vec(&state).unwrap()
            );
        }
    }

    #[test]
    fn stream_rejects_reordering_duplicates_gaps_lengths_and_footer_changes() {
        let original = frames(&encoded(&state()));
        for mode in 0..10 {
            let mut frames = original.clone();
            match mode {
                0 => {
                    frames.swap(1, 2);
                }
                1 => {
                    frames.insert(2, frames[1].clone());
                }
                2 => {
                    frames.remove(2);
                }
                3 => {
                    frames[1].1.truncate(8);
                }
                4 => {
                    frames[1].1.pop();
                }
                5 => {
                    frames[1].0 = frame::PREPARE;
                }
                6 => {
                    frames[0].1 = br#"{"version":3,"segment_bytes":1048576}"#.to_vec();
                }
                7..=9 => {
                    let mut footer: serde_json::Value =
                        serde_json::from_slice(&frames.last().unwrap().1).unwrap();
                    match mode {
                        7 => footer["segments"] = 999.into(),
                        8 => footer["json_bytes"] = 0.into(),
                        _ => footer["json_sha256"] = "0".repeat(64).into(),
                    }
                    frames.last_mut().unwrap().1 = serde_json::to_vec(&footer).unwrap();
                }
                _ => unreachable!(),
            }
            rejected(&pack(&frames));
        }
        // A checksum-valid data mutation still fails the aggregate SHA-256.
        let mut changed = original;
        let index = changed[1]
            .1
            .windows(7)
            .position(|b| b == b"unicode")
            .unwrap();
        changed[1].1[index] = b'v';
        rejected(&pack(&changed));
    }

    #[test]
    fn stream_checks_declared_limits_before_payload_read_and_requires_complete_json() {
        let small = encoded(&State::default());
        let frames = frames(&small);
        for (kind, limit, prefix) in [
            (frame::SNAPSHOT_HEADER, METADATA_BYTES, vec![]),
            (
                frame::SNAPSHOT_DATA,
                (SEGMENT_BYTES + 8) as u64,
                pack(&frames[..1]),
            ),
            (frame::SNAPSHOT_END, METADATA_BYTES, pack(&frames[..2])),
        ] {
            let mut header = frame::encode(kind, b"").unwrap();
            header.truncate(frame::HEADER);
            header[12..20].copy_from_slice(&(limit + 1).to_le_bytes());
            let crc = crc32fast::hash(&header[..20]);
            header[20..24].copy_from_slice(&crc.to_le_bytes());
            let mut input = prefix;
            input.extend(header);
            let error = read(&mut Cursor::new(input)).err().unwrap().to_string();
            assert!(error.contains("oversized frame"), "{error}");
        }
        // The footer alone cannot make malformed or concatenated JSON acceptable.
        for body in [b"{".as_slice(), b"{}{}".as_slice()] {
            let mut changed = frames.clone();
            changed[1].1 = [0_u64.to_le_bytes().as_slice(), body].concat();
            changed[2].1 = serde_json::to_vec(&End {
                segments: 1,
                json_bytes: body.len() as u64,
                json_sha256: crate::sha256(body),
            })
            .unwrap();
            rejected(&pack(&changed));
        }
    }

    #[test]
    fn segment_writer_handles_partial_writes_and_propagates_io_failures() {
        struct Sink {
            bytes: Vec<u8>,
            fail_after: usize,
        }
        impl Write for Sink {
            fn write(&mut self, input: &[u8]) -> io::Result<usize> {
                if self.bytes.len() >= self.fail_after {
                    return Err(io::Error::other("disk full"));
                }
                let count = input.len().min(37).min(self.fail_after - self.bytes.len());
                self.bytes.extend_from_slice(&input[..count]);
                Ok(count)
            }
            fn flush(&mut self) -> io::Result<()> {
                Ok(())
            }
        }
        let original = state();
        let mut sink = Sink {
            bytes: vec![],
            fail_after: usize::MAX,
        };
        write(&mut sink, 0, &crate::sha256(b""), &original, || Ok(())).unwrap();
        assert_eq!(sink.bytes, encoded(&original));
        let mut failed = Sink {
            bytes: vec![],
            fail_after: SEGMENT_BYTES + 100,
        };
        assert!(write(&mut failed, 0, &crate::sha256(b""), &original, || Ok(())).is_err());
        rejected(&failed.bytes);
    }
}
