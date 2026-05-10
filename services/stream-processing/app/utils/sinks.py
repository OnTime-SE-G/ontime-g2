import json
import logging
import redis
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from app.config import settings

logger = logging.getLogger(__name__)

class RedisSink:
    def __init__(self):
        self.r = None

    def open(self):
        self.r = redis.Redis(host=settings.redis_host, port=settings.redis_port, db=0)

    def write(self, value: str):
        try:
            data = json.loads(value)
            bus_id = data.get("busId")
            if not bus_id:
                return

            # 1. Update position snapshot
            self.r.set(f"bus:{bus_id}:position", value)

            # 2. Publish to live feed
            self.r.publish(settings.redis_fleet_live_channel, value)
        except Exception as e:
            logger.error(f"Redis Sink error: {e}")

class InfluxDBSink:
    def __init__(self):
        self.client = None
        self.write_api = None

    def open(self):
        self.client = InfluxDBClient(
            url=settings.influxdb_url,
            token=settings.influxdb_token,
            org=settings.influxdb_org
        )
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)

    def write(self, value: str):
        try:
            data = json.loads(value)

            point = Point("gps_readings") \
                .tag("bus_id", data.get("busId", "unknown")) \
                .tag("route_id", data.get("routeId", "unknown")) \
                .tag("trip_id", data.get("tripId", "unknown")) \
                .field("lat", float(data.get("lat", 0.0))) \
                .field("lon", float(data.get("lon", 0.0))) \
                .field("speed", float(data.get("speed", 0.0))) \
                .field("heading", float(data.get("heading", 0.0))) \
                .field("progress", float(data.get("routeProgressPct", 0.0))) \
                .time(data.get("timestamp"), WritePrecision.NS)

            self.write_api.write(bucket=settings.influxdb_bucket, record=point)
        except Exception as e:
            logger.error(f"InfluxDB Sink error: {e}")

# Flink MapFunctions to wrap the sinks
from pyflink.datastream import MapFunction, RuntimeContext

class RedisSinkFunction(MapFunction):
    def __init__(self):
        self.sink = None

    def open(self, runtime_context: RuntimeContext):
        self.sink = RedisSink()
        self.sink.open()

    def map(self, value):
        self.sink.write(value)
        return value

class InfluxDBSinkFunction(MapFunction):
    def __init__(self):
        self.sink = None

    def open(self, runtime_context: RuntimeContext):
        self.sink = InfluxDBSink()
        self.sink.open()

    def map(self, value):
        self.sink.write(value)
        return value
