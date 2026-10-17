"""Evaluation-only worker adapter; never imported by production entry points.

Each Lane owns a serial JSON-lines subprocess. Scoped module bindings below must
not be used in a multithreaded interpreter. The execution runner still owns the
custody/freeze gate and model lease; this module does not admit evaluation jobs.
"""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from model_worker.server import Worker

from .format_contract import INSTRUCTION, messages_for_stage, require_string_fields

HERE = Path(__file__).parent


def prepared(messages):
    """Recognize only current production prompts; never transform user content."""
    from model_worker import answers, planning
    bases = {answers.PROMPT: 'extraction', answers.ASSESS_PROMPT: 'assessment',
             planning.PROMPT: 'planning', planning.PROMPT + planning.REQUESTED_FACTS: 'planning'}
    instruction = INSTRUCTION.read_text(encoding='utf-8')
    if not messages or messages[0].get('role') != 'system':
        raise ValueError('Expected an explicit benchmark system prompt')
    content = messages[0].get('content')
    if content in bases:
        return messages_for_stage(messages, bases[content])
    suffix = '\n\n' + instruction
    if isinstance(content, str) and content.endswith(suffix) and content[:-len(suffix)] in bases:
        # _generate calls count_prompt after generate has already applied it.
        return deepcopy(messages), {'stage': bases[content[:-len(suffix)]],
            'instruction_sha256': hashlib.sha256(INSTRUCTION.read_bytes()).hexdigest()}
    raise ValueError('Unknown or multiply formatted benchmark prompt')


@contextmanager
def formatted_operations():
    from model_worker import answers, planning
    from model_worker.measurement import generation
    original_count, original_generate, original_plan = answers.count_prompt, answers.generate, planning.generate

    def count(worker, messages, schema=None):
        effective, _ = prepared(messages)
        return original_count(worker, effective, schema)

    def generate(worker, messages, schema, prompt, output_tokens=answers.OUTPUT_TOKENS):
        effective, contract = prepared(messages)
        # Validate the caller's prompt identity before replacing its audit hash.
        if messages[0]['content'] != prompt:
            raise ValueError('Prompt/audit identity mismatch')
        with generation(worker, contract['stage']) as observed:
            value, audit = answers._generate(worker, effective, schema, effective[0]['content'], output_tokens, observed)
        audit['evaluation_format'] = contract
        return value, audit

    answers.count_prompt, answers.generate, planning.generate = count, generate, generate
    try:
        yield
    finally:
        answers.count_prompt, answers.generate, planning.generate = original_count, original_generate, original_plan


def formatted_operation(worker, request):
    """Called inside the selected model lease by a future isolated entry point."""
    op = request['op']
    if op not in ('plan_fields', 'answer_tokens', 'answer'):
        raise ValueError('Not a formatted evaluation operation')
    if op in ('answer', 'answer_tokens'):
        require_string_fields(list(request['input']['fields'].values()))
    with formatted_operations():
        result = Worker.operation(worker, request)
    if op == 'plan_fields' and result['plan']['status'] == 'ready':
        require_string_fields(result['plan']['fields'])
    return result


def closed_book(worker, value):
    """One D7 call: no history, evidence, field hints, fallback or retry."""
    from model_worker import answers
    from model_worker.measurement import generation
    if (not isinstance(value, dict) or set(value) != {'question'}
            or not isinstance(value['question'], str) or not value['question'].strip()
            or len(value['question'].encode()) > 8192):
        raise ValueError('Closed-book input accepts only a bounded original question')
    prompt = (HERE / 'closed-book-v1.4.txt').read_text(encoding='utf-8')
    schema_raw = (HERE / 'closed-book-v1.4.schema.json').read_bytes()
    schema = json.loads(schema_raw)
    messages = [{'role': 'system', 'content': prompt}, {'role': 'user', 'content': value['question']}]
    # Do not install the D4 formatting wrapper: this control has its own freeze.
    with generation(worker, 'closed_book') as observed:
        result, audit = answers._generate(worker, messages, schema, prompt, 768, observed)
    audit['evaluation_control'] = {
        'instruction_sha256': hashlib.sha256((HERE / 'closed-book-v1.4.txt').read_bytes()).hexdigest(),
        'schema_file_sha256': hashlib.sha256(schema_raw).hexdigest(),
        'question_sha256': hashlib.sha256(value['question'].encode()).hexdigest(),
        'source_available': False, 'gold_fields_available': False, 'attempts': 1}
    return {'control': result, 'audit': audit}


