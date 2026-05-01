import httpx
from app.config import ROUTE_SERVICE_URL

async def get_route(route_id: str):
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{ROUTE_SERVICE_URL}/api/v1/routes/{route_id}")
        return res.json()

async def get_route_stops(route_id: str):
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{ROUTE_SERVICE_URL}/api/v1/routes/{route_id}/stops")
        return res.json()

async def get_routes_list():
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{ROUTE_SERVICE_URL}/api/v1/routes")
        return res.json()

async def search_routes(start_lat: float, start_lon: float, end_lat: float, end_lon: float, radius_m: int = 500):
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{ROUTE_SERVICE_URL}/api/v1/routes/search", params={
            "start_lat": start_lat,
            "start_lon": start_lon,
            "end_lat": end_lat,
            "end_lon": end_lon,
            "radius_m": radius_m
        })
        return res.json()

async def get_route_progress(route_id: str, lat: float, lon: float, target_stop_order: int):
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{ROUTE_SERVICE_URL}/api/v1/routes/{route_id}/progress", params={
            "lat": lat,
            "lon": lon,
            "target_stop_order": target_stop_order
        })
        return res.json()

async def get_route_buses(route_id: str):
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{ROUTE_SERVICE_URL}/api/v1/routes/{route_id}/buses")
        return res.json()

async def get_all_stops():
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{ROUTE_SERVICE_URL}/api/v1/stops")
        return res.json()

async def get_nearby_stops(lat: float, lon: float, radius_m: int = 500):
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{ROUTE_SERVICE_URL}/api/v1/stops/nearby", params={
            "lat": lat,
            "lon": lon,
            "radius_m": radius_m
        })
        return res.json()

async def get_routes_for_stop(stop_id: str):
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{ROUTE_SERVICE_URL}/api/v1/stops/{stop_id}/routes")
        return res.json()

async def add_route(route_name: str, filename: str, file_bytes: bytes, content_type: str):
    async with httpx.AsyncClient() as client:
        files = {'file': (filename, file_bytes, content_type)}
        data = {'route_name': route_name}
        res = await client.post(f"{ROUTE_SERVICE_URL}/api/v1/admin/routes/add-route", data=data, files=files)
        res.raise_for_status()
        return res.json()

async def update_route(route_id: str, route_name: str, filename: str, file_bytes: bytes, content_type: str):
    async with httpx.AsyncClient() as client:
        files = {'file': (filename, file_bytes, content_type)}
        data = {'route_name': route_name}
        res = await client.put(f"{ROUTE_SERVICE_URL}/api/v1/admin/routes/{route_id}", data=data, files=files)
        res.raise_for_status()
        return res.json()

async def delete_route(route_id: str):
    async with httpx.AsyncClient() as client:
        res = await client.delete(f"{ROUTE_SERVICE_URL}/api/v1/admin/routes/{route_id}")
        res.raise_for_status()
        return res.json()