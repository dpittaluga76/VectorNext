"""Preserve public pre-Hybrid source bytes, including uncommitted experiments."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PREFIXES = ('experiments/t02/', 'experiments/t27/', 'experiments/t28/',
            'experiments/t29/', 'experiments/t30/', 'experiments/t33/',
            'experiments/t34/', 'experiments/t35/', 'experiments/t36/',
            'model_worker/', 'docker/', 'deployment/')


def main():
    destination = ROOT / 'archives/llm/pre-hybrid-source.zip'
    if destination.exists():
        raise SystemExit('Archive already exists; never overwrite historical sources')
    paths = sorted(set(subprocess.check_output(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=ROOT,
        text=True).splitlines()))
    paths = [p for p in paths if (p.startswith(PREFIXES) or
             (p.startswith('compose.') and p.endswith('.yaml'))) and (ROOT/p).is_file()]
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = {}
    with zipfile.ZipFile(destination, 'x', zipfile.ZIP_DEFLATED) as archive:
        for name in paths:
            raw = (ROOT/name).read_bytes()
            manifest[name] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
            archive.writestr(name, raw)
    with zipfile.ZipFile(destination) as archive:
        for name, record in manifest.items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == record['sha256']
    record = {'purpose': 'Exact public working-tree sources before T37 cleanup; includes uncommitted T33-T36.',
              'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'archive_sha256': hashlib.sha256(destination.read_bytes()).hexdigest(), 'files': manifest}
    destination.with_suffix('.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    print(f'Verified {len(paths)} files; archive SHA-256 {record["archive_sha256"]}')


if __name__ == '__main__':
    main()
