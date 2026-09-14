"""Shared fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from contracts import Candidate
from contracts.master import REPO_ROOT
from contracts.sweep import SweepDefinition


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def seed_candidate() -> Candidate:
    with (REPO_ROOT / "config" / "object001_seed.yaml").open() as fh:
        return Candidate.model_validate(yaml.safe_load(fh))


@pytest.fixture
def object001_sweep() -> SweepDefinition:
    with (REPO_ROOT / "sweeps" / "object001_grid.yaml").open() as fh:
        return SweepDefinition.model_validate(yaml.safe_load(fh))
