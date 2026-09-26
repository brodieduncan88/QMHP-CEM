# QUTIP-A-READOUT-CROSSCHECK-v1: the one approved execution

This directory holds the provenance of the single approved QuTiP-A execution. The
records themselves are under `results/`. Each is committed byte for byte as written on
the owner's Mac, and each is verified against its own execution-time register:

| Record | Classification | Register |
|---|---|---|
| `results/QUTIP-A-LAUNCH-BLOCKED-20260926T025352Z/` | supporting execution provenance: the first launcher stopped at BLOCKED-PREFLIGHT; `checker_launched` false, `attempt_consumed` false | `launcher-manifest.sha256` |
| `results/QUTIP-A-MAC-MEMORY-DIAGNOSTIC-20260926T045655Z/` | supporting control provenance: a dummy-only memory-limit diagnostic, **not** a QMHP or QuTiP calculation | `SHA256SUMS` |
| `results/QUTIP-A-LAUNCHER-CONTROL-TEST-20260926T060642Z/` | supporting control provenance: pre-flight qualification with dummy probes; no checker, no receipt, no ledger | `qualification-manifest.sha256` |
| `results/QUTIP-A-READOUT-CROSSCHECK-20260926T061643Z/` | **scientific evidence**: the one execution of the pinned checker (110a2e0) | `launcher-manifest.sha256` |

None of the three supporting records is a scientific attempt.

Files here:

- `qutip_branch_a_launcher_asgrowth.py`: the launcher that produced the last two
  records (sha256 `4f34781953db2fd4791827065ef5fc7003f899b7d96069059263ac81b7b2e711`).
- `RESOURCE-RULE-APPROVAL.json`: the owner's approval of the growth rule, exactly as the
  launcher consumed it (sha256 `7d38e9de…`).
- `ATTEMPT-LEDGER.QUTIP-A-READOUT-CROSSCHECK-v1-110a2e0-attempt1.json`: the one-attempt
  ledger entry, byte for byte. The attempt is spent.
- `EXECUTION-LOG.json`: written after the run. It records the approvals, all digests,
  the timeline, the verification done, the limitations and the disclosure below.

## Final classification

| Aspect | Result |
|---|---|
| Numerical cross-check | **PASS**: 11/11 named checks, each a checker verdict against the frozen engineering thresholds |
| Execution integrity | **VERIFIED** |
| Protocol conformance | **QUALIFIED: RESOURCE-LIMIT DEVIATION** |

This is **not** an unqualified overall scientific PASS, and no tool issued an overall
scientific verdict.

The execution used the separately approved 1024 MiB **address-space-growth** control,
`QUTIP-A-MACOS-AS-GROWTH-LIMIT-v1`. It sets RLIMIT_AS, soft and hard, to the checker
process's own baseline VSZ + 1,073,741,824 bytes. It did not use the original 1024 MB
total-memory interpretation of the frozen rule `memory_limit_MB = 1024`, which could not
be applied on the Mac and was not enforced.

## What it means, and what it does not

QuTiP's independent operator/tensor assembly, built from the same CEM-exported inputs,
reproduced the CEM Branch-A Hamiltonian to 1.1e-16 GHz per entry. Every downstream
quantity agrees to between about 1e-17 and 1e-11. Differences of that size are
consistent with floating-point round-off; no error bound was derived.

What it does not establish:

- The eigensolver, the labelling rule and the observable formulas are shared with CEM,
  so agreement past the Hamiltonian is not independent confirmation.
- It says nothing about the static spectrum, EM extraction, geometry, convergence,
  hardware, the coupling g (a reference value, not geometry-derived) or the
  architecture. It covers one fixed readout frequency.
- The growth control is not a total-memory or resident-memory limit. It has not
  established that memory committed later inside regions reserved before the limit was
  applied is bounded. The checker's own memory use was not measured.

## Disclosure

While preparing this bundle, a mutation test of the integrity guard appended one byte to
the **working copy** of the execution record's `checker-output/result.json`, then
restored it. The restored file's sha256 equals the original
(`bf3b642ce850556ddea4590218a7ffd93d3af45ccdc0577edf1ebc866f9a47ee`). The record again
verifies against its launcher manifest and is byte-identical to the uploaded archive, and
no altered version was staged or committed. The guard's negative controls use synthetic
records only.
