import pytest
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

SERVICE_ROOT = Path(__file__).resolve().parents[2]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.transforms.enrichment import EnrichmentFunction
from app.utils.geo import get_dist_along_route

# ---------------------------------------------------------------------------
# Shared route geometry: vertical line from lat 6.0 → 7.0, lon 80.0
# Stops at 6.2, 6.4, 6.6, 6.8 (equally spaced, increasing stop_order)
# ---------------------------------------------------------------------------
_ROUTE_GEOM = [(6.0, 80.0), (7.0, 80.0)]

def _make_stop(stop_id, name, stop_order, lat):
    return {
        "id": stop_id,
        "name": name,
        "stop_order": stop_order,
        "lat": lat,
        "lon": 80.0,
        "dist_along_route": get_dist_along_route(lat, 80.0, _ROUTE_GEOM),
    }

_STOPS_R1 = [
    _make_stop(1, "Stop A", 1, 6.2),
    _make_stop(2, "Stop B", 2, 6.4),
    _make_stop(3, "Stop C", 3, 6.6),
    _make_stop(4, "Stop D", 4, 6.8),
]


@pytest.fixture
def enrichment_fn():
    fn = EnrichmentFunction()
    fn.trip_to_route_state = MagicMock()
    fn.last_ts_state = MagicMock()
    fn.route_geometries = {"R1": _ROUTE_GEOM}
    fn.route_stops = {}
    return fn


@pytest.fixture
def enrichment_fn_with_stops():
    fn = EnrichmentFunction()
    fn.trip_to_route_state = MagicMock()
    fn.last_ts_state = MagicMock()
    fn.route_geometries = {"R1": _ROUTE_GEOM}
    fn.route_stops = {"R1": _STOPS_R1}
    return fn


def _gps(lat, ts="2026-05-02T10:00:00Z"):
    return json.dumps({
        "busId": "B1", "tripId": "T1",
        "lat": lat, "lon": 80.0,
        "speed": 10.0, "timestamp": ts,
    })


# ---------------------------------------------------------------------------
# Existing tests (unchanged)
# ---------------------------------------------------------------------------

def test_process_lifecycle_event(enrichment_fn):
    ctx = MagicMock()
    event = json.dumps({
        "event": "TRIP_STARTED",
        "busId": "B1",
        "tripId": "T1",
        "routeId": "R1"
    })

    gen = enrichment_fn.process_element(event, ctx)
    list(gen) if gen else None

    print(f"\n>>> STATE UPDATED: trip_to_route_state.put('T1', 'R1') called successfully.")
    enrichment_fn.trip_to_route_state.put.assert_called_with("T1", "R1")

def test_process_telemetry_enrichment(enrichment_fn):
    ctx = MagicMock()
    enrichment_fn.trip_to_route_state.get.return_value = "R1"
    enrichment_fn.last_ts_state.value.return_value = None

    telemetry = json.dumps({
        "busId": "B1",
        "tripId": "T1",
        "lat": 6.5,
        "lon": 80.0,
        "speed": 40.0,
        "timestamp": "2026-05-02T10:00:00Z"
    })

    gen = enrichment_fn.process_element(telemetry, ctx)
    results = list(gen)

    assert len(results) == 1
    enriched = json.loads(results[0])
    print(f"\n>>> ENRICHED TELEMETRY OUTPUT: {json.dumps(enriched, indent=2)}")
    assert enriched["routeId"] == "R1"
    assert "routeProgressPct" in enriched
    assert enriched["routeProgressPct"] == pytest.approx(50.0, rel=0.1)

def test_process_deduplication(enrichment_fn):
    ctx = MagicMock()
    enrichment_fn.last_ts_state.value.return_value = "2026-05-02T10:05:00Z"

    old_telemetry = json.dumps({
        "busId": "B1",
        "tripId": "T1",
        "lat": 6.5,
        "lon": 80.0,
        "speed": 40.0,
        "timestamp": "2026-05-02T10:00:00Z"
    })

    gen = enrichment_fn.process_element(old_telemetry, ctx)
    results = list(gen)

    print(f"\n>>> DROPPED OUTDATED TELEMETRY: length={len(results)} (Expected 0)")
    assert len(results) == 0


