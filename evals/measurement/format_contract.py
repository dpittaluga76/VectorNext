"""Pure evaluation adapter helpers; never installed in the production worker.

The future frozen runner must record these identities at each relevant call.
No gold file is accepted here, and original user/question messages stay intact.
"""
from copy import deepcopy
from pathlib import Path

from .typed_facts import digest

INSTRUCTION = Path(__file__).with_name('answer-format-v1.1.txt')
STAGES = ('planning', 'assessment', 'extraction')


def messages_for_stage(messages, stage):
    if stage not in STAGES:
        raise ValueError('Unknown benchmark format stage')
    result = deepcopy(messages)
    if not result or result[0].get('role') != 'system' or not isinstance(result[0].get('content'), str):
        raise ValueError('Expected an explicit system instruction')
    instruction = INSTRUCTION.read_text(encoding='utf-8')
    if instruction in result[0]['content']:
        raise ValueError('Format instruction already applied')
    result[0]['content'] += '\n\n' + instruction
    return result, {'stage': stage, 'instruction_sha256': digest(INSTRUCTION)}


def require_string_fields(fields):
    """Do not silently coerce a plan or revise its identity after generation."""
    if not fields or any(f.get('kind') != 'string' for f in fields):
        raise ValueError('Benchmark plan does not satisfy the frozen string-field instruction')
    return deepcopy(fields)
