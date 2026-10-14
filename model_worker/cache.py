"""Disposable bounded cache. Atomic replacement, checksummed payload, corrupt = miss."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from contextlib import contextmanager
import fcntl


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


class Cache:
    def __init__(self, root, max_bytes=64 * 1024 * 1024):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes
        self.hits = self.misses = 0
        with self.locked():
            for pending in self.root.glob("vn-cache-*.pending"):
                pending.unlink(missing_ok=True)
            self.prune()

    @contextmanager
    def locked(self):
        # Separate CLI processes may share this disposable cache. Inference never
        # holds this lock; only lookup/eviction/atomic publication are serialized.
        with (self.root / "cache.lock").open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def prune(self, incoming=0):
        # Only this cache's hashed entries are eligible for deletion.
        entries = sorted((p for p in self.root.glob("*.json") if len(p.stem) == 64
                          and all(c in "0123456789abcdef" for c in p.stem)), key=lambda p: p.stat().st_mtime_ns)
        sizes = [(p, p.stat().st_size) for p in entries]
        size = sum(n for _, n in sizes)
        for path, n in sizes:
            if size + incoming <= self.max_bytes:
                break
            path.unlink(missing_ok=True)
            size -= n

    def get(self, key):
        with self.locked():
            return self._get(key)

    def _get(self, key):
        try:
            path = self.root / (key + ".json")
            if path.stat().st_size > min(self.max_bytes, 4 * 1024 * 1024):
                raise ValueError("oversized entry")
            entry = json.loads(path.read_bytes())
            if entry["key"] != key or entry["sha256"] != digest(entry["value"]):
                raise ValueError("cache checksum mismatch")
            self.hits += 1
            return True, entry["value"]
        except (OSError, ValueError, KeyError, TypeError):
            self.misses += 1
            return False, None

    def put(self, key, value):
        with self.locked():
            self._put(key, value)

    def _put(self, key, value):
        data = canonical({"key": key, "value": value, "sha256": digest(value)})
        if len(data) > min(self.max_bytes, 4 * 1024 * 1024):
            return
        self.prune(len(data))
        name = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.root, prefix="vn-cache-", suffix=".pending", delete=False) as f:
                name = f.name
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(name, self.root / (key + ".json"))
        finally:
            if name:
                Path(name).unlink(missing_ok=True)