# ---------------------------------------------------------------------------
# K-6: stopsAhead enrichment tests
# ---------------------------------------------------------------------------

def test_stops_ahead_all_stops_when_at_start(enrichment_fn_with_stops):
    """Bus at route start — all 4 stops should be in stopsAhead."""
    ctx = MagicMock()
    enrichment_fn_with_stops.trip_to_route_state.get.return_value = "R1"
    enrichment_fn_with_stops.last_ts_state.value.return_value = None

    results = list(enrichment_fn_with_stops.process_element(_gps(6.0), ctx))
    assert len(results) == 1
    enriched = json.loads(results[0])

    print(f"\n>>> stopsAhead at start: {enriched['stopsAhead']}")
    assert len(enriched["stopsAhead"]) == 4
    assert enriched["stopsRemaining"] == 4


def test_stops_ahead_some_passed(enrichment_fn_with_stops):
    """Bus at lat 6.5 — stops A (6.2) and B (6.4) should be behind, C and D ahead."""
    ctx = MagicMock()
    enrichment_fn_with_stops.trip_to_route_state.get.return_value = "R1"
    enrichment_fn_with_stops.last_ts_state.value.return_value = None

    results = list(enrichment_fn_with_stops.process_element(_gps(6.5), ctx))
    assert len(results) == 1
    enriched = json.loads(results[0])

    print(f"\n>>> stopsAhead at lat 6.5: {enriched['stopsAhead']}")
    stop_ids = [s["stopId"] for s in enriched["stopsAhead"]]
    # Stops A(id=1) and B(id=2) are at 6.2 and 6.4 — behind 6.5
    assert 1 not in stop_ids
    assert 2 not in stop_ids
    # Stops C(id=3) and D(id=4) are at 6.6 and 6.8 — ahead
    assert 3 in stop_ids
    assert 4 in stop_ids


def test_stops_ahead_empty_when_no_stops(enrichment_fn):
    """Route has no preloaded stops — stopsAhead should be empty list."""
    ctx = MagicMock()
    enrichment_fn.trip_to_route_state.get.return_value = "R1"
    enrichment_fn.last_ts_state.value.return_value = None

    results = list(enrichment_fn.process_element(_gps(6.5), ctx))
    assert len(results) == 1
    enriched = json.loads(results[0])

    print(f"\n>>> stopsAhead with no stops loaded: {enriched['stopsAhead']}")
    assert enriched["stopsAhead"] == []
    assert enriched["stopsRemaining"] == 0
    assert enriched["nextStopId"] is None


def test_next_stop_id_is_first_stop_ahead(enrichment_fn_with_stops):
    """nextStopId should equal the stopId of the first entry in stopsAhead."""
    ctx = MagicMock()
    enrichment_fn_with_stops.trip_to_route_state.get.return_value = "R1"
    enrichment_fn_with_stops.last_ts_state.value.return_value = None

    results = list(enrichment_fn_with_stops.process_element(_gps(6.0), ctx))
    enriched = json.loads(results[0])

    print(f"\n>>> nextStopId={enriched['nextStopId']}  stopsAhead[0]={enriched['stopsAhead'][0]}")
    assert enriched["nextStopId"] == enriched["stopsAhead"][0]["stopId"]


def test_distance_to_next_stop_matches_stops_ahead(enrichment_fn_with_stops):
    """distanceToNextStop should equal stopsAhead[0].distanceAlongRouteMeters."""
    ctx = MagicMock()
    enrichment_fn_with_stops.trip_to_route_state.get.return_value = "R1"
    enrichment_fn_with_stops.last_ts_state.value.return_value = None

    results = list(enrichment_fn_with_stops.process_element(_gps(6.3), ctx))
    enriched = json.loads(results[0])

    print(f"\n>>> distanceToNextStop={enriched['distanceToNextStop']}  stopsAhead[0].distanceAlongRouteMeters={enriched['stopsAhead'][0]['distanceAlongRouteMeters']}")
    assert enriched["distanceToNextStop"] == enriched["stopsAhead"][0]["distanceAlongRouteMeters"]


