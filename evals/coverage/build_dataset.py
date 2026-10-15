"""Explicit pre-inference annotation authoring. Never imported by the runner/tests."""
import itertools
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent


def build():
    if (HERE / 'data-freeze.json').exists():
        raise ValueError('annotations are frozen')
    sources = json.loads((HERE / 'sources.json').read_text(encoding='utf-8'))
    data = {'version': 't14-annotation-v2', 'documents': sources, 'evidence': [], 'cases': []}
    requests = {}

    def text(doc, value):
        raw = (HERE / 'fixtures' / (doc + '.txt')).read_bytes()
        needle = value.encode('utf-8'); start = raw.index(needle)
        identifier = doc + '-' + str(len(data['evidence']) + 1)
        # Unicode whitespace, mapped back to exact UTF-8 byte offsets.
        parts = [[start + len(value[:m.start()].encode()), start + len(value[:m.end()].encode())]
                 for m in re.finditer(r'\S+', value)]
        data['evidence'].append({'id': identifier, 'document_id': doc,
            'locator': {'kind': 'text', 'byte_start': start, 'byte_end': start + len(needle),
                        'line_start': raw[:start].count(b'\n') + 1,
                        'line_end': raw[:start + len(needle)].count(b'\n') + 1},
            'content_runs': parts, 'expected': value})
        return identifier

    def lines(doc, needles):
        lines = (HERE / 'fixtures' / (doc + '.txt')).read_text(encoding='utf-8').splitlines()
        found = [line for line in lines if any(needle in line for needle in needles)]
        if not found:
            raise ValueError((doc, needles))
        return [text(doc, line) for line in found]

    def pointer(doc, path):
        value = json.loads((HERE / 'fixtures' / (doc + '.json')).read_bytes())
        for part in path.split('/')[1:]:
            value = value[int(part)] if isinstance(value, list) else value[part]
        identifier = doc + '-' + str(len(data['evidence']) + 1)
        data['evidence'].append({'id': identifier, 'document_id': doc,
                                'locator': {'kind': 'json', 'pointer': path}, 'expected': value})
        return [identifier]

    def case(identifier, question, fields, values, refs, tags, history=None, status='supported', alternatives=None):
        expected = {'status': status, 'fields': values, 'field_sources': refs}
        if status == 'supported':
            expected['support_sets'] = [sorted(set(group)) for group in itertools.product(*refs.values())]
        if alternatives:
            expected['alternatives'] = alternatives
        data['cases'].append({'id': identifier, 'split': 'comparison', 'question': question, 'tags': tags, 'expected': expected})
        requests[identifier] = {'question': question, 'fields': fields}
        if history:
            requests[identifier]['history'] = history

    def field(kind, description, nullable=False):
        return {'kind': kind, 'description': description, 'nullable': nullable}

    ignition = lines('mariner_9', ['ignited its main engine for'])
    photos = lines('mariner_9', ['returning 7,329 photos'])
    venus = lines('mariner_10', ['returned 4,165 photos'])
    mercury = [lines('mariner_10', [needle]) for needle in ('at a range of 437 miles', '48,069 kilometers', '327 kilometers')]
    case('ignition_duration', 'For how many seconds did Mariner 9 fire its main engine to enter Mars orbit?',
         {'seconds': field('number', 'Mariner 9 Mars orbit insertion engine burn duration in seconds')}, {'seconds': 915.6}, {'seconds': ignition}, ['single_source', 'numeric_distractors'])
    case('mission_photos', 'How many photos had Mariner 9 returned by last contact, including the moon photos?',
         {'photos': field('integer', 'Mariner 9 final reported photo count, including Phobos and Deimos')}, {'photos': 7329}, {'photos': photos}, ['numeric_distractors'])
    case('venus_photos', 'How many photos of Venus did Mariner 10 return during its Venus encounter?',
         {'photos': field('integer', 'Mariner 10 Venus encounter photo count')}, {'photos': 4165}, {'photos': venus}, ['numeric_distractors'])
    case('three_mercury_ranges', 'Give the closest approach ranges in kilometers for Mariner 10\'s first, second and third Mercury flybys separately.',
         {n: field('integer', 'Mariner 10 ' + ordinal + ' Mercury flyby closest range in kilometers') for n, ordinal in [('first_km', 'first'), ('second_km', 'second'), ('third_km', 'third')]},
         {'first_km': 703, 'second_km': 48069, 'third_km': 327}, dict(zip(['first_km', 'second_km', 'third_km'], mercury)), ['distant_passages', 'numeric_distractors'])
    mass_docs = [('mariner_4', 260.8), ('near_shoemaker', 805), ('magellan', 3445)]
    masses = {d: lines(d, ['Spacecraft Mass |']) for d, _ in mass_docs}
    case('three_masses', 'Give the listed spacecraft masses in kilograms for Mariner 4, NEAR Shoemaker and Magellan separately.',
         {d + '_kg': field('number' if isinstance(v, float) else 'integer', d.replace('_', ' ') + ' spacecraft mass in kilograms') for d, v in mass_docs},
         {d + '_kg': v for d, v in mass_docs}, {d + '_kg': masses[d] for d, _ in mass_docs}, ['multi_document', 'units'])
    launch_docs = [('mariner_6', 1969, ['Launch Date and Time |', 'was launched at']), ('mariner_9', 1971, ['Launch Date and Time |', 'lifted off from']), ('near_shoemaker', 1996, ['Launch Date and Time |', '1996: Launch'])]
    launches = {d: lines(d, needles) for d, _, needles in launch_docs}
    for d, date in [('mariner_6', 'Feb. 25,1969'), ('mariner_9', 'May 30, 1971'), ('near_shoemaker', 'Feb. 17, 1996')]:
        launches[d].append(text(d, 'Launch\n\n' + date))
    case('three_launches', 'Give the launch years of Mariner 6, Mariner 9 and NEAR Shoemaker separately.',
         {d + '_year': field('integer', d.replace('_', ' ') + ' launch year') for d, _, _ in launch_docs},
         {d + '_year': v for d, v, _ in launch_docs}, {d + '_year': launches[d] for d, _, _ in launch_docs}, ['multi_document', 'duplicate_support', 'whitespace_boundary'])
    mags = {d: pointer(d, '/features/0/properties/mag') for d in ('nepal', 'sumatra')}
    case('two_earthquakes', 'Give the USGS recorded magnitudes for the April 25, 2015 Nepal earthquake and December 26, 2004 Sumatra earthquake separately.',
         {d + '_magnitude': field('number', d + ' earthquake magnitude, ' + date) for d, date in [('nepal', 'April 25 2015'), ('sumatra', 'December 26 2004')]},
         {'nepal_magnitude': 7.8, 'sumatra_magnitude': 9.1}, {d + '_magnitude': mags[d] for d in mags}, ['multi_document', 'json'])
    landing = lines('near_shoemaker', ['2001: NEAR touched down', 'landed on the surface', 'at a gentle 4 miles'])
    case('near_timeline', 'In which years did NEAR Shoemaker launch and touch down on Eros?',
         {'launch_year': field('integer', 'NEAR Shoemaker launch year'), 'landing_year': field('integer', 'NEAR Shoemaker touchdown on Eros year')},
         {'launch_year': 1996, 'landing_year': 2001}, {'launch_year': launches['near_shoemaker'], 'landing_year': landing}, ['distant_passages', 'duplicate_support'])
    case('conversation_planet', 'How many photos did it return of that planet?',
         {'photos': field('integer', 'Photos of the planet asked about in the preceding user question')}, {'photos': 4165}, {'photos': venus}, ['conversation', 'numeric_distractors'],
         history=[{'role': 'user', 'text': 'When did Mariner 10 encounter Venus?'}, {'role': 'assistant', 'text': 'It encountered Venus in February 1974, then continued to Mercury, where three flybys returned over 2,700 pictures.'}])
    case('conversation_mission', 'What was the final photo count for that mission, including the moon photos?',
         {'photos': field('integer', 'Final photo count for the mission named in the preceding user question')}, {'photos': 7329}, {'photos': photos}, ['conversation', 'numeric_distractors'],
         history=[{'role': 'user', 'text': 'What did Mariner 9 observe at Mars?'}, {'role': 'assistant', 'text': 'It observed Mars, Phobos and Deimos; at least 80 photos showed the moons. Mariner 10 later imaged Venus and Mercury.'}])
    depth = pointer('nepal', '/features/0/geometry/coordinates/2')
    flag = pointer('nepal', '/features/0/properties/tsunami')
    case('nepal_record', 'For the April 25, 2015 Nepal event, return the recorded magnitude, depth in kilometers, and raw tsunami flag stored in this USGS record.',
         {'magnitude': field('number', 'Nepal 2015 USGS magnitude'), 'depth_km': field('number', 'Nepal 2015 USGS geometry depth in kilometers'), 'tsunami_flag': field('integer', 'Nepal 2015 raw properties tsunami flag; not a statement about physical tsunami occurrence')},
         {'magnitude': 7.8, 'depth_km': 8.22, 'tsunami_flag': 0}, {'magnitude': mags['nepal'], 'depth_km': depth, 'tsunami_flag': flag}, ['json', 'array_pointer', 'zero'])
    stations = pointer('sumatra', '/features/0/properties/nst')
    case('sumatra_stations', 'What station count is recorded as nst for the December 26, 2004 Sumatra earthquake?',
         {'stations': field('integer', 'Sumatra 2004 recorded nst station count')}, {'stations': 601}, {'stations': stations}, ['json', 'pointer_selection'])
    null = pointer('nepal', '/features/0/properties/nst')
    case('raw_null', 'Return the raw nullable nst field for the April 25, 2015 Nepal earthquake.',
         {'nst': field('integer', 'Nepal 2015 raw nullable nst property', True)}, {'nst': None}, {'nst': null}, ['json', 'raw_null'])
    case('unknown_count', 'How many stations were used for the April 25, 2015 Nepal earthquake, according to its nst field?',
         {'stations': field('integer', 'Nepal 2015 station count; an unknown is not a numeric count')}, {}, {}, ['json', 'unknown_count'], status='insufficient_evidence')
    case('unspecified_flyby', 'At what closest range in kilometers did Mariner 10 fly by Mercury?',
         {'range_km': field('integer', 'Mariner 10 Mercury flyby closest range in kilometers')}, {}, {}, ['ambiguous', 'multiple_events'], status='ambiguous',
         alternatives=[{'fields': {'range_km': v}, 'support_set': refs} for v, refs in zip([703, 48069, 327], mercury)])
    case('absent_fact', 'How many humans traveled aboard Mariner 10, according to an explicit crew-count statement in these sources?',
         {'crew': field('integer', 'Explicitly reported Mariner 10 human crew count; do not infer from spacecraft type')}, {}, {}, ['absent_fact', 'no_inference'], status='insufficient_evidence')
    assert len(data['cases']) == 16
    for name, value in [('dataset.json', data), ('requests.json', requests)]:
        (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    build()
