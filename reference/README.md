# reference/

Vendored upstream artifacts. **Read-only provenance material — not QMHP-CEM code.**

## `v1_5_8f_release_bundle/`

The QMHP-CoPro v1.5.8f release bundle, vendored verbatim. It carries its own
integrity manifest, `qmhp_v158f_amdc_manifest.json`, listing 29 files.

Verification status in this repository:

| | |
|---|---|
| Files listed in the AMD-C manifest | 29 |
| Present and hash-verified | **27** |
| Hash mismatches | **0** |
| Listed but not shipped in the bundle | 2 (`base_v1_5_8e_117pp_operative.pdf`, `base_v1_5_8e_109pp_provenance.pdf`) |

Re-verify at any time:

```bash
uv run python scripts/verify_reference_bundle.py
```

### What it contains

- `qmhp_v158f_readout_replication.py` — the **third independent implementation**
  of the readout/collision screen. This is the authority QMHP-CEM's physics
  models are implemented against (see `models/`).
- `qmhp_v158e_core.py`, `qmhp_v158e_run.py`, `qmhp_v158e_analyse.py` — the QEC
  layer and its run/analysis drivers.
- `qmhp_v158f_t12_t13.py`, `build_master_figures.py`, `wp_figures.py` — T.12 /
  T.13 and figure generation.
- `expected_outputs.json` — declared expected values for the release.
- `ensemble_*.json`, `t12_*.json`, `t13_*.json`, `qmhp_v158e_runs.json` — run
  records.
- Two rendered PDFs (Full Edition, Master Final) and the release figures.
- `requirements.lock` — the declared runtime: Python 3.12.3, numpy 2.4.4,
  scipy 1.17.1, stim 1.16.0, PyMatching 2.4.0, matplotlib 3.10.8.

### Why it is vendored rather than referenced

QMHP-CEM's physics models must be reproducible against a fixed authority. A
bundle that lives only in someone's downloads directory cannot serve that role,
and the AMD-C manifest is only meaningful if the files it covers travel with
it.

### Rules

This directory is upstream material. Do not edit it, refactor it, reformat it,
or "fix" it. If the upstream release changes, replace the whole directory and
re-verify against the new manifest — do not patch files in place, because that
silently breaks the digest chain that makes the bundle worth vendoring.

QMHP-CEM code must not import from here at runtime. `models/` reimplements the
physics against the frozen conventions and is regression-tested against the
values this bundle produces; it does not execute vendored scripts.
