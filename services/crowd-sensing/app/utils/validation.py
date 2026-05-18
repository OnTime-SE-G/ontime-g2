import urllib.request
import urllib.error
import json
import logging
from fastapi import HTTPException
from app.config import settings

logger = logging.getLogger(__name__)

def validate_route_stop(route_id: int, stop_id: int):
    """
    Query the central Route Service to ensure the route exists and the stop belongs to that route.
    """
    logger.debug(f"Verifying route stop integrity for route {route_id}, stop {stop_id}")
    url = f"{settings.route_service_url}/api/v1/routes/{route_id}/stops"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5.0) as response:
            data = json.loads(response.read().decode())
            valid_stops = data.get("stops", [])
            valid_stop_ids = [s["id"] for s in valid_stops]
            
            if stop_id not in valid_stop_ids:
                raise HTTPException(
                    status_code=400,
                    detail=f"Stop ID {stop_id} is not associated with Route ID {route_id}."
                )
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Route ID {route_id} does not exist in the system."
            )
        raise HTTPException(
            status_code=502,
            detail=f"Route service error: {e.reason}"
        )
    except urllib.error.URLError as e:
        logger.error(f"Failed to connect to Route Service: {e.reason}")
        # Return 503 Service Unavailable if route-service is down
        raise HTTPException(
            status_code=503,
            detail="Route Service is currently offline or unreachable."
        )
