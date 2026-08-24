# The evidence model

Why QMHP-CEM's stubs raise instead of returning numbers.

## The failure mode being prevented

The tempting shape for an unimplemented physics model is to return the frozen
reference value — the dressed root is 4.301974466 GHz, after all, so why not
return it?

Because that value is `MASTER-FROZEN` for the *nominal* Branch-A device, not
`SOLVED` for *this candidate*. Returning it would let a gate emit `PASS` on
evidence that was never computed for the thing being evaluated. The candidate
would then carry a `PASS` into an append-only, SHA-256-hashed record, and
nothing downstream could tell it apart from a real result.

So `models/` raises `PhysicsNotImplemented`, the pipeline records the quantity
as unavailable, and the dependent gate reports `INCOMPLETE`.

## Consequences you will see

A full mock sweep ends `INCOMPLETE`, not `NO_FEASIBLE_DESIGN_FOUND`. Those are
different claims:

- `NO_FEASIBLE_DESIGN_FOUND` — every candidate was adjudicated and none
  survived. A real scientific result.
- `INCOMPLETE` — candidates could not be adjudicated. No claim either way.

Reporting the second as the first would overstate what the computation
established, so `_batch_outcome()` keeps them separate.

## Where the boundary is enforced

The hardware boundary (spec §2.3) is enforced redundantly on purpose:

1. `master/validation_gates.yaml` omits `PASS` from hardware gates' allowed
   statuses — data, not code.
2. `Gate.evaluate()` rejects any status outside the frozen allowed list —
   catches a gate implementation that returns the wrong thing.
3. `GateResult.__init__` refuses to construct a `PASS` for a hardware-required
   gate without `MEASURED` evidence — catches anything that bypasses the gate
   classes entirely.

A single-layer check would be defeated by a plausible-looking refactor. Three
layers means the invariant has to be broken deliberately.

## Values that look like physics but are not

Some things are conventions rather than physics, and those *are* implemented:

- the tolerance RNG draw stream (a declared convention: `default_rng`, 2%
  sigma, `EC -> EJ -> EL` order);
- the 13 MHz collision comparison;
- the 34/36 dB filter comparison;
- the 10% coupling-extraction consistency rule;
- the Wilson score interval.

Each compares or transforms already-known quantities. None of them computes a
Hamiltonian.

## The 13 MHz boundary

The frozen rule is `>= 13 MHz`, so an exact 13.000 MHz separation passes.
Computing that separation as a difference of two GHz-scale floats can land it
at 12.999999999999789 MHz, which would emit a spurious `FAIL` on a HARD gate.
`models.collision.BOUNDARY_ATOL_MHz` (1e-9 MHz) exists solely to make the
frozen boundary behave as specified. It is classified `ENGINEERING-RULE` and is
roughly nine orders of magnitude below any physically meaningful separation.
