import httpx
from app.config import FLEET_SERVICE_URL

async def get_buses():
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{FLEET_SERVICE_URL}/api/v1/fleet/buses")
        return res.json()

async def get_bus(bus_id: str):
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{FLEET_SERVICE_URL}/api/v1/fleet/buses/{bus_id}")
        return res.json()

async def add_bus(bus_data: dict):
    async with httpx.AsyncClient() as client:
        res = await client.post(f"{FLEET_SERVICE_URL}/api/v1/fleet/buses", json=bus_data)
        res.raise_for_status()
        return res.json()

async def update_bus(bus_id: str, bus_data: dict):
    async with httpx.AsyncClient() as client:
        res = await client.put(f"{FLEET_SERVICE_URL}/api/v1/fleet/buses/{bus_id}", json=bus_data)
        res.raise_for_status()
        return res.json()

async def delete_bus(bus_id: str):
    async with httpx.AsyncClient() as client:
        res = await client.delete(f"{FLEET_SERVICE_URL}/api/v1/fleet/buses/{bus_id}")
        res.raise_for_status()
        return res.json()

async def assign_route(bus_id: str, route_id: str):
    async with httpx.AsyncClient() as client:
        res = await client.post(f"{FLEET_SERVICE_URL}/api/v1/fleet/buses/{bus_id}/assign-route/{route_id}")
        res.raise_for_status()
        return res.json()

async def unassign_route(bus_id: str):
    async with httpx.AsyncClient() as client:
        res = await client.post(f"{FLEET_SERVICE_URL}/api/v1/fleet/buses/{bus_id}/unassign")
        res.raise_for_status()
        return res.json()

async def get_route_buses(route_id: str):
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{FLEET_SERVICE_URL}/api/v1/fleet/buses/route/{route_id}")
        return res.json()