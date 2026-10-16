"""Offline CLI checks on isolated Linux storage; no application/model data.

Set VECTORNEXT_MAINTENANCE_ROOT to a disposable Linux volume and
VECTORNEXT_MAINTENANCE_TIGHT_ROOT to a separate filesystem with <64 MiB free.
Run with all capabilities dropped so read-only permissions are enforced.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.environ.get("VECTORNEXT_MAINTENANCE_ROOT"),
                     "requires explicitly isolated Linux maintenance storage")
class MaintenanceCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(
            dir=os.environ["VECTORNEXT_MAINTENANCE_ROOT"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "db"
        self.cli("inspect", self.db)

    def cli(self, *args, success=True):
        result = subprocess.run(["vectornext", *map(str, args)],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode == 0, success, result.stderr)
        return json.loads(result.stdout) if success else result.stderr

    @staticmethod
    def inventory(path):
        return {str(p.relative_to(path)): (p.stat().st_size,
                p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())
                for p in path.rglob("*") if p.is_file()}

    def test_dry_run_does_not_repair_or_create_and_apply_is_explicit(self):
        with (self.db / "journal.bin").open("ab") as file:
            file.write(b"VNX")
        before = self.inventory(self.db)
        report = self.cli("storage-plan", self.db)
        self.assertEqual(report["uncommitted_tail_bytes"], 3)
        self.assertEqual(before, self.inventory(self.db))
        self.cli("compact", self.db, success=False)
        self.assertEqual(before, self.inventory(self.db))
        missing = self.root / "missing"
        self.cli("storage-plan", missing, success=False)
        self.assertFalse(missing.exists())

    def test_read_only_inspection(self):
        paths = [self.root, self.db, self.db / "blobs"]
        files = list(self.db.glob("*"))
        for path in files:
            if path.is_file():
                path.chmod(0o444)
        for path in paths:
            path.chmod(0o555)
        try:
            before = self.inventory(self.db)
            self.assertEqual(self.cli("storage-plan", self.db)["status"], "dry_run")
            self.cli("compact", self.db, "--apply", success=False)
            self.assertEqual(before, self.inventory(self.db))
        finally:
            for path in paths:
                path.chmod(0o755)
            for path in files:
                if path.is_file():
                    path.chmod(0o644)

    def test_disk_volume_exchange_backup_and_repeat(self):
        data = b"unreferenced original" * 65536
        blob = self.db / "blobs" / hashlib.sha256(data).hexdigest()
        blob.write_bytes(data)
        sibling = self.root / "db.answer-jobs"
        sibling.mkdir()
        (sibling / "retained.job").write_bytes(b"opaque history")
        self.cli("export", self.db, self.root / "backup")
        self.cli("restore", self.root / "backup", self.root / "restored")
        lock_inode = (self.db / "writer.lock").stat().st_ino
        result = self.cli("compact", self.db, "--apply")
        self.assertEqual(result["unreferenced_blobs"]["files"], 1)
        self.assertGreater(result["actual_reclaimed_bytes"], 1_000_000)
        self.assertEqual((self.db / "writer.lock").stat().st_ino, lock_inode)
        self.assertFalse(blob.exists())
        self.assertEqual((sibling / "retained.job").read_bytes(), b"opaque history")
        self.assertEqual(self.cli("inspect", self.db)["documents"], [])
        self.assertEqual(self.cli("compact", self.db, "--apply")["actual_reclaimed_bytes"], 0)
        self.assertFalse(list(self.root.glob(".vnx-compact-*")))

    def test_actual_insufficient_filesystem_space_rejects_before_staging(self):
        tight = os.environ.get("VECTORNEXT_MAINTENANCE_TIGHT_ROOT")
        self.assertIsNotNone(tight, "set a separate <64 MiB filesystem")
        with tempfile.TemporaryDirectory(dir=tight) as directory:
            root = Path(directory)
            db = root / "db"
            shutil.copytree(self.db, db)
            before = self.inventory(db)
            report = self.cli("storage-plan", db)
            self.assertFalse(report["enough_space"], report)
            self.assertIn("insufficient free space", self.cli("compact", db, "--apply", success=False))
            self.assertEqual(before, self.inventory(db))
            self.assertFalse(list(root.glob(".vnx-compact-*")))
