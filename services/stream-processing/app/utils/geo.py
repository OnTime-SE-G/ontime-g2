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
    Calculate progress along a route by projecting onto segments.
    Returns: (remaining_distance_m, progress_percentage)
    """
    if not points or len(points) < 2:
        return 0.0, 0.0

    total_distance = sum(haversine_distance(points[i][0], points[i][1], points[i+1][0], points[i+1][1]) 
                         for i in range(len(points) - 1))
    
    if total_distance == 0:
        return 0.0, 0.0

    min_dist = float('inf')
    dist_along_path = 0.0
    accumulated_dist = 0.0

    for i in range(len(points) - 1):
        p1 = points[i]
        p2 = points[i+1]
        
        # Segment length
        seg_len = haversine_distance(p1[0], p1[1], p2[0], p2[1])
        if seg_len == 0:
            continue
            
        # Linear projection (simplified for small distances)
        # Using a simple ratio based on distances to endpoints
        d1 = haversine_distance(lat, lon, p1[0], p1[1])
        d2 = haversine_distance(lat, lon, p2[0], p2[1])
        
        # Heron's formula or projection could be used here for better accuracy,
        # but for Inc 1, we use a simple projection ratio
        # Projection ratio t using Law of Cosines simplified:
        # t = (d1^2 + seg_len^2 - d2^2) / (2 * seg_len^2)
        t = (d1**2 + seg_len**2 - d2**2) / (2 * seg_len**2) if seg_len > 0 else 0.0
        t = max(0.0, min(1.0, t)) # Clamp to segment
        
        # Closest point on this segment
        proj_lat = p1[0] + t * (p2[0] - p1[0])
        proj_lon = p1[1] + t * (p2[1] - p1[1])
        
        d_seg = haversine_distance(lat, lon, proj_lat, proj_lon)
        
        if d_seg < min_dist:
            min_dist = d_seg
            dist_along_path = accumulated_dist + (t * seg_len)
            
        accumulated_dist += seg_len

    remaining_distance = total_distance - dist_along_path
    progress_pct = (dist_along_path / total_distance) * 100
    
    return max(0.0, remaining_distance), min(100.0, max(0.0, progress_pct))


