"""NuExtract prompt guidance. The original JSON Schema remains the hard constraint.

Native templates cannot express dependent unions, empty objects or a null-only
leaf. Merge the prompt guidance across branches, using string for null-only
leaves. Never use this projection to validate or materialize an answer.
"""
import json


def project(schemas, key='', depth=0):
    if depth > 64:
        raise ValueError('extraction template depth exceeded')
    expanded = []
    for schema in schemas:
        if 'oneOf' in schema or 'anyOf' in schema:
            expanded.extend(schema.get('oneOf', schema.get('anyOf')))
        else:
            expanded.append(schema)
    if any('oneOf' in s or 'anyOf' in s for s in expanded):
        return project(expanded, key, depth + 1)
    nonnull = [s for s in expanded if s.get('type') != 'null' and s != {'const': None}]
    if not nonnull:
        return 'string'  # Grammar still requires null, never a transcribed value.
    properties = {}
    kinds = set()
    values = []
    for schema in nonnull:
        if 'const' in schema or 'enum' in schema:
            for value in schema.get('enum', [schema.get('const')]):
                if value is not None:
                    if not isinstance(value, str):
                        raise ValueError('native extraction enum must contain strings')
                    if value not in values:
                        values.append(value)
            kinds.add('string')
        else:
            kind = schema.get('type')
            kinds.update(kind if isinstance(kind, list) else [kind])
        for name, child in schema.get('properties', {}).items():
            properties.setdefault(name, []).append(child)
    kinds.discard('null')
    if kinds == {'object'}:
        return {name: project(children, name, depth + 1) for name, children in properties.items()}
    if kinds == {'array'}:
        return [project([s['items'] for s in nonnull], key, depth + 1)]
    if kinds == {'string'}:
        if values and all('const' in s or 'enum' in s for s in nonnull):
            return values
        return 'verbatim-string' if key == 'quote' else 'string'
    if kinds <= {'integer', 'number'} and kinds:
        return 'number' if 'number' in kinds else 'integer'
    if kinds == {'boolean'}:
        return 'boolean'
    raise ValueError('unsupported extraction template union: ' + str(sorted(kinds, key=str)))


def options(profile, schema):
    from .generator_profile import answer_adapter
    if answer_adapter(profile) is None:
        return {}
    if schema is None:
        raise ValueError('NuExtract requires the actual output schema for prompt admission')
    template = json.dumps(project([schema]), ensure_ascii=False, separators=(',', ':'))
    if len(template.encode()) > 65536:
        raise ValueError('extraction template exceeds byte budget')
    return {'chat_template_kwargs': {'enable_thinking': False, 'template': template}}
