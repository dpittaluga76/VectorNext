"""Annotation v2: whitespace gaps only; T11's original scorer is unchanged."""
from evals.score import Scorer as LegacyScorer, interval_covered


class Scorer(LegacyScorer):
    def coverage(self, items, ids):
        ids = list(ids)
        result = super().coverage(items, ids)
        for identifier in ids:
            ref = self.gold[identifier]
            if ref['locator']['kind'] != 'text':
                continue
            doc = self.documents.get(ref['document_id'])
            ranges = []
            for item in items:
                if not doc or item['key']['document_id'] != ref['document_id'] or item['key']['revision'] != doc['revision']:
                    continue
                for source in item['sources']:
                    if source['revision'] == doc['revision'] and 'Text' in source['locator']:
                        span = source['locator']['Text']['bytes']
                        ranges.append((span['start'], span['end']))
            covered = all(interval_covered(start, end, ranges) for start, end in ref['content_runs'])
            result[identifier]['location'] = covered
            result[identifier]['covered'] = covered
        return result

    def case(self, case, report):
        result = super().case(case, report)
        # A complete record alone is not credit for selecting the correct JSON field.
        for name, proof in report['answer']['fields'].items():
            item = next(e for e in report['evidence'] if e['id'] == proof['evidence_id'])
            if item['record'] is None:
                continue
            actual = {s['locator']['Json']['pointer'] + proof['pointer']
                      for s in item['sources'] if 'Json' in s['locator'] and proof['pointer'] is not None}
            refs = case['expected'].get('field_sources', {}).get(name, [])
            result['proofs'][name]['gold_source_overlap'] = any(
                self.gold[r]['document_id'] == item['key']['document_id']
                and self.gold[r]['locator'].get('pointer') in actual for r in refs)
        result['supported_with_annotated_proofs'] = (result['answer_correct'] and result['expected_status'] == 'supported'
            and all(p['gold_source_overlap'] for p in result['proofs'].values()))
        return result
