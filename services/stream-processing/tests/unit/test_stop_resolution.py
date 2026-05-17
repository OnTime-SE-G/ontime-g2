"""Unit tests for stop resolution utility."""

import pytest
from app.utils.stop_resolution import StopZone, StopResolutionManager


def test_stop_zone_contains_point_inside():
    """Test point-in-polygon check for point inside zone."""
    zone = StopZone(
        stop_id="Stop_A",
        lat=6.9271,
        lon=80.7789,
        radius_meters=50
    )
    
    # Point slightly offset (should be within 50m)
    assert zone.contains_point(6.92715, 80.77895) is True


def test_stop_zone_contains_point_outside():
    """Test point-in-polygon check for point outside zone."""
    zone = StopZone(
        stop_id="Stop_A",
        lat=6.9271,
        lon=80.7789,
        radius_meters=50
    )
    
    # Point far away (definitely outside)
    assert zone.contains_point(7.0, 81.0) is False


def test_stop_resolution_manager_add_stop():
    """Test adding stops to manager."""
    manager = StopResolutionManager()
    
    zone = StopZone(
        stop_id="Stop_A",
        lat=6.9271,
        lon=80.7789,
        radius_meters=50
    )
    
    manager.add_stop(zone)
    assert "Stop_A" in manager.stops
    assert manager.get_stop_info("Stop_A").stop_id == "Stop_A"


def test_stop_resolution_manager_resolve_stop():
    """Test stop resolution from GPS coordinates."""
    manager = StopResolutionManager()
    
    zone = StopZone(
        stop_id="Stop_A",
        lat=6.9271,
        lon=80.7789,
        radius_meters=50
    )
    
    manager.add_stop(zone)
    
    # Resolve point inside zone
    stop_id = manager.resolve_stop(6.92715, 80.77895)
    assert stop_id == "Stop_A"
    
    # Resolve point outside all zones
    stop_id = manager.resolve_stop(7.0, 81.0)
    assert stop_id is None


def test_stop_resolution_manager_load_from_dict():
    """Test loading stops from dictionary configuration."""
    manager = StopResolutionManager()
    
    stops_dict = {
        "Stop_A": {
            "lat": 6.9271,
            "lon": 80.7789,
            "radius_meters": 50,
            "name": "Colombo Central"
        },
        "Stop_B": {
            "lat": 6.8800,
            "lon": 80.6700,
            "radius_meters": 60,
            "name": "Galle Face"
        }
    }
    
    manager.load_stops_from_dict(stops_dict)
    
    assert len(manager.stops) == 2
    assert "Stop_A" in manager.stops
    assert "Stop_B" in manager.stops
    assert manager.get_stop_info("Stop_A").zone_name == "Colombo Central"
