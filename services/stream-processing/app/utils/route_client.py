import httpx
import logging
from typing import Dict, List, Tuple
from app.config import settings

logger = logging.getLogger(__name__)

class RouteClient:
    def __init__(self):
        self.base_url = settings.route_service_url

    async def get_all_route_geometries(self) -> Dict[str, List[Tuple[float, float]]]:
        """
        Fetch all route geometries from the Route Service.
        Expected format: { "routeId": [(lat, lon), ...] }
        """
        try:
            async with httpx.AsyncClient() as client:
                # Based on INCREMENT_1_PLAN_2 section 12.2 Phase C2
                response = await client.get(f"{self.base_url}/internal/routes/geometry", timeout=10.0)
                if response.status_code == 200:
                    data = response.json()
                    # Convert to expected internal format
                    geometries = {}
                    for route in data:
                        route_id = str(route["id"])
                        coords = route["geometry"]["coordinates"]
                        # GeoJSON is [lon, lat], we want [(lat, lon), ...]
                        geometries[route_id] = [(c[1], c[0]) for c in coords]
                    return geometries
                else:
                    logger.error(f"Failed to fetch route geometries: {response.status_code}")
                    return {}
        except Exception as e:
            logger.error(f"Error fetching route geometries: {e}")
            return {}

def fetch_geometries_sync():
    """Synchronous wrapper for startup."""
    import asyncio
    client = RouteClient()
    return asyncio.run(client.get_all_route_geometries())
