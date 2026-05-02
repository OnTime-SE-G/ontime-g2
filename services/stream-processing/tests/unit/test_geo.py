import pytest
from app.utils.geo import calculate_route_progress

def test_calculate_route_progress_exact_match():
    # Vertical line from lat 6.0 to 7.0
    route_geom = [(6.0, 80.0), (7.0, 80.0)]
    lat, lon = 6.5, 80.0
    
    remaining_dist, progress_pct = calculate_route_progress(lat, lon, route_geom)
    
    print(f"\n>>> GEO EXACT MATCH: Bus at halfway point -> Progress: {progress_pct:.2f}%, Remaining: {remaining_dist:.2f}m")
    
    # Halfway through
    assert progress_pct == pytest.approx(50.0, rel=0.1)
    # Total distance is ~111km, so half is ~55.5km
    assert remaining_dist > 50000

def test_calculate_route_progress_start():
    route_geom = [(6.0, 80.0), (7.0, 80.0)]
    lat, lon = 6.0, 80.0
    remaining_dist, progress_pct = calculate_route_progress(lat, lon, route_geom)
    print(f"\n>>> GEO START: Bus at start point -> Progress: {progress_pct:.2f}%, Remaining: {remaining_dist:.2f}m")
    assert progress_pct == pytest.approx(0.0, abs=0.1)

def test_calculate_route_progress_end():
    route_geom = [(6.0, 80.0), (7.0, 80.0)]
    lat, lon = 7.0, 80.0
    remaining_dist, progress_pct = calculate_route_progress(lat, lon, route_geom)
    print(f"\n>>> GEO END: Bus at end point -> Progress: {progress_pct:.2f}%, Remaining: {remaining_dist:.2f}m")
    assert progress_pct == pytest.approx(100.0, abs=0.1)
    assert remaining_dist == pytest.approx(0.0, abs=1.0)
