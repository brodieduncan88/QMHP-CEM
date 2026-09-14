"""Hardware-gated objects (spec §6.6, §6.7).

None of these can emit PASS in v0.1. The invariant is enforced in three
independent places, deliberately:

1. ``master/validation_gates.yaml`` omits PASS from their allowed statuses;
2. :class:`evaluator.base.Gate.evaluate` rejects a status outside that list;
3. :class:`contracts.results.GateResult` refuses to construct a PASS for a
   hardware-required gate without ``MEASURED`` evidence.

Defeating the boundary would require breaking all three.
"""

from __future__ import annotations

from evaluator.base import HardwareGate


class P6E6JointGate(HardwareGate):
    """``P6E6_JOINT`` — measured P6-E6 joint acceptance (spec §6.6).

    All four frozen conditions are required: measured f >= f*, p_induced <=
    1e-3, complete Pu <= 1e-2, and logical benefit at >= 95% confidence on an
    equal-wall-clock basis. v0.1 has none of the measured inputs.
    """

    gate_id = "P6E6_JOINT"
    requires = (
        "measured f >= f*, p_induced <= 1e-3, complete Pu <= 1e-2 and >= 95% "
        "logical-advantage confidence at equal wall-clock — all four conditions"
    )


class P0dGate(HardwareGate):
    gate_id = "P0D"
    requires = "measured sink reset / process validation"


class P1Gate(HardwareGate):
    gate_id = "P1"
    requires = "measured direct unlocated bypass acceptance"


class P3Gate(HardwareGate):
    gate_id = "P3"
    requires = "measured trajectory coherence / bias data"


class P5Gate(HardwareGate):
    gate_id = "P5"
    requires = "measured destination-resolved erasure conversion"


class P7Gate(HardwareGate):
    gate_id = "P7"
    requires = "measured unconditional logical advantage"
