"""Post-run reporting only: preserve the frozen scorer and sleep-affected capture."""
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / 'data/t37/pilot-v1'
SUPPORTED = {'constrained_count', 'pdf_pressure', 'explicit_identifiers', 'followup_draft', 'exact_sequence'}
METRICS = ('seconds', 'queue_seconds', 'activation_seconds', 'work_seconds', 'observed_generation_seconds')


def stats(values):
    values = sorted(v for v in values if v is not None)
    return {'n': len(values), 'median': statistics.median(values),
            'p95': values[math.ceil(len(values) * .95) - 1], 'min': values[0], 'max': values[-1]} if values else None


def main():
    raw = (RUN / 'summary.json').read_bytes()
    summary = json.loads(raw)
    freeze = json.loads((RUN / 'execution-freeze.json').read_bytes())
    output = {'run': 'pilot-v1', 'protocol': 'docs/t37-protocol.md',
              'frozen_summary_sha256': hashlib.sha256(raw).hexdigest(),
              'execution_freeze_sha256': hashlib.sha256((RUN / 'execution-freeze.json').read_bytes()).hexdigest(),
              'source_zip_sha256': freeze['source_zip_sha256'], 'frozen_files': len(freeze['files']),
              'images': freeze['images'], 'gpu': freeze['gpu'],
              'timing_exclusion': {'mode': 'hybrid', 'case': 'unclear_subject',
                  'reason': 'User confirmed overnight PC sleep. Original raw timing and accuracy denominator retained; only derived timing summaries exclude this turn.'},
              'modes': {}}
    for mode, arm in summary['modes'].items():
        cases = [{k: v for k, v in c.items() if k not in ('score', 'original_score')} |
                 {'correct': c['score']['correct'], 'original_correct': c['score']['original_score_correct']}
                 for c in arm['cases']]
        timed = [c for c in cases if c['admitted'] and not (mode == 'hybrid' and c['case'] == 'unclear_subject')]
        positives = [c for c in cases if c['case'] in SUPPORTED]
        output['modes'][mode] = {'correct': arm['correct'], 'denominator': 8,
            'unchanged_scorer_correct': arm['original_scorer_correct'], 'admitted': sum(c['admitted'] for c in cases),
            'fallbacks': arm['fallbacks'], 'cases': cases,
            'admitted_sleep_excluded_timing': {k: stats([c[k] for c in timed]) for k in METRICS},
            'five_common_supported_timing': {k: stats([c[k] for c in positives]) for k in METRICS}}
    samples = [json.loads(line) for line in (RUN / 'resources.jsonl').read_text().splitlines()]
    gpu = [int(s['gpu'].split(',')[0]) for s in samples if s.get('gpu') and ',' in s['gpu']]
    ram = [s['ram'] for s in samples if s.get('ram')]
    output['resources'] = {'samples': len(samples), 'whole_device_gpu_peak_mib': max(gpu),
        'minimum_host_available_ram_bytes': min(s['available_bytes'] for s in ram),
        'maximum_host_ram_load_percent': max(s['load_percent'] for s in ram),
        'limits': 'Whole-device and host samples, not per-model allocations; WDDM paging was not instrumented. Sampling pauses during PC sleep.'}
    operational = ROOT / 'data/t37/operational'
    output['operational_drill'] = json.loads((operational / 'drill-v1/success.json').read_bytes())
    output['ui_release_amendment'] = json.loads((operational / 'ui-release.json').read_bytes())
    output['normal_browser_activation'] = json.loads((operational / 'activation-browser-v2/activation-browser-result.json').read_bytes())
    output['final_release_browser'] = json.loads((operational / 'release-browser-result.json').read_bytes())
    backup = ROOT / 'backups/t37-preactivation-20261016'
    verified = json.loads((backup / 'verification.json').read_bytes())
    output['backup'] = {k: verified[k] for k in ('verified', 'restored_volume', 'generation', 'documents', 'jobs')}
    output['backup']['full_volume_tar_sha256'] = verified['hashes']['storage.tar']
    output['backup']['export_manifest_sha256'] = verified['hashes']['export/backup.json']
    path = ROOT / 'docs/reports/t37-hybrid.json'
    path.write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
    print(path)
    for mode, arm in output['modes'].items():
        print(mode, arm['correct'], arm['five_common_supported_timing']['work_seconds'], arm['admitted_sleep_excluded_timing']['seconds'])
    print(output['resources'])


if __name__ == '__main__':
    main()
