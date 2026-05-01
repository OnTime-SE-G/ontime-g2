import math
from typing import List, Tuple

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance between two points on the earth in meters."""
    R = 6371000  # Radius of earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def calculate_route_progress(lat: float, lon: float, points: List[Tuple[float, float]]) -> Tuple[float, float]:
    """
    Calculate progress along a route.
    Returns: (remaining_distance_m, progress_percentage)
    """
    if not points or len(points) < 2:
        return 0.0, 0.0

    total_distance = 0.0
    segment_distances = []
    for i in range(len(points) - 1):
        d = haversine_distance(points[i][0], points[i][1], points[i+1][0], points[i+1][1])
        segment_distances.append(d)
        total_distance += d

    if total_distance == 0:
        return 0.0, 0.0

    # Find the closest point on the route
    min_dist = float('inf')
    closest_idx = 0
    for i, p in enumerate(points):
        d = haversine_distance(lat, lon, p[0], p[1])
        if d < min_dist:
            min_dist = d
            closest_idx = i

    # Calculate distance from start to closest point
    dist_from_start = sum(segment_distances[:closest_idx])
    
    remaining_distance = total_distance - dist_from_start
    progress_pct = (dist_from_start / total_distance) * 100
    
    return max(0.0, remaining_distance), min(100.0, max(0.0, progress_pct))
