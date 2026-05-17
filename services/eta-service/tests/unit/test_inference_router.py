import datetime
import sys
from pathlib import Path

import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[2]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from models.inference_router import predict


def test_physics_model():
    outcome = predict(1000.0, 5.0, model_name="physics")
    assert outcome.model_used == "physics"
    assert outcome.result.eta_seconds == pytest.approx(200.0, rel=0.05)


def test_expressway_physics():
    outcome = predict(
        1000.0,
        5.0,
        model_name="physics",
        segment_mode="expressway",
    )
    assert outcome.segment_mode == "expressway"
    assert outcome.result.eta_seconds > 0
