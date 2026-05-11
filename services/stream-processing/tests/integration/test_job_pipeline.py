import importlib.util
from pathlib import Path
import sys
from unittest.mock import MagicMock, call, patch

import pytest


def _load_job_module():
    module_path = Path(__file__).resolve().parents[2] / "flink" / "job.py"
    spec = importlib.util.spec_from_file_location("flink_job_cr1_integration", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules["flink_job_cr1_integration"] = module
    spec.loader.exec_module(module)
    return module


class RecordingRedisSink:
    def __init__(self):
        self.published = []

    def publish(self, value):
        self.published.append(value)


class RecordingInfluxSink:
    def __init__(self):
        self.writes = []

    def write(self, measurement, data):
        self.writes.append((measurement, data))


@pytest.mark.integration
def test_cleaned_event_is_published_to_redis_and_influx():
    job = _load_job_module()
    cache = job.RuntimeCache(routes={"R1": [(6.9, 79.9), (6.91, 79.91)]})
    redis_sink = RecordingRedisSink()
    influx_sink = RecordingInfluxSink()

    wrapper = job.classify_event_record(
        {"busId": "B1", "routeId": "R1", "lat": 7.2, "lon": 79.9, "speed": 25.0},
        cache,
    )

    assert wrapper["kind"] == "cleaned"
    assert wrapper["payload"]["on_route"] is False
    assert wrapper["payload"]["route_deviation_meters"] > 50.0

    result = job.publish_cleaned_event(wrapper["payload"], redis_sink, influx_sink)

    assert result == wrapper["payload"]
    assert redis_sink.published == [wrapper["payload"]]
    assert influx_sink.writes == [("telemetry", wrapper["payload"])]


@pytest.mark.integration
def test_lifecycle_event_updates_cache_before_raw_classification():
    job = _load_job_module()
    cache = job.RuntimeCache()

    job.apply_lifecycle_event(
        {
            "event": "TRIP_STARTED",
            "busId": "B1",
            "tripId": "T1",
            "routeId": "R1",
            "timestamp": "2026-05-09T10:00:00Z",
        },
        cache,
    )

    wrapper = job.classify_event_record(
        {"busId": "B1", "lat": 6.9, "lon": 79.9, "speed": 20.0},
        cache,
    )

    assert cache.active_trips["B1"]["tripId"] == "T1"
    assert wrapper["kind"] == "cleaned"
    assert wrapper["payload"]["tripId"] == "T1"
    assert wrapper["payload"]["routeId"] == "R1"
    assert wrapper["payload"]["trip_status"] == "active"


@pytest.mark.integration
def test_malformed_raw_event_is_classified_invalid():
    job = _load_job_module()

    wrapper = job.classify_event_record("not-json", job.RuntimeCache())

    assert wrapper["kind"] == "invalid"
    assert wrapper["payload"]["_invalid_reason"] == "MALFORMED_JSON"


@pytest.mark.integration
def test_main_wires_cleaned_side_effects_and_kafka_sinks():
    job = _load_job_module()

    mock_env = MagicMock()
    raw_stream = MagicMock()
    lifecycle_stream = MagicMock()
    classified_stream = MagicMock()
    cleaned_stream = MagicMock()
    invalid_stream = MagicMock()
    cleaned_sink = MagicMock()
    invalid_sink = MagicMock()
    redis_sink = RecordingRedisSink()
    influx_sink = RecordingInfluxSink()

    job.StreamExecutionEnvironment = MagicMock()
    job.StreamExecutionEnvironment.get_execution_environment.return_value = mock_env
    mock_env.add_source.side_effect = [raw_stream, lifecycle_stream]

    raw_stream.name.return_value = raw_stream
    lifecycle_stream.name.return_value = lifecycle_stream
    raw_stream.map.return_value = classified_stream
    classified_stream.name.return_value = classified_stream
    classified_stream.filter.side_effect = [cleaned_stream, invalid_stream]
    cleaned_stream.map.return_value = cleaned_stream
    invalid_stream.map.return_value = invalid_stream
    cleaned_stream.name.return_value = cleaned_stream
    invalid_stream.name.return_value = invalid_stream
    cleaned_stream.sink_to.return_value = cleaned_stream
    invalid_stream.sink_to.return_value = invalid_stream

    with patch.object(job, "fetch_startup_cache", return_value=job.RuntimeCache()) as mock_cache, \
        patch.object(job, "build_raw_telemetry_source", return_value=MagicMock()) as mock_raw_source, \
        patch.object(job, "build_lifecycle_event_source", return_value=MagicMock()) as mock_lifecycle_source, \
        patch.object(job, "build_cleaned_telemetry_sink", return_value=cleaned_sink) as mock_cleaned_sink, \
        patch.object(job, "build_invalid_telemetry_sink", return_value=invalid_sink) as mock_invalid_sink, \
        patch.object(job, "build_redis_live_sink", return_value=redis_sink) as mock_redis_sink, \
        patch.object(job, "build_influx_history_sink", return_value=influx_sink) as mock_influx_sink:
        job.main()

    mock_cache.assert_called_once()
    mock_raw_source.assert_called_once()
    mock_lifecycle_source.assert_called_once()
    mock_cleaned_sink.assert_called_once()
    mock_invalid_sink.assert_called_once()
    mock_redis_sink.assert_called_once()
    mock_influx_sink.assert_called_once()
    mock_env.add_source.assert_has_calls([call(mock_raw_source.return_value), call(mock_lifecycle_source.return_value)])
    assert raw_stream.map.call_count == 1
    assert lifecycle_stream.map.call_count == 1
    assert classified_stream.filter.call_count == 2
    assert cleaned_stream.map.call_count == 3
    assert cleaned_stream.sink_to.call_count == 1
    assert invalid_stream.map.call_count == 2
    assert invalid_stream.sink_to.call_count == 1
    mock_env.execute.assert_called_once_with("OnTime CR1 Telemetry Processing")
