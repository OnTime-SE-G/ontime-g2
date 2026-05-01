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