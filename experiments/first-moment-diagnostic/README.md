# First-moment diagnostic on N2R — PREPARED, NOT APPROVED, NOT EXECUTED

Preparation of the direct evaluation of `A = Re(f_free^H M_free^-1 f_free)/L`
on N2R's constrained Nédélec space. Nothing here runs Palace; see
`docs/coupled-candidate/first-moment-diagnostic.md`.

| file | what |
|---|---|
| `reference_model.py` → `reference_model.json` | the algebra of the diagnostic against the pinned source, verified on synthetic fixtures |
| `prepare.py` → `config.candidate.json`, `config.delta.txt`, `proposal.json` | N2R's solved config with the literal delta; the one execution proposal; the saved moments recomputed from committed columns |
| `evaluate_record.py` → `fixture_evaluation.json` | the post-run evaluator, exercised on the synthetic fixture only |
| `../../docker/patches/first-moment-diagnostic.patch` | the Palace patch (applies to v0.13.0 `a61c8cbe`; verified with `git apply --check`) |
| `../../docker/palace-first-moment.Dockerfile` | the production Dockerfile plus the patch step; built by no workflow |
