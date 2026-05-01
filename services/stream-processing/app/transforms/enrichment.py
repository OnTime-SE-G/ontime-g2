import json
import logging
from pyflink.datastream import KeyedProcessFunction, RuntimeContext
from pyflink.datastream.state import ValueStateDescriptor, MapStateDescriptor
from pyflink.common.typeinfo import Types
from app.utils.geo import calculate_route_progress
from app.utils.route_client import fetch_geometries_sync

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

    def process_element(self, value, ctx: KeyedProcessFunction.Context):
        """
        Input can be either a GPSMessage (string) or a TripLifecycleEvent (string).
        We distinguish them by checking for the 'event' field.
        """
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
            
            # Deduplication
            last_ts = self.last_ts_state.value()
            if last_ts == ts:
                return # Skip duplicate
            self.last_ts_state.update(ts)

            # Sanity Check (Cleaning Phase)
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                return # Drop invalid coordinates
            if speed < 0 or speed > 150: # km/h
                return # Drop unrealistic speed

            # Enrichment: Lookup routeId from tripId
            route_id = self.trip_to_route_state.get(trip_id)
            
            if not route_id:
                # If we don't have the routeId from a lifecycle event, 
                # we can't fully enrich, but we still emit it with routeId=null 
                # or drop it depending on requirements.
                # Requirement 7.3: Flink enriches GPS with routeId.
                return 

            # Enrichment: Progress & Distance
            remaining_dist = 0.0
            progress_pct = 0.0
            
            if route_id in self.route_geometries:
                geom = self.route_geometries[route_id]
                remaining_dist, progress_pct = calculate_route_progress(lat, lon, geom)

            enriched = {
                **data,
                "routeId": route_id,
                "remainingDistance": round(remaining_dist, 2),
                "routeProgressPct": round(progress_pct, 2)
            }
            
            yield json.dumps(enriched)

        except Exception as e:
            logger.error(f"Error in EnrichmentFunction: {e}")
