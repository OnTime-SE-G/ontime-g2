import httpx
import logging
from typing import Dict, List, Tuple, Any
from app.config import settings

logger = logging.getLogger(__name__)


def _geometry_to_points(route: dict) -> List[Tuple[float, float]]:
    geometry = route.get("geometry")
    if not geometry:
        logger.warning("Skipping route %s because geometry is missing", route.get("id"))
        return []

    coordinates = geometry.get("coordinates")
    if not coordinates:
        logger.warning("Skipping route %s because coordinates are missing", route.get("id"))
        return []

    points = []
    for coordinate in coordinates:
        if not isinstance(coordinate, (list, tuple)) or len(coordinate) < 2:
            logger.warning("Skipping invalid coordinate for route %s: %s", route.get("id"), coordinate)
            return []
        lon, lat = coordinate[0], coordinate[1]
        points.append((lat, lon))

    return points


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
                        if route.get("id") is None:
                            logger.warning("Skipping route geometry without id")
                            continue
                        route_id = str(route["id"])
                        # GeoJSON is [lon, lat], we want [(lat, lon), ...]
                        points = _geometry_to_points(route)
                        if points:
                            geometries[route_id] = points
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


def fetch_stops_sync(route_id: str) -> List[Dict]:
    """
    Synchronously fetch all stops for a single route from the Route Service.
    Returns [{id, name, stop_order, lat, lon}, ...] ordered by stop_order.
    Used by EnrichmentFunction.open() to preload stop data for stopsAhead computation.
    """
    import asyncio

    async def _fetch():
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{settings.route_service_url}/internal/routes/{route_id}/stops",
                    timeout=10.0,
                )
                if response.status_code == 200:
                    return response.json()
                logger.warning("fetch_stops_sync: route %s returned %s", route_id, response.status_code)
                return []
            except Exception as exc:
                logger.error("fetch_stops_sync: request failed for route %s: %s", route_id, exc)
                return []

    try:
        return asyncio.run(_fetch())
    except Exception as exc:
        logger.error("fetch_stops_sync: asyncio.run failed for route %s: %s", route_id, exc)
        return []


def fetch_active_trips_sync() -> Dict[str, Dict[str, str]]:
    """
    Fetch currently active Fleet trips for Flink startup bootstrap.

    Returns {busId: {tripId, routeId, trip_status}}. Lifecycle Kafka events
    remain the live source of updates after startup.
    """
    import asyncio

    async def _fetch():
        async with httpx.AsyncClient() as client:
            try:
                schedules_response = await client.get(
                    f"{settings.fleet_service_url}/api/v1/fleet/schedules",
                    timeout=10.0,
                )
                if schedules_response.status_code != 200:
                    logger.warning(
                        "fetch_active_trips_sync: schedules returned %s",
                        schedules_response.status_code,
                    )
                    return {}

                schedules = schedules_response.json()
                schedule_to_route = {
                    str(schedule.get("id")): str(schedule.get("route_id"))
                    for schedule in schedules
                    if schedule.get("id") is not None and schedule.get("route_id") is not None
                }

                active_by_bus: Dict[str, Dict[str, str]] = {}
                for status in ("EN_ROUTE", "INCIDENT_REPORTED"):
                    trips_response = await client.get(
                        f"{settings.fleet_service_url}/api/v1/fleet/planned-trips",
                        params={"status": status},
                        timeout=10.0,
                    )
                    if trips_response.status_code != 200:
                        logger.warning(
                            "fetch_active_trips_sync: trips status=%s returned %s",
                            status,
                            trips_response.status_code,
                        )
                        continue

                    for trip in trips_response.json():
                        bus_id = trip.get("bus_id")
                        trip_id = trip.get("id")
                        schedule_id = trip.get("schedule_id")
                        route_id = schedule_to_route.get(str(schedule_id))
                        if bus_id is None or trip_id is None or route_id is None:
                            continue
                        active_by_bus[str(bus_id)] = {
                            "tripId": str(trip_id),
                            "routeId": route_id,
                            "trip_status": "ACTIVE",
                        }

                return active_by_bus
            except Exception as exc:
                logger.error("fetch_active_trips_sync: request failed: %s", exc)
                return {}

    try:
        return asyncio.run(_fetch())
    except Exception as exc:
        logger.error("fetch_active_trips_sync: asyncio.run failed: %s", exc)
        return {}
