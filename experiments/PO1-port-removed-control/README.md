# PO1: the port-removed control, prepared against N2R

**PREPARED, NOT APPROVED, NOT LAUNCHED.** Nothing here starts a run. The file
whose commit on a `palace/**` branch triggers the ladder workflow,
`.github/ladder-approval.json`, is untouched and carries no `port_control`
key. No extraction, no coupling value, no target amendment.

| file | content |
|---|---|
| `candidate.json` | the control: the operator change and its source, the corrected null-space accounting and the projector change it forces, the near-zero-frequency postprocessing hazards and what survives them, the corrected energy diagnostics and their threshold, the declared localisation rule with its inconclusive outcomes, the resources and refusals, the execution path and the single approval needed |
| `prepare.py` | builds `config.candidate.json` from N2R's **solved** config, verifying its SHA-256, asserting it round-trips through the driver's serialisation, and refusing to write unless the flattened leaf-path delta is exactly the expected set. Imports the probe points from `solvers/palace/coupled_config.py` rather than restating them |
| `config.candidate.json` | the candidate Palace config. SHA-256 `2826e78c026097aeb90dc1f50ec2b08e2afefce7ecbb43270d34b7667e0d1728` |
| `config.delta.txt` | the literal unified diff against N2R's solved config |

The analysis is in
[`docs/coupled-candidate/po1-port-removed-control.md`](../../docs/coupled-candidate/po1-port-removed-control.md).

```
uv run python experiments/PO1-port-removed-control/prepare.py
uv run pytest tests/test_port_removed_control.py
```

Both are offline: no container, no Palace invocation, nothing written under
`results/`.
