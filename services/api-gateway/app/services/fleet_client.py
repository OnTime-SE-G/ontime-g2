import httpx
import os

# Internal service URLs from environment variables
FLEET_SERVICE_URL = os.getenv("FLEET_SERVICE_URL", "http://fleet-management-service:8003")


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


async def list_buses():
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{FLEET_SERVICE_URL}/api/v1/fleet/buses")
        res.raise_for_status()
        return res.json()


async def get_bus_detail(bus_id: int):
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{FLEET_SERVICE_URL}/api/v1/fleet/buses/{bus_id}")
        res.raise_for_status()
        return res.json()


async def list_buses_by_route(route_id: int):
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{FLEET_SERVICE_URL}/api/v1/fleet/buses/route/{route_id}")
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


async def create_driver(driver_data: dict):
    async with httpx.AsyncClient() as client:
        res = await client.post(f"{FLEET_SERVICE_URL}/api/v1/fleet/drivers", json=driver_data)
        res.raise_for_status()
        return res.json()


async def list_drivers():
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{FLEET_SERVICE_URL}/api/v1/fleet/drivers")
        res.raise_for_status()
        return res.json()


async def create_schedule(schedule_data: dict):
    async with httpx.AsyncClient() as client:
        res = await client.post(f"{FLEET_SERVICE_URL}/api/v1/fleet/schedules", json=schedule_data)
        res.raise_for_status()
        return res.json()


async def list_schedules():
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{FLEET_SERVICE_URL}/api/v1/fleet/schedules")
        res.raise_for_status()
        return res.json()


async def generate_planned_trips(target_date: str):
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{FLEET_SERVICE_URL}/api/v1/fleet/planned-trips/generate",
            params={"target_date": target_date},
        )
        res.raise_for_status()
        return res.json()


async def get_today_trips():
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{FLEET_SERVICE_URL}/api/v1/fleet/planned-trips/today")
        res.raise_for_status()
        return res.json()


async def get_trip_detail(trip_id: str):
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{FLEET_SERVICE_URL}/api/v1/fleet/planned-trips/{trip_id}")
        res.raise_for_status()
        return res.json()


async def assign_trip_resources(trip_id: str, bus_id: int, driver_id: int):
    async with httpx.AsyncClient() as client:
        res = await client.patch(
            f"{FLEET_SERVICE_URL}/api/v1/fleet/planned-trips/{trip_id}/assign",
            params={"bus_id": bus_id, "driver_id": driver_id},
        )
        res.raise_for_status()
        return res.json()


async def start_planned_trip(trip_id: str):
    async with httpx.AsyncClient() as client:
        res = await client.post(f"{FLEET_SERVICE_URL}/api/v1/fleet/planned-trips/{trip_id}/start")
        res.raise_for_status()
        return res.json()


async def end_planned_trip(trip_id: str):
    async with httpx.AsyncClient() as client:
        res = await client.post(f"{FLEET_SERVICE_URL}/api/v1/fleet/planned-trips/{trip_id}/end")
        res.raise_for_status()
        return res.json()


async def report_trip_delay(trip_id: str, delay_minutes: int):
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{FLEET_SERVICE_URL}/api/v1/fleet/planned-trips/{trip_id}/delay",
            json={"delay_minutes": delay_minutes}
        )
        res.raise_for_status()
        return res.json()


async def report_trip_incident(trip_id: str, incident_type: str, message: str | None = None):
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{FLEET_SERVICE_URL}/api/v1/fleet/planned-trips/{trip_id}/incident",
            json={"incident_type": incident_type, "message": message}
        )
        res.raise_for_status()
        return res.json()