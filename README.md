# QMHP-CEM

Computational evidence and audit record for the QMHP-CoPro programme.

## Contents

| Path | What it is |
|---|---|
| [`docs/v2a/`](docs/v2a/README.md) | V2A gate programme: G0 follow-up audit v0.1 deep-research assessment, the M3 prescreen registration template, reference list, and the list of audit inputs taken on report |
| [`tools/v2a/check_assessment_arithmetic.py`](tools/v2a/check_assessment_arithmetic.py) | Standard-library script that reproduces every number stated in the assessment and exits non-zero on any mismatch |
| [`tests/`](tests/) | `unittest` suite over the arithmetic script |

## Checking the arithmetic

```
python3 tools/v2a/check_assessment_arithmetic.py
python3 -m unittest discover -s tests -v
```

No third-party packages are required.
