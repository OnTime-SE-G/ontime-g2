import httpx
import os

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8005")

async def register_user(user_data: dict):
    async with httpx.AsyncClient() as client:
        res = await client.post(f"{AUTH_SERVICE_URL}/users/register", json=user_data)
        res.raise_for_status()
        return res.json()

async def get_drivers():
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{AUTH_SERVICE_URL}/users/drivers")
        res.raise_for_status()
        return res.json()
