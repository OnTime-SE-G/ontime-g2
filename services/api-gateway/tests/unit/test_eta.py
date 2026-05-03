from app.models.eta import ETACalculator
from datetime import datetime, timedelta

def test_haversine_distance():
    # Distance between Colombo and Kandy (~115km)
    colombo = (6.9271, 79.8612)
    kandy = (7.2906, 80.6337)
    
    distance = ETACalculator.haversine_distance(*colombo, *kandy)
    assert 110 < distance < 120

def test_calculate_eta_minutes():
    # 20km at 20km/h should take 60 mins. 
    # With 20% buffer, it should be 72 mins.
    # We use a distance of exactly 20km by choosing lat/lon carefully or just checking the math
    # 1 degree lat is ~111km. 0.18 degrees is ~20km.
    current = (0.0, 0.0)
    target = (0.18, 0.0) 
    
    minutes = ETACalculator.calculate_eta_minutes(*current, *target)
    # distance is ~20.01km. time is ~1.00h -> 60m. +20% -> 72m.
    assert 70 <= minutes <= 75

def test_get_arrival_time():
    current = (0.0, 0.0)
    target = (0.18, 0.0)
    delay = 10 # 10 mins delay
    
    now = datetime.now()
    arrival = ETACalculator.get_arrival_time(*current, *target, delay_minutes=delay)
    
    # Expected: now + ~72m + 10m = now + 82m
    expected_diff = timedelta(minutes=82)
    actual_diff = arrival - now
    
    assert 80 <= actual_diff.total_seconds() / 60 <= 85
