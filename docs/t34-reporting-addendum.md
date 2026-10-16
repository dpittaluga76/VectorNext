# T34 — post-run reporting correction

Recorded after the sole measured run `data/t34/pilot-v1`, without further inference. The original `experiments/t34/score.py`, input freeze, execution freeze, source ZIP, request/response bytes, labels and scoring rules remain unchanged.

The original summary command raised `KeyError: 'text'` on Ministral's rejected prose answers. The reused T32 scorer assumes every diagnostic evidence entry contains passage text. The API's rejected-answer envelope instead records source metadata and an explicitly unvalidated draft. It must not be treated as a supported answer or fabricated passage coverage.

`experiments/t34/report.py` preserves the frozen reporter's successful-response scoring and applies an early failure result to non-200 responses. It retains the error message, leaves unrecorded coverage unknown, and never accepts rejected drafts. Blocked preflight cases remain failures in the six-per-arm denominator, without latency. The existing PDF review is unchanged. This is a reporting robustness correction, not a revised quality criterion or a request retry.

Use the corrected offline command:

```powershell
python -m experiments.t34.report --run pilot-v1 --output data/t34/pilot-v1/summary.json
```

The separate module intentionally leaves frozen execution code reproducible. Its hash and this addendum are recorded in the summary; the original summary command's failure remains documented here. Regression checks cover text-free diagnostics, rejected drafts, unavailable coverage and equality with the frozen scorer on successful responses. No model settings, prompt, evidence selection or labels were changed after observing results.
