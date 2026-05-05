import pytest
from app.utils.geo import calculate_route_progress, get_dist_along_route, haversine_distance

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


# --- get_dist_along_route ---

def test_get_dist_along_route_at_start():
    route_geom = [(6.0, 80.0), (7.0, 80.0)]
    dist = get_dist_along_route(6.0, 80.0, route_geom)
    print(f"\n>>> dist_along at start: {dist:.2f}m")
    assert dist == pytest.approx(0.0, abs=10.0)


def test_get_dist_along_route_at_end():
    route_geom = [(6.0, 80.0), (7.0, 80.0)]
    total = haversine_distance(6.0, 80.0, 7.0, 80.0)
    dist = get_dist_along_route(7.0, 80.0, route_geom)
    print(f"\n>>> dist_along at end: {dist:.2f}m  total: {total:.2f}m")
    assert dist == pytest.approx(total, rel=0.01)


def test_get_dist_along_route_at_midpoint():
    route_geom = [(6.0, 80.0), (7.0, 80.0)]
    total = haversine_distance(6.0, 80.0, 7.0, 80.0)
    dist = get_dist_along_route(6.5, 80.0, route_geom)
    print(f"\n>>> dist_along at midpoint: {dist:.2f}m  half: {total/2:.2f}m")
    assert dist == pytest.approx(total / 2, rel=0.05)


def test_get_dist_along_route_stops_increase_with_order():
    """Stops further along the route should have larger dist_along values."""
    route_geom = [(6.0, 80.0), (7.0, 80.0)]
    d1 = get_dist_along_route(6.2, 80.0, route_geom)
    d2 = get_dist_along_route(6.5, 80.0, route_geom)
    d3 = get_dist_along_route(6.8, 80.0, route_geom)
    print(f"\n>>> dist_along stop 1:{d1:.0f}m  stop 2:{d2:.0f}m  stop 3:{d3:.0f}m")
    assert d1 < d2 < d3


def test_get_dist_along_route_empty_returns_zero():
    assert get_dist_along_route(6.5, 80.0, []) == 0.0


def test_get_dist_along_route_single_point_returns_zero():
    assert get_dist_along_route(6.5, 80.0, [(6.5, 80.0)]) == 0.0
