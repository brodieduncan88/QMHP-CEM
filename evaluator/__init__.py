"""QMHP-CEM gate evaluator (spec §6).

Gates compare computed quantities against thresholds frozen in
``master/validation_gates.yaml``. They never compute physics, never invent a
threshold, and never close a hardware gate on simulated evidence.
"""

from evaluator.base import Gate, GateInputs, HardwareGate
from evaluator.candidate_evaluator import GATE_TYPES, evaluate_candidate, roll_up

__all__ = [
    "GATE_TYPES",
    "Gate",
    "GateInputs",
    "HardwareGate",
    "evaluate_candidate",
    "roll_up",
]