def test_stops_ahead_ordered_by_stop_order(enrichment_fn_with_stops):
    """stopsAhead must be ordered by ascending stop_order."""
    ctx = MagicMock()
    enrichment_fn_with_stops.trip_to_route_state.get.return_value = "R1"
    enrichment_fn_with_stops.last_ts_state.value.return_value = None

    results = list(enrichment_fn_with_stops.process_element(_gps(6.0), ctx))
    enriched = json.loads(results[0])

    stop_ids = [s["stopId"] for s in enriched["stopsAhead"]]
    print(f"\n>>> stopsAhead order: {stop_ids}")
    assert stop_ids == sorted(stop_ids)


def test_enriched_message_contains_new_fields(enrichment_fn_with_stops):
    """All new ETA fields must be present in the enriched message."""
    ctx = MagicMock()
    enrichment_fn_with_stops.trip_to_route_state.get.return_value = "R1"
    enrichment_fn_with_stops.last_ts_state.value.return_value = None

    results = list(enrichment_fn_with_stops.process_element(_gps(6.1), ctx))
    enriched = json.loads(results[0])

    for field in (
        "nextStopId",
        "distanceToNextStop",
        "stopsRemaining",
        "stopsAhead",
        "on_route",
        "onRoute",
        "offRoute",
        "offRouteDistanceM",
        "trip_status",
        "next_stops",
    ):
        assert field in enriched, f"Missing field: {field}"
    print(f"\n>>> All ETA fields present in enriched message.")


def test_enriched_message_flags_off_route(enrichment_fn):
    ctx = MagicMock()
    enrichment_fn.trip_to_route_state.get.return_value = "R1"
    enrichment_fn.last_ts_state.value.return_value = None

    telemetry = json.dumps({
        "busId": "B1",
        "tripId": "T1",
        "lat": 6.5,
        "lon": 80.01,
        "speed": 40.0,
        "timestamp": "2026-05-02T10:00:00Z"
    })

    results = list(enrichment_fn.process_element(telemetry, ctx))
    enriched = json.loads(results[0])

    assert enriched["offRoute"] is True
    assert enriched["on_route"] is False
    assert enriched["offRouteDistanceM"] > 50.0


def test_lifecycle_state_supplies_trip_for_stateless_ingestion(enrichment_fn):
    ctx = MagicMock()
    enrichment_fn.active_trip_id_state = MagicMock()
    enrichment_fn.active_route_id_state = MagicMock()
    enrichment_fn.trip_status_state = MagicMock()
    enrichment_fn.active_trip_id_state.value.return_value = "T1"
    enrichment_fn.active_route_id_state.value.return_value = "R1"
    enrichment_fn.trip_status_state.value.return_value = "ACTIVE"
    enrichment_fn.last_ts_state.value.return_value = None

    telemetry = json.dumps({
        "busId": "B1",
        "lat": 6.5,
        "lon": 80.0,
        "speed": 40.0,
        "timestamp": "2026-05-02T10:00:00Z"
    })

    results = list(enrichment_fn.process_element(telemetry, ctx))
    enriched = json.loads(results[0])

    assert enriched["tripId"] == "T1"
    assert enriched["routeId"] == "R1"
    assert enriched["trip_status"] == "ACTIVE"


def test_startup_active_trip_bootstrap_supplies_trip_for_stateless_ingestion(enrichment_fn):
    ctx = MagicMock()
    enrichment_fn.bootstrap_active_trips = {
        "B1": {"tripId": "T1", "routeId": "R1", "trip_status": "ACTIVE"}
    }
    enrichment_fn.last_ts_state.value.return_value = None

    telemetry = json.dumps({
        "busId": "B1",
        "lat": 6.5,
        "lon": 80.0,
        "speed": 40.0,
        "timestamp": "2026-05-02T10:00:00Z"
    })

    results = list(enrichment_fn.process_element(telemetry, ctx))
    enriched = json.loads(results[0])

    assert enriched["tripId"] == "T1"
    assert enriched["routeId"] == "R1"
    assert enriched["trip_status"] == "ACTIVE"
