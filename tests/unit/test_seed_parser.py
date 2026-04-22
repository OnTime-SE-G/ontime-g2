# tests/unit/test_seed_parser.py

from pathlib import Path

import pytest

from scripts.seed_routes import load_kml
from scripts.models.route import RouteSeed


def test_load_kml_returns_route_seed():
    route = load_kml("data/moratuwa_kadawatha.kml")

    assert isinstance(route, RouteSeed)


def test_load_kml_has_route_name():
    route = load_kml("data/moratuwa_kadawatha.kml")

    assert route.name == "Moratuwa to Kadawatha"


def test_load_kml_has_geometry_points():
    route = load_kml("data/moratuwa_kadawatha.kml")

    assert len(route.geometry.coordinates) >= 2


def test_load_kml_has_stops():
    route = load_kml("data/moratuwa_kadawatha.kml")

    assert len(route.stops) > 0


def test_load_kml_first_stop_has_name():
    route = load_kml("data/moratuwa_kadawatha.kml")

    assert route.stops[0].name is not None
    assert route.stops[0].name != ""


def test_load_kml_invalid_file_raises_error():
    with pytest.raises(FileNotFoundError):
        load_kml("data/ghost_bus_route.kml")


def test_load_kml_file_exists():
    assert Path("data/moratuwa_kadawatha.kml").exists()