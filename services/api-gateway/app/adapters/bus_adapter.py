def build_bus_data(bus, live_data=None):
    return {
        "id": str(bus["id"]),
        "number": bus.get("plate_number"),
        "routeId": str(bus.get("route_id")) if bus.get("route_id") else None,
        "driverName": bus.get("driver_name", "Unknown"),
        "status": (live_data or {}).get("status", "active"),
        "initProgress": (live_data or {}).get("progress", 0.0),
        "occupancyPct": (live_data or {}).get("occupancy", 0),
    }