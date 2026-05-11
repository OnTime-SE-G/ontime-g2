from datetime import datetime, timezone

from app.models.training.feature_extraction import build_summary_vector


def test_build_summary_vector_computes_window_statistics():
    window = [
        {"timestamp": "2026-05-02T10:00:00Z", "speed": 10.0, "heading": 10.0},
        {"timestamp": "2026-05-02T10:00:10Z", "speed": 25.0, "heading": 40.0},
        {"timestamp": datetime(2026, 5, 2, 10, 0, 20, tzinfo=timezone.utc), "speed": 15.0, "heading": 30.0},
    ]

    summary = build_summary_vector(window)

    assert summary["sample_count"] == 3.0
    assert summary["average_speed"] == 50.0 / 3.0
    assert summary["speed_variance"] > 0.0
    assert summary["heading_variance"] > 0.0
    assert summary["max_acceleration"] > 0.0
    assert summary["min_acceleration"] < 0.0


def test_build_summary_vector_handles_small_window():
    summary = build_summary_vector([
        {"timestamp": "2026-05-02T10:00:00Z", "speed": 10.0, "heading": 10.0},
    ])

    assert summary["sample_count"] == 1.0
    assert summary["max_acceleration"] == 0.0
    assert summary["min_acceleration"] == 0.0
