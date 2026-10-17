"""Verify a reviewer-completed proposal; hashes are integrity, not proof of independence."""
import argparse
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath


def sha(raw): return hashlib.sha256(raw).hexdigest()


def checked_file(root,name):
    rel=PurePosixPath(name)
    if rel.is_absolute() or not rel.parts or any(p in ('..','.') for p in rel.parts) or '\\' in name or ':' in name:
        raise ValueError('invalid manifest path')
    path=root.joinpath(*rel.parts)
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('manifest path escapes or is not a file')
    return path


def verify(root,review_path):
    raw=(root/'manifest.json').read_bytes(); manifest=json.loads(raw)
    review=json.loads(review_path.read_text(encoding='utf-8'))
    if review.get('approved') is not True or review.get('independent_of_implementation') is not True:
        raise ValueError('independent approval is pending')
    if not all(isinstance(review.get(k),str) and review[k].strip() for k in ('reviewer','custodian','date')):
        raise ValueError('named reviewer/custodian/date required')
    if review.get('package_manifest_sha256')!=sha(raw): raise ValueError('review is for a different manifest')
    if review.get('custody_transferred') is not True: raise ValueError('sealed custody transfer required')
    for name,expected in manifest['files'].items():
        if sha(checked_file(root,name).read_bytes())!=expected: raise ValueError('package file changed: '+name)
    if review.get('unresolved'): raise ValueError('unresolved independent review findings')
    cases=review['cases']
    if len({r['case_id'] for r in cases})!=len(cases): raise ValueError('duplicate reviewed case')
    requests={}
    for split in ('development','sealed'):
        for r in json.loads(checked_file(root,split+'/requests.json').read_text(encoding='utf-8')):
            if r['case_id'] in requests: raise ValueError('duplicate public request')
            requests[r['case_id']]=r
    if set(requests)!={r['case_id'] for r in cases}: raise ValueError('review must account for every public case exactly once')
    primary=[r for r in cases if r['capability']=='direct_extraction' and r['accepted']]
    if not 150<=len(primary)<=300: raise ValueError('primary question count outside 150–300')
    families=defaultdict(set)
    for r in primary:
        request=requests[r['case_id']]
        if any(r[k]!=request[k] for k in ('split','family','format','structure')):
            raise ValueError('reviewed metadata differs; create a corrected successor package before approval')
        if r['split'] not in ('development','sealed') or not r['family']: raise ValueError('missing split/family')
        families[r['family']].add(r['split'])
        if not r.get('exact_values_reviewed') or not r.get('support_reviewed') or not r.get('scope_reviewed'):
            raise ValueError('missing case-level evidence/value/scope review')
        if not isinstance(r.get('gold_fields'),dict) or not r['gold_fields']:
            raise ValueError('independently approved field definitions required')
        if r['expected']=='supported' and (not r.get('answer_variants') or not r.get('support_sets')):
            raise ValueError('approved typed alternatives and support sets required')
        if r['format']=='pdf' and not r.get('pdf_visually_reviewed'): raise ValueError('PDF visual review pending')
        if r['expected'] not in ('supported','ambiguous','insufficient_evidence'): raise ValueError('invalid primary expected status')
    if any(len(s)!=1 for s in families.values()): raise ValueError('source family leaks across splits')
    neg=sum(r['expected']!='supported' for r in primary)/len(primary)
    if not .25<=neg<=.30: raise ValueError('negative proportion outside 25–30%')
    sealed=[r for r in primary if r['split']=='sealed']
    if len(sealed)/len(primary)<.30: raise ValueError('fewer than 30% sealed questions')
    for split in ('development','sealed'):
        if len({r['family'] for r in primary if r['split']==split})<20: raise ValueError('fewer than 20 source families')
    formats=Counter(r['format'] for r in primary)
    if any(formats[f]<20 for f in ('txt','pdf','json')): raise ValueError('insufficient format coverage')
    if sum(r['structure']=='table' for r in primary)<20: raise ValueError('insufficient table coverage')
    # Attestation covers a complete manifest. A different execution freeze must
    # subsequently pin runtime images, code, actual ingestion and public inputs.
    return {'status':'independent_review_accepted','reviewer':review['reviewer'],
            'custodian':review['custodian'],'manifest_sha256':sha(raw),
            'review_sha256':sha(review_path.read_bytes()),'questions':len(primary),
            'sealed_questions':len(sealed),'negative_fraction':neg,'formats':dict(formats)}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('package',type=Path);p.add_argument('review',type=Path)
    a=p.parse_args();print(json.dumps(verify(a.package,a.review),indent=2))


if __name__=='__main__': main()
