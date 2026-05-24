"""Shared test fixtures."""
from pathlib import Path

import pytest


@pytest.fixture
def tmp_output(tmp_path: Path) -> Path:
    """A temporary output directory for archive tests."""
    d = tmp_path / "output"
    d.mkdir()
    return d
