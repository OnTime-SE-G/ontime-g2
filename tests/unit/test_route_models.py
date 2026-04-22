# tests/unit/test_route_models.py

import pytest
from pydantic import ValidationError

from scripts.models.route import Stop, RouteGeometry, RouteSeed


def make_valid_stops(count: int = 20):
    return [
        Stop(
            name=f"Stop {i}",
            lat=6.80 + (i * 0.001),
            lon=79.90 + (i * 0.001),
        )
        for i in range(1, count + 1)
    ]


def test_create_valid_stop():
    stop = Stop(
        name="Katubedda Junction",
        lat=6.7974,
        lon=79.8886,
    )

    assert stop.name == "Katubedda Junction"
    assert stop.lat == 6.7974
    assert stop.lon == 79.8886
    assert stop.stop_order is None


def test_stop_invalid_latitude():
    with pytest.raises(ValidationError):
        Stop(
            name="Bad Stop",
            lat=200,
            lon=79.9,
        )


def test_stop_invalid_longitude():
    with pytest.raises(ValidationError):
        Stop(
            name="Bad Stop",
            lat=6.8,
            lon=500,
        )


def test_stop_coordinates_must_be_within_configured_bounds():
    with pytest.raises(ValidationError):
        Stop(
            name="Outside Sri Lanka",
            lat=10.5,
            lon=79.9,
        )


def test_route_geometry_valid():
    geometry = RouteGeometry(
        coordinates=[
            (79.88, 6.77),
            (79.95, 7.00),
        ]
    )

    assert len(geometry.coordinates) == 2


def test_route_geometry_requires_two_points():
    with pytest.raises(ValidationError):
        RouteGeometry(
            coordinates=[
                (79.88, 6.77),
            ]
        )


def test_route_geometry_coordinates_must_be_within_configured_bounds():
    with pytest.raises(ValidationError):
        RouteGeometry(
            coordinates=[
                (79.88, 6.77),
                (85.0, 7.00),
            ]
        )


def test_route_seed_valid_with_20_stops():
    route = RouteSeed(
        name="Moratuwa to Kadawatha",
        geometry=RouteGeometry(
            coordinates=[
                (79.88, 6.77),
                (79.95, 7.00),
            ]
        ),
        stops=make_valid_stops(20),
    )

    assert route.name == "Moratuwa to Kadawatha"
    assert len(route.stops) == 20

def test_route_seed_auto_assigns_stop_order():
    route = RouteSeed(
        name="Ordered Route",
        geometry=RouteGeometry(
            coordinates=[
                (79.88, 6.77),
                (79.95, 7.00),
            ]
        ),
        stops=make_valid_stops(20),
    )

    assert route.stops[0].stop_order == 1
    assert route.stops[1].stop_order == 2
    assert route.stops[-1].stop_order == 20
