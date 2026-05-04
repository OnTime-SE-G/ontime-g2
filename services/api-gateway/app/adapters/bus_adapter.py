def build_bus_data(bus, live_data=None):
    return {
        "id": str(bus["id"]),
        "fleet_code": bus.get("fleet_code"),
        "plate_number": bus.get("plate_number"),
        "status": bus.get("status", "active"),
        "route_id": str(bus.get("route_id")) if bus.get("route_id") else None,
        "latitude": (live_data or {}).get("latitude"),
        "longitude": (live_data or {}).get("longitude"),
    }