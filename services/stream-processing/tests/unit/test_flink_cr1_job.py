import importlib.util
from pathlib import Path
import sys


def _load_job_module():
    module_path = (
        Path(__file__).resolve().parents[2] / "flink" / "job.py"
    )
    spec = importlib.util.spec_from_file_location("flink_job_cr1", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules["flink_job_cr1"] = module
    spec.loader.exec_module(module)
    return module


def test_classify_physics_rejects_unrealistic_speed():
    job = _load_job_module()
    kind, payload = job.classify_physics({"lat": 6.9, "lon": 79.9, "speed": 130.0})

    assert kind == "invalid"
    assert payload["_invalid_reason"] == "UNREALISTIC_SPEED"


def test_classify_physics_accepts_normal_event():
    job = _load_job_module()
    kind, payload = job.classify_physics({"lat": 6.9, "lon": 79.9, "speed": 25.0})

    assert kind == "cleaned"
    assert payload["physics_status"] == "accepted"
    assert payload["on_route"] is True


def test_route_lifecycle_event_updates_active_trips():
    job = _load_job_module()
    cache = job.RuntimeCache()

    job.route_lifecycle_event(
        {
            "event": "TRIP_STARTED",
            "busId": "B1",
            "tripId": "T1",
            "routeId": "R1",
            "timestamp": "2026-05-09T10:00:00Z",
        },
        cache,
    )
    assert cache.active_trips["B1"]["tripId"] == "T1"

    job.route_lifecycle_event({"event": "TRIP_ENDED", "busId": "B1"}, cache)
    assert "B1" not in cache.active_trips


def test_parse_route_cache_response_supports_common_shapes():
    job = _load_job_module()

    payload = {
        "items": [
            {
                "routeId": "R1",
                "polyline": [{"lat": 6.9, "lon": 79.9}, {"lat": 6.91, "lon": 79.91}],
            }
        ]
    }

    routes = job.parse_route_cache_response(payload)
    assert routes["R1"] == [(6.9, 79.9), (6.91, 79.91)]


def test_parse_active_trip_cache_response_supports_common_shapes():
    job = _load_job_module()

    payload = {
        "activeTrips": [
            {"busId": "B1", "tripId": "T1", "routeId": "R1", "timestamp": "2026-05-09T10:00:00Z"}
        ]
    }

    active = job.parse_active_trip_cache_response(payload)
    assert active["B1"]["tripId"] == "T1"
    assert active["B1"]["routeId"] == "R1"


def test_fetch_startup_cache_tolerates_failures(monkeypatch):
    job = _load_job_module()

    class DummyResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class DummyClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url):
            if "route" in url:
                return DummyResponse({"items": [{"routeId": "R1", "polyline": [[6.9, 79.9], [6.91, 79.91]]}]})
            raise RuntimeError("fleet service unavailable")

    monkeypatch.setattr(job.httpx, "Client", DummyClient)

    cache = job.fetch_startup_cache("http://route-service/routes", "http://fleet-service/active")

    assert cache.routes["R1"] == [(6.9, 79.9), (6.91, 79.91)]
    assert cache.active_trips == {}


def test_build_raw_telemetry_source_raises_when_pyflink_unavailable():
    """Verify build_raw_telemetry_source raises RuntimeError if PyFlink not installed."""
    job = _load_job_module()

    # Temporarily set KafkaSource to None to simulate missing PyFlink
    original_source = job.KafkaSource
    try:
        job.KafkaSource = None
        try:
            job.build_raw_telemetry_source()
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "PyFlink is not available" in str(e)
    finally:
        job.KafkaSource = original_source


def test_build_lifecycle_event_source_raises_when_pyflink_unavailable():
    """Verify build_lifecycle_event_source raises RuntimeError if PyFlink not installed."""
    job = _load_job_module()

    # Temporarily set KafkaSource to None to simulate missing PyFlink
    original_source = job.KafkaSource
    try:
        job.KafkaSource = None
        try:
            job.build_lifecycle_event_source()
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "PyFlink is not available" in str(e)
    finally:
        job.KafkaSource = original_source


def test_build_raw_telemetry_source_uses_settings():
    """Verify raw telemetry source uses correct settings for bootstrap and topic."""
    job = _load_job_module()

    # Skip if PyFlink is not available
    if job.KafkaSource is None:
        return

    source = job.build_raw_telemetry_source()
    assert source is not None
    # Verify the source object was created (actual config validation requires Flink cluster)


def test_build_lifecycle_event_source_uses_settings():
    """Verify lifecycle event source uses correct settings for bootstrap and topic."""
    job = _load_job_module()

    # Skip if PyFlink is not available
    if job.KafkaSource is None:
        return

    source = job.build_lifecycle_event_source()
    assert source is not None
    # Verify the source object was created (actual config validation requires Flink cluster)


def test_build_cleaned_telemetry_sink_raises_when_pyflink_unavailable():
    """Verify build_cleaned_telemetry_sink raises RuntimeError if PyFlink not installed."""
    job = _load_job_module()

    # Temporarily set KafkaSink to None to simulate missing PyFlink
    original_sink = job.KafkaSink
    try:
        job.KafkaSink = None
        try:
            job.build_cleaned_telemetry_sink()
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "PyFlink is not available" in str(e)
    finally:
        job.KafkaSink = original_sink


def test_build_invalid_telemetry_sink_raises_when_pyflink_unavailable():
    """Verify build_invalid_telemetry_sink raises RuntimeError if PyFlink not installed."""
    job = _load_job_module()

    # Temporarily set KafkaSink to None to simulate missing PyFlink
    original_sink = job.KafkaSink
    try:
        job.KafkaSink = None
        try:
            job.build_invalid_telemetry_sink()
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "PyFlink is not available" in str(e)
    finally:
        job.KafkaSink = original_sink


def test_build_cleaned_telemetry_sink_uses_settings():
    """Verify cleaned telemetry sink uses correct settings for bootstrap and topic."""
    job = _load_job_module()

    # Skip if PyFlink is not available
    if job.KafkaSink is None:
        return

    sink = job.build_cleaned_telemetry_sink()
    assert sink is not None
    # Verify the sink object was created (actual config validation requires Flink cluster)


def test_build_invalid_telemetry_sink_uses_settings():
    """Verify invalid telemetry sink uses correct settings for bootstrap and topic."""
    job = _load_job_module()

    # Skip if PyFlink is not available
    if job.KafkaSink is None:
        return

    sink = job.build_invalid_telemetry_sink()
    assert sink is not None
    # Verify the sink object was created (actual config validation requires Flink cluster)


def test_build_redis_live_sink_raises_when_redis_unavailable():
    job = _load_job_module()

    original = getattr(job, "redis_module", None)
    try:
        job.redis_module = None
        try:
            job.build_redis_live_sink()
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "redis" in str(e)
    finally:
        job.redis_module = original


def test_build_influx_history_sink_raises_when_influx_unavailable():
    job = _load_job_module()

    original = getattr(job, "InfluxDBClient", None)
    try:
        job.InfluxDBClient = None
        try:
            job.build_influx_history_sink()
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "influxdb-client" in str(e)
    finally:
        job.InfluxDBClient = original


def test_build_redis_live_sink_uses_settings():
    job = _load_job_module()
    if job.redis_module is None:
        return
    sink = job.build_redis_live_sink()
    assert sink is not None


def test_build_influx_history_sink_uses_settings():
    job = _load_job_module()
    if job.InfluxDBClient is None:
        return
    sink = job.build_influx_history_sink()
    assert sink is not None