class EvaluationWorker(Worker):
    """Dedicated serial worker; normal model_worker.server stays unchanged."""
    capture_directory = None

    def handle(self, request):
        if request['op'] in ('generate', 'rewrite'):
            raise ValueError('Evaluation worker forbids enrichment and prose')
        if request['op'] == 'closed_book':
            with self.selected(request.get('lease')):
                return closed_book(self, request['input'])
        return super().handle(request)

    def operation(self, request):
        if request['op'] in ('plan_fields', 'answer_tokens', 'answer'):
            return formatted_operation(self, request)
        if request['op'] not in ('profile', 'stats', 'count', 'embed', 'rerank'):
            raise ValueError('Evaluation worker forbids enrichment and prose')
        return super().operation(request)

    def http(self, path, payload, priority='background'):
        from .families import save
        if self.capture_directory is None:
            raise ValueError('Evaluation wire capture must be initialized')
        number = self.transport_sequence
        self.transport_sequence += 1
        prefix = self.capture_directory / f'transport-{number:03d}'
        save(prefix.with_suffix('.request.json'), {'capture_type': 'decoded_transport', 'path': path,
            'priority': priority, 'lease': self.lease, 'profile': self.generation_profile['name'], 'payload': payload})
        try:
            response = super().http(path, payload, priority)
        except Exception as error:
            save(prefix.with_suffix('.error.json'), {'error': f'{type(error).__name__}: {error}'})
            raise
        save(prefix.with_suffix('.response.json'), {'capture_type': 'decoded_transport', 'response': response})
        return response


def main():
    import argparse
    import os
    import sys
    import uuid
    from .families import digest, save
    from model_worker.cache import canonical
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture-directory', type=Path, required=True)
    args = parser.parse_args()
    args.capture_directory.mkdir(parents=True, exist_ok=True)
    session = args.capture_directory / ('worker-' + uuid.uuid4().hex)
    session.mkdir(exist_ok=False)
    def raw_save(path, data):
        with path.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    worker = None
    sequence = 0
    while True:
        raw = sys.stdin.buffer.readline(4 * 1024 * 1024 + 1)
        if not raw:
            return
        if len(raw) > 4 * 1024 * 1024 or not raw.endswith(b'\n'):
            raw_save(session / f'oversized-{sequence:06d}.json', raw)
            raise ValueError('Oversized/incomplete worker request retained')
        request = json.loads(raw)
        # Token splitting can make thousands of CPU-only calls per document.
        # Processor health retains their counts/time. Full wire capture is for
        # retrieval and generation, not repeated prefix token-count strings.
        capture = request.get('op') not in ('profile', 'stats', 'count', 'embed')
        directory = session / f'rpc-{sequence:06d}'
        sequence += 1
        if capture:
            directory.mkdir()
            raw_save(directory / 'request.json', raw)
        try:
            if worker is None:
                worker = EvaluationWorker()
            worker.capture_directory, worker.transport_sequence, worker.measurements = directory, 0, []
            reply = {'result': worker.handle(request)}
        except Exception as error:
            reply = {'error': f'{type(error).__name__}: {error}'[:4096]}
        reply['measurement'] = {'version': 1, 'calls': getattr(worker, 'measurements', []),
            'evaluation_capture': {'rpc': f'{session.name}/{directory.name}', 'request_sha256': digest(raw),
                                   'wire_request_retained': capture, 'transport_capture': 'decoded'}}
        wire = canonical(reply) + b'\n'
        if len(wire) > 4 * 1024 * 1024:
            directory.mkdir(exist_ok=True)
            save(directory / 'oversized-reply.json', reply)
            raise ValueError('Oversized worker reply retained; no truncated success')
        if capture:
            raw_save(directory / 'response.json', wire)
        sys.stdout.buffer.write(wire)
        sys.stdout.buffer.flush()


if __name__ == '__main__':
    main()
