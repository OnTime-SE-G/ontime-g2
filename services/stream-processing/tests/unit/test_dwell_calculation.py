"""Unit tests for dwell calculation utility."""

import pytest
from datetime import datetime, timedelta
from app.utils.dwell_calculation import DwellCalculator, VehicleStopState


def test_vehicle_stop_state_update_dwell():
    """Test dwell time update in stop state."""
    entry_time = datetime(2023, 10, 24, 8, 0, 0)
    state = VehicleStopState(
        vehicle_id="BUS_001",
        trip_id="TRIP_123",
        stop_id="Stop_A",
        entry_time=entry_time
    )
    
    # Update after 60 seconds
    current_time = entry_time + timedelta(seconds=60)
    dwell = state.update_dwell(current_time)
    
    assert dwell == 60
    assert state.dwell_seconds == 60


def test_dwell_calculator_first_stop():
    """Test dwell calculation for first stop."""
    calculator = DwellCalculator()
    
    entry_time = datetime(2023, 10, 24, 8, 0, 0)
    dwell_current, dwell_prev = calculator.record_vehicle_at_stop(
        vehicle_id="BUS_001",
        trip_id="TRIP_123",
        stop_id="Stop_A",
        timestamp=entry_time
    )
    
    # First stop should have 0 current dwell and None for previous
    assert dwell_current == 0
    assert dwell_prev is None


def test_dwell_calculator_same_stop_update():
    """Test dwell time increases at same stop."""
    calculator = DwellCalculator()
    
    entry_time = datetime(2023, 10, 24, 8, 0, 0)
    
    # Record at stop
    dwell1, _ = calculator.record_vehicle_at_stop(
        vehicle_id="BUS_001",
        trip_id="TRIP_123",
        stop_id="Stop_A",
        timestamp=entry_time
    )
    assert dwell1 == 0
    
    # Update at same stop after 30 seconds
    update_time = entry_time + timedelta(seconds=30)
    dwell2, _ = calculator.record_vehicle_at_stop(
        vehicle_id="BUS_001",
        trip_id="TRIP_123",
        stop_id="Stop_A",
        timestamp=update_time
    )
    assert dwell2 == 30


def test_dwell_calculator_stop_transition():
    """Test dwell calculation when vehicle moves to new stop."""
    calculator = DwellCalculator()
    
    entry_time = datetime(2023, 10, 24, 8, 0, 0)
    
    # Record at Stop A
    dwell1, dwell_prev1 = calculator.record_vehicle_at_stop(
        vehicle_id="BUS_001",
        trip_id="TRIP_123",
        stop_id="Stop_A",
        timestamp=entry_time
    )
    
    # Update at Stop A after 45 seconds
    update_time = entry_time + timedelta(seconds=45)
    dwell2, dwell_prev2 = calculator.record_vehicle_at_stop(
        vehicle_id="BUS_001",
        trip_id="TRIP_123",
        stop_id="Stop_A",
        timestamp=update_time
    )
    assert dwell2 == 45
    assert dwell_prev2 is None  # Still no previous stop
    
    # Move to Stop B
    move_time = update_time + timedelta(seconds=10)
    dwell3, dwell_prev3 = calculator.record_vehicle_at_stop(
        vehicle_id="BUS_001",
        trip_id="TRIP_123",
        stop_id="Stop_B",
        timestamp=move_time
    )
    
    # Now should have dwell_prev from Stop A
    assert dwell3 == 0  # Just arrived at new stop
    assert dwell_prev3 == 45  # Dwell at previous stop


def test_dwell_calculator_multiple_vehicles():
    """Test dwell calculator with multiple vehicles."""
    calculator = DwellCalculator()
    
    time1 = datetime(2023, 10, 24, 8, 0, 0)
    
    # Vehicle 1 at Stop A
    calc1_curr, calc1_prev = calculator.record_vehicle_at_stop(
        vehicle_id="BUS_001",
        trip_id="TRIP_123",
        stop_id="Stop_A",
        timestamp=time1
    )
    
    # Vehicle 2 at Stop B
    calc2_curr, calc2_prev = calculator.record_vehicle_at_stop(
        vehicle_id="BUS_002",
        trip_id="TRIP_124",
        stop_id="Stop_B",
        timestamp=time1
    )
    
    # Both should track independently
    assert calculator.get_vehicle_state("BUS_001", "TRIP_123") is not None
    assert calculator.get_vehicle_state("BUS_002", "TRIP_124") is not None
    assert calculator.get_vehicle_state("BUS_001", "TRIP_123") != calculator.get_vehicle_state("BUS_002", "TRIP_124")


def test_dwell_calculator_clear_vehicle_state():
    """Test clearing vehicle state."""
    calculator = DwellCalculator()
    
    time1 = datetime(2023, 10, 24, 8, 0, 0)
    
    # Record vehicle
    calculator.record_vehicle_at_stop(
        vehicle_id="BUS_001",
        trip_id="TRIP_123",
        stop_id="Stop_A",
        timestamp=time1
    )
    
    # Verify it exists
    assert calculator.get_vehicle_state("BUS_001", "TRIP_123") is not None
    
    # Clear state
    calculator.clear_vehicle_state("BUS_001", "TRIP_123")
    
    # Verify it's gone
    assert calculator.get_vehicle_state("BUS_001", "TRIP_123") is None
