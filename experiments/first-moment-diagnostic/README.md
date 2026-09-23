# First-moment diagnostic — PREPARED, COMPILED, NOT APPROVED, NOT EXECUTED ON N2R

Preparation and synthetic qualification of the direct evaluation of
`A = Re(f_free^H M_free^-1 f_free)/L` on N2R's constrained Nédélec space. The C++
has been compiled and run here on synthetic, non-QMHP fixtures only. Nothing here
assembles, solves or reads an N2R quantity, and no `E_C` or `g` is produced. See
`docs/coupled-candidate/first-moment-diagnostic.md`.

| file | what |
|---|---|
| `reference_model.py` → `reference_model.json` | the algebra against the pinned source, the exact residual error identity, the counterexamples to the old bound, the record schema and the fail-closed evaluator |
| `synthetic_fixture.py` → `synthetic_fixture.json`, `fixtures/` | the non-QMHP fixtures and an independent Whitney assembly of the answer, with an exact constant-field self-check |
| `compiled_qualification.py` → `compiled_qualification.json` | runs the fixtures through the compiled binary and compares; refuses any config that is not a fixture |
| `run_diagnostic.py` | the launcher: wall-clock and DOF cap enforcement plus provenance capture. **PREPARED, NOT ACTIVATED** — refuses without `EXECUTION-APPROVAL.json`, which is deliberately absent |
| `prepare.py` → `config.candidate.json`, `config.delta.txt`, `proposal.json` | N2R's config with the literal delta, the required provenance, the saved moments with their printed-precision interval, and the one execution proposal |
| `evaluate_record.py` → `fixture_evaluation.json` | the post-run evaluation, exercised on fixtures only |
| `../../docker/patches/first-moment-diagnostic.patch` | the Palace patch (applies to v0.13.0 `a61c8cbe`) |
| `../../docker/palace-first-moment.Dockerfile` | the image that applies it; built by no workflow |
