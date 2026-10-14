"""Fetch exact public artifacts, or verify them without network access."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import time
from urllib.request import Request, urlopen


LOCK = Path(os.environ.get("VECTORNEXT_MODELS_LOCK", Path(__file__).with_name("models.lock.json")))


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def artifact_path(root, model, artifact):
    path = (root / model["directory"] / artifact["path"]).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Artifact path escapes model directory")
    return path


def verify(path, artifact):
    return path.is_file() and path.stat().st_size == artifact["size"] and sha256(path) == artifact["sha256"]


def download_ranges(url, partial, size, workers=4, chunk_size=32 * 1024 * 1024):
    """Resume a contiguous prefix; verify every range and the complete file afterward."""
    start = partial.stat().st_size if partial.exists() else 0
    if start > size:
        raise ValueError("Partial download exceeds expected size")

    def read_range(bounds):
        first, last = bounds
        request = Request(url + f"?download=true&range={first}-{last}", headers={"Range": f"bytes={first}-{last}"})
        with urlopen(request, timeout=60) as response:
            if response.status != 206 or response.headers.get("Content-Range") != f"bytes {first}-{last}/{size}":
                raise ValueError("Server did not honor the exact download range")
            block = response.read(last - first + 2)
        if len(block) != last - first + 1:
            raise ValueError("Incomplete download range")
        return block

    reported = start
    with ThreadPoolExecutor(max_workers=workers) as pool, partial.open("ab") as out:
        # Only one bounded group is submitted at a time; completed futures cannot
        # accumulate an entire large model in RAM behind a slow leading request.
        while start < size:
            ranges = [(first, min(first + chunk_size, size) - 1) for first in range(start, min(start + workers * chunk_size, size), chunk_size)]
            for block in pool.map(read_range, ranges):
                out.write(block)
                out.flush()
                start += len(block)
            if start - reported >= 256 * 1024 * 1024 or start == size:
                print(f"DOWNLOAD {start}/{size} bytes ({100 * start / size:.1f}%)", flush=True)
                reported = start


def fetch(root, verify_only=False, workers=4):
    if not 1 <= workers <= 8:
        raise ValueError("Download workers must be between 1 and 8")
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    for model in lock["models"].values():
        for artifact in model["files"]:
            path = artifact_path(root, model, artifact)
            if verify(path, artifact):
                print(f"VERIFIED {model['directory']}/{artifact['path']}", flush=True)
                continue
            if verify_only:
                raise ValueError(f"Missing or invalid artifact: {path}. Run the explicit model download first.")
            path.parent.mkdir(parents=True, exist_ok=True)
            partial = path.with_suffix(path.suffix + ".part")
            url = f"https://huggingface.co/{model['repo']}/resolve/{model['revision']}/{artifact['remote_path']}"
            print(f"FETCH {model['directory']}/{artifact['path']} ({artifact['size']} bytes)", flush=True)
            for attempt in range(3):
                try:
                    if artifact["size"] >= 256 * 1024 * 1024 and workers > 1:
                        download_ranges(url, partial, artifact["size"], workers)
                    else:
                        with urlopen(url, timeout=60) as response, partial.open("wb") as out:
                            while block := response.read(4 * 1024 * 1024):
                                out.write(block)
                    if not verify(partial, artifact):
                        raise ValueError(f"Downloaded bytes failed checksum: {artifact['path']}")
                    partial.replace(path)
                    break
                except ValueError:
                    partial.unlink(missing_ok=True)
                    if attempt == 2:
                        raise
                    time.sleep(2 * (attempt + 1))
                except OSError:
                    # A validated contiguous prefix can be resumed after a network failure.
                    if attempt == 2:
                        raise
                    time.sleep(2 * (attempt + 1))
            print(f"VERIFIED {model['directory']}/{artifact['path']}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", type=Path, default=Path("/models"))
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--workers", type=int, default=4, help="1-8 bounded download workers; 1 uses serial downloads")
    args = parser.parse_args()
    fetch(args.models, args.verify_only, args.workers)
