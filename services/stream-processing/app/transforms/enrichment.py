import json
import logging
from pyflink.datastream import KeyedProcessFunction, RuntimeContext
from pyflink.datastream.state import ValueStateDescriptor, MapStateDescriptor
from pyflink.common.typeinfo import Types
from app.utils.geo import calculate_route_progress, get_dist_along_route, haversine_distance
from app.utils.route_client import fetch_geometries_sync, fetch_stops_sync

logger = logging.getLogger(__name__)
logger = logging.getLogger(__name__)

from pyflink.common.watermark_strategy import TimestampAssigner
from datetime import datetime

class GPSTimestampAssigner(TimestampAssigner):
    def extract_timestamp(self, value, record_timestamp) -> int:
        try:
            data = json.loads(value)
            ts_str = data.get("timestamp")
            if ts_str:
                if ts_str.endswith('Z'):
                    ts_str = ts_str[:-1] + '+00:00'
                dt = datetime.fromisoformat(ts_str)
                return int(dt.timestamp() * 1000)
            return record_timestamp
        except Exception:
            return record_timestamp
class EnrichmentFunction(KeyedProcessFunction):
    """
    Enriches GPS telemetry with routeId and progress.
    Maintains a mapping of tripId -> routeId in state.
    """

    def __init__(self):
        self.trip_to_route_state = None
        self.route_geometries = {}
        # {routeId: [{id, name, stop_order, lat, lon, dist_along_route}, ...]}
        self.route_stops = {}

    def open(self, runtime_context: RuntimeContext):
        # State to store mapping of tripId to routeId for this bus
        state_desc = MapStateDescriptor("trip_to_route", Types.STRING(), Types.STRING())
        self.trip_to_route_state = runtime_context.get_map_state(state_desc)

        # State to store last processed timestamp per bus to deduplicate
        # Note: In a real system, you'd want a more complex deduplication key (bus + timestamp + coords)
        dedup_desc = ValueStateDescriptor("last_timestamp", Types.STRING())
        self.last_ts_state = runtime_context.get_state(dedup_desc)

        # Load route geometries at startup
        # In a real system, this should be refreshed periodically or pushed via broadcast
        logger.info("Fetching route geometries for enrichment...")
        self.route_geometries = fetch_geometries_sync()
        logger.info(f"Loaded {len(self.route_geometries)} route geometries.")

        # Load stop sequences for each route (used for stopsAhead computation)
        logger.info("Fetching route stops for stopsAhead enrichment...")
        for route_id, geom_points in self.route_geometries.items():
            raw_stops = fetch_stops_sync(route_id)
            enriched_stops = []
            for stop in raw_stops:
                stop_lat = stop.get("lat")
                stop_lon = stop.get("lon")
                if stop_lat is None or stop_lon is None:
                    continue
                dist_along = get_dist_along_route(stop_lat, stop_lon, geom_points)
                enriched_stops.append({
                    "id": stop["id"],
                    "name": stop["name"],
                    "stop_order": stop["stop_order"],
                    "lat": stop_lat,
                    "lon": stop_lon,
                    "dist_along_route": dist_along,
                })
            enriched_stops.sort(key=lambda s: s["stop_order"])
            self.route_stops[route_id] = enriched_stops
        logger.info(f"Loaded stops for {len(self.route_stops)} routes.")

    def process_element(self, value, ctx: KeyedProcessFunction.Context):
        if not value or not value.strip():
            return

        try:
            data = json.loads(value)

            # 1. Handle Trip Lifecycle Events
            if "event" in data:
                event_type = data["event"]
                bus_id = data["busId"]
                trip_id = data["tripId"]
                route_id = data.get("routeId")

                if event_type == "TRIP_STARTED" and route_id:
                    self.trip_to_route_state.put(trip_id, route_id)
                    logger.info(f"Bus {bus_id} started trip {trip_id} on route {route_id}")
                elif event_type == "TRIP_ENDED":
                    self.trip_to_route_state.remove(trip_id)
                    logger.info(f"Bus {bus_id} ended trip {trip_id}")
                return # Don't emit lifecycle events to the cleaned stream

            # 2. Handle GPS Telemetry
            bus_id = data.get("busId")
            trip_id = data.get("tripId")
            lat = data.get("lat")
            lon = data.get("lon")
            speed = data.get("speed", 0.0)
            ts = data.get("timestamp")

            # Late Data and Deduplication Check
            # We only process messages that are strictly newer than the last one seen for this bus
            last_ts = self.last_ts_state.value()
            if last_ts:
                # String comparison works for ISO8601 timestamps
                if ts <= last_ts:
                    logger.warning(f"Dropping late or duplicate message for bus {bus_id}: {ts} <= {last_ts}")
                    return
            self.last_ts_state.update(ts)

            # Sanity Check (Cleaning Phase)
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                return # Drop invalid coordinates
            if speed < 0 or speed > 250: # km/h
                return # Drop physically impossible speed, let anomaly handle 120-250

            # Enrichment: Lookup routeId from tripId
            route_id = self.trip_to_route_state.get(trip_id)

            if not route_id:
                # We emit with routeId=None so Anomaly Service can flag INACTIVE_GPS
                pass

            # Enrichment: Progress & Distance
            remaining_dist = 0.0
            progress_pct = 0.0
            deviation_m = 0.0
            next_stop_id = None
            distance_to_next_stop = 0.0
            stops_remaining = 0
            stops_ahead = []

            if route_id and route_id in self.route_geometries:
                geom = self.route_geometries[route_id]
                remaining_dist, progress_pct, deviation_m = calculate_route_progress(lat, lon, geom)

                route_stops = self.route_stops.get(route_id, [])
                if route_stops:
                    bus_dist_along = get_dist_along_route(lat, lon, geom)
                    for stop in route_stops:  # already sorted by stop_order
                        if stop["dist_along_route"] >= bus_dist_along:
                            dist_along_from_bus = stop["dist_along_route"] - bus_dist_along
                            stops_ahead.append({
                                "stopId": stop["id"],
                                "stopName": stop["name"],
                                "stopOrder": stop["stop_order"],
                                "distanceAlongRouteMeters": round(dist_along_from_bus, 2),
                            })
                    if stops_ahead:
                        stops_remaining = len(stops_ahead)
                        next_stop_id = stops_ahead[0]["stopId"]
                        distance_to_next_stop = stops_ahead[0]["distanceAlongRouteMeters"]

            enriched = {
                **data,
                "routeId": route_id,
                "remainingDistanceToNextStops": round(remaining_dist, 2),
                "routeProgressPct": round(progress_pct, 2),
                "nextStopId": next_stop_id,
                "distanceToNextStop": round(distance_to_next_stop, 2),
                "stopsRemaining": stops_remaining,
                "stopsAhead": stops_ahead,
                "onRoute": deviation_m < 50.0,
                "routeDeviationMeters": round(deviation_m, 2),
            }

            yield json.dumps(enriched)

        except Exception as e:
            logger.error(f"Error in EnrichmentFunction processing '{value}': {e}")
