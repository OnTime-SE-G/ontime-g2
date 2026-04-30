# tests/unit/test_seed_parser.py

from pathlib import Path

import pytest

from scripts.seed_routes import discover_kml_files, load_kml, route_name_from_file
from scripts.models.route import RouteSeed


def test_load_kml_returns_route_seed():
    route = load_kml("data/moratuwa_kadawatha.kml")

    assert isinstance(route, RouteSeed)


def test_load_kml_has_route_name():
    route = load_kml("data/moratuwa_kadawatha.kml")

    assert route.name == "moratuwa_kadawatha"


def test_route_name_from_file_uses_file_stem():
    assert route_name_from_file("data/moratuwa_kadawatha.kml") == "moratuwa_kadawatha"


def test_discover_kml_files_returns_data_folder_routes():
    route_files = discover_kml_files("data")

    assert Path("data/moratuwa_kadawatha.kml") in route_files


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
