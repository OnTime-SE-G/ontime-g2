import httpx
from app.config import FLEET_SERVICE_URL

async def get_buses():
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{FLEET_SERVICE_URL}/api/v1/fleet/buses")
        return res.json()