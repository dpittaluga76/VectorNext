"""Independent streaming inspection of completed T21 snapshots, without loading state JSON."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib

def inspect(path):
    whole = hashlib.sha256()
    data = hashlib.sha256()
    segments = length = maximum = 0
    short = False
    with path.open('rb') as stream:
        position = 0
        while True:
            header = stream.read(24)
            assert len(header) == 24
            magic, version, kind, size, crc = struct.unpack('<8sHHQI', header)
            assert magic == b'VNXFRAME' and version == 1 and zlib.crc32(header[:20]) == crc
            assert size <= (1048584 if kind == 6 else 4096)
            payload = stream.read(size)
            checksum = stream.read(4)
            assert len(payload) == size and len(checksum) == 4
            assert zlib.crc32(payload, zlib.crc32(header)) == struct.unpack('<I', checksum)[0]
            whole.update(header); whole.update(payload); whole.update(checksum)
            maximum = max(maximum, size)
            if position == 0:
                assert kind == 5 and json.loads(payload) == {'version': 2, 'segment_bytes': 1048576}
            elif kind == 6:
                assert not short and size > 8 and struct.unpack('<Q', payload[:8])[0] == segments
                segments += 1
                length += size - 8
                data.update(payload[8:])
                short = size < 1048584
            else:
                assert kind == 7 and segments > 0
                assert json.loads(payload) == {'segments': segments, 'json_bytes': length, 'json_sha256': data.hexdigest()}
                assert stream.read(1) == b''
                break
            position += 1
    return {'file_bytes': path.stat().st_size, 'segments': segments, 'json_bytes': length,
            'max_frame_payload': maximum, 'snapshot_sha256': whole.hexdigest()}

if __name__ == '__main__':
    root = Path(sys.argv[1])
    results = {}
    for size in ('400', '1600'):
        rows = [inspect(root / name / 'snapshot.bin') for name in (size, f'export-{size}', f'restored-{size}')]
        assert rows[0] == rows[1] == rows[2]
        assert rows[0]['file_bytes'] > 64 * 1024 * 1024
        results[size] = rows[0]
    print(json.dumps(results, indent=2))
