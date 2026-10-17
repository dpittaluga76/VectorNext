"""Isolated evaluation processor entry point; no production Compose selection."""
import argparse
import os
from pathlib import Path
import threading

from deployment import processor_server as base
from .families import digest
from .format_contract import INSTRUCTION

OPS = {'profile', 'stats', 'count', 'embed', 'rerank', 'answer_tokens', 'answer', 'plan_fields', 'closed_book'}


class EvaluationRuntime(base.Runtime):
    def __init__(self, capture_root):
        super().__init__()
        capture_root.mkdir(parents=True, exist_ok=True)
        self.lanes = {name: base.Lane(command=[
            os.environ.get('MODEL_PYTHON', '/opt/model-env/bin/python'), '-m',
            'evals.measurement.evaluation_worker', '--capture-directory', str(capture_root / name)])
            for name in ('interactive', 'background')}

    def health(self):
        result = super().health()
        result['measurement_adapter'] = {
            'version': 1, 'production_entry_point': False,
            'format_instruction_sha256': digest(INSTRUCTION.read_bytes()),
            'worker_sha256': digest(Path(__file__).with_name('evaluation_worker.py').read_bytes()),
            'closed_book_prompt_sha256': digest(Path(__file__).with_name('closed-book-v1.4.txt').read_bytes()),
            'closed_book_schema_sha256': digest(Path(__file__).with_name('closed-book-v1.4.schema.json').read_bytes())}
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture-root', type=Path, required=True)
    args = parser.parse_args()
    # Scope the private operation list to this dedicated processor process.
    base.OPS = OPS
    runtime = EvaluationRuntime(args.capture_root)
    server = base.Server(('0.0.0.0', 8090), runtime)
    threading.Thread(target=runtime.warm, daemon=True).start()
    try:
        server.serve_forever()
    finally:
        server.server_close()
        for lane in runtime.lanes.values():
            lane.stop()


if __name__ == '__main__':
    main()
