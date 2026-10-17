"""Observed durations only; no prompts, values, inferred stages or model reasoning."""
from contextlib import contextmanager
import time


@contextmanager
def phase(record, name):
    start = time.monotonic()
    try:
        yield
    finally:
        record['stages_ms'][name] = (time.monotonic() - start) * 1000


@contextmanager
def generation(worker, stage):
    if not hasattr(worker, 'measurements'):
        worker.measurements = []
    record = {'stage': stage, 'state': 'failed', 'stages_ms': {},
              'input_tokens': None, 'output_tokens': None}
    start = time.monotonic()
    try:
        yield record
        record['state'] = 'completed'
    finally:
        record['elapsed_ms'] = (time.monotonic() - start) * 1000
        worker.measurements.append(record)
