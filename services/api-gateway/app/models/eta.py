import math
from datetime import datetime, timedelta

class ETACalculator:
    """
    Mathematical ETA Model (Increment 1 Heuristic).
    Calculates ETA based on Haversine distance and an average speed heuristic.
    """
    
    # Average urban bus speed in km/h (heuristic)
    AVG_SPEED_KMH = 20.0
    
    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate the great-circle distance between two points on Earth in km."""
        R = 6371.0  # Earth radius in km
        
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        
        a = math.sin(dphi/2)**2 + \
            math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
        
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    @classmethod
    def calculate_eta_minutes(cls, current_lat: float, current_lon: float, target_lat: float, target_lon: float) -> int:
        """Estimate travel time in minutes based on distance and average speed."""
        distance_km = cls.haversine_distance(current_lat, current_lon, target_lat, target_lon)
        
        # time = distance / speed
        time_hours = distance_km / cls.AVG_SPEED_KMH
        time_minutes = time_hours * 60
        
        # Add a 20% buffer for traffic/stops
        return int(time_minutes * 1.2)

    @classmethod
    def get_arrival_time(cls, current_lat: float, current_lon: float, target_lat: float, target_lon: float, delay_minutes: int = 0) -> datetime:
        """Get the absolute estimated arrival time, accounting for reported delays."""
        travel_minutes = cls.calculate_eta_minutes(current_lat, current_lon, target_lat, target_lon)
        total_offset = travel_minutes + delay_minutes
        
        return datetime.now() + timedelta(minutes=total_offset)
