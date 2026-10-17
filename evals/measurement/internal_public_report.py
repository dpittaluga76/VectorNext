"""Aggregate-only publication. Exposed candidate content/IDs never leave the run."""
import argparse
from collections import Counter
from pathlib import Path

from .families import digest, load
from .internal_runtime import save


def compact(result):
    return {k:result[k] for k in ('arm','split','representation','primary','views','latency','stages',
                                'model_calls','input_tokens','original_label_view','missing_capture_count')} | {
        'controls':{model:{k:v for k,v in control.items() if k!='cases'}
                    for model,control in result['controls'].items()},
        'projection_issue_count':len(result['projection_issues'])}


def publish(root,scores,oracles,attribution,output):
    if output.exists():raise ValueError('Publication must use a new directory')
    output.mkdir(parents=True)
    freeze=load(root/'execution-freeze.json')
    bindings=load(root/'bindings.json')
    public={'classification':'internal_exposed_pilot','independent_review':False,'blind_holdout':False,
        'default_model':'nuextract','default_strategy':'ranked_30_20_5',
        'execution_freeze_sha256':digest((root/'execution-freeze.json').read_bytes()),'source_commit':freeze['commit'],
        'ingestion':dict(Counter(b['state'] for b in bindings)),
        'development':{k:compact(v) for k,v in scores['development'].items() if k!='comparisons'},
        'exposed_candidates':{k:compact(v) for k,v in scores['exposed_candidates'].items() if k!='comparisons'},
        'comparisons':{split:scores[split]['comparisons'] for split in ('development','exposed_candidates')},
        'original_table_representation':compact(scores['development_v1']),
        'oracles':{model:{variant:{k:v for k,v in result.items() if k!='cases'}
                          for variant,result in variants.items()} for model,variants in oracles.items()},
        'attribution':{k:v for k,v in attribution.items() if k!='cases'},
        'limitations':['147 primary items; below original 150-item floor and prospective 520 sealed requirement',
            'all 60 candidates exposed; no independent review or blind holdout',
            'comprehensive corporate lineage uncertified',
            'unpaired clean-render PDF text ingestion; JSON structured-table QA',
            'source-only oracle selection is an internal deterministic approximation',
            'unlisted variants remain incorrect; no retrospective scoring-list changes']}
    save(output/'results.json',public)
    lines=['# T39 internal measurement results','',
        'NuExtract and ranked 30/20/5 remain the defaults. This is an exposed internal pilot, '
        'not an independently validated benchmark or evidence for strategy promotion.','',
        'The pilot measures the evaluation harness, exact factual extraction, source grounding '
        'and observable failure modes on reviewed public-source adaptations.','',
        '| Split / strategy | Primary correct | Median / p95 seconds | Answered wrong | Errors |',
        '| --- | ---: | ---: | ---: | ---: |']
    def seconds(value):return 'unrecorded' if value is None else f'{value/1000:.2f}'
    for split in ('development','exposed_candidates'):
        for arm,result in public[split].items():
            p=result['primary'];v=result['views']['primary_direct_extraction'];t=result['latency']
            lines.append(f"| {split} / {arm} | {p['correct']}/{p['n']} | {seconds(t['median'])} / {seconds(t['p95'])} | "
                         f"{v['outcomes'].get('answered_wrong',0)} | {v['outcomes'].get('system_error',0)} |")
    lines+=['','Accuracy rows use the primary tier. Latency covers every planned case in that split '
            '(including derived/stress and failures where observed), not only successful answers. '
            'Paired primary latency, family-bootstrap intervals and Wilson intervals are in `results.json`.','',
            '| Model / oracle fields | Primary roster | Validator on correct | Validator off correct | Retained states |',
            '| --- | ---: | ---: | ---: | --- |']
    for model,variants in public['oracles'].items():
        for variant,v in variants.items():
            lines.append(f"| {model} / {variant} | {v['primary_n']} | {v['validator_on_correct']} | "
                         f"{v['validator_off_correct']} | {v['states']} |")
    lines+=['','Unavailable oracle definitions/plans and budget failures stay visible. Gold-field '
            'interventions are not applicable to negative cases; consult states rather than treating '
            'that column as ordinary end-to-end accuracy. Validator-off outputs are untrusted diagnostics. '
            'A gold-matching rejection has not been independently established as a validator defect.','',
            'Closed-book-adjusted scores, original-label scores, the v1 table-representation ablation, '
            'derived/stress counts, separate grounding results and stage/token distributions are retained '
            'in the aggregate JSON. Unknown controls block the adjusted headline; no successful-control '
            'items are silently discarded from the all-item score.','',
            'Failure attribution allows multiple causes and reports unobserved categories. It does not '
            'claim a unique root cause or independent semantic proof review.','',
            'Not evidence of performance on original publisher layouts, scanned pages, charts or PDF tables.','',
            'Not evidence of table-extraction performance, only of reading from supplied structured cells.','',
            'Not generalizable to enterprise or domain documents beyond Wikipedia text, arXiv-style papers and financial-report tables.','',
            'Not a measurement of the NASA/USGS track. Those historical results remain separate.','',
            'The original repository holdout was not used. Raw responses, exact values, errors, attempt '
            'records, resource samples and candidate-level results remain in the private execution directory. '
            'No prompts, labels or frozen alternatives were tuned from these outputs.','',
            'Reproduction: [internal runtime guide](../../../evals/measurement/internal-runtime-guide.md). '
            f"Execution source commit: `{freeze['commit']}`. Private freeze SHA-256: "
            f"`{public['execution_freeze_sha256']}`.",'']
    (output/'README.md').write_text('\n'.join(lines),encoding='utf8',newline='\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('root','scores','oracles','attribution','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();publish(a.root,load(a.scores),load(a.oracles),load(a.attribution),a.output)


if __name__=='__main__':main()
