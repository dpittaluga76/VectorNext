"""Read-only T24 fixture validation using the preserved source-bound contract."""
from pathlib import Path
import json
from evals.evidence.validate import validate as validate_inputs


def validate():
    result=validate_inputs(Path('evals/selection'))
    assert result['sources']==10 and result['facts']==22 and result['fact_requirements']==37
    return result


if __name__=='__main__':print(json.dumps(validate(),indent=2))
