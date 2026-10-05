import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_70 = ROOT / "examples" / "refractor-70-400.json"
EXAMPLE_80 = ROOT / "examples" / "refractor-80-600.json"


@pytest.fixture
def data70() -> dict:
    return json.loads(EXAMPLE_70.read_text())
