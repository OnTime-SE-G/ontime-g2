import pytest
import json
from unittest.mock import MagicMock
from app.transforms.enrichment import EnrichmentFunction

@pytest.fixture
def enrichment_fn():
    fn = EnrichmentFunction()
    # Mock states
    fn.trip_to_route_state = MagicMock()
    fn.last_ts_state = MagicMock()
    fn.route_geometries = {
        "R1": [(6.0, 80.0), (7.0, 80.0)]
    }
    return fn

def test_process_lifecycle_event(enrichment_fn):
    ctx = MagicMock()
    event = json.dumps({
        "event": "TRIP_STARTED",
        "busId": "B1",
        "tripId": "T1",
        "routeId": "R1"
    })
    
    # process_element should update state and return nothing (yield is empty)
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
    # Mock that we already saw a message at 10:05
    enrichment_fn.last_ts_state.value.return_value = "2026-05-02T10:05:00Z"
    
    # Old message (10:00)
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
    
    # Should be dropped
    print(f"\n>>> DROPPED OUTDATED TELEMETRY: length={len(results)} (Expected 0)")
    assert len(results) == 0
