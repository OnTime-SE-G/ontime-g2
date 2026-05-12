import logging
import json
from datetime import datetime
from pyflink.common import WatermarkStrategy, Duration, Types
from pyflink.common.watermark_strategy import TimestampAssigner
from pyflink.datastream import StreamExecutionEnvironment, RuntimeExecutionMode
from pyflink.datastream.connectors.kafka import KafkaSource, KafkaOffsetsInitializer, KafkaSink, DeliveryGuarantee, KafkaRecordSerializationSchema
from pyflink.common.serialization import SimpleStringSchema

from app.config import settings
from app.transforms.enrichment import EnrichmentFunction, GPSTimestampAssigner
from app.utils.sinks import RedisSinkFunction, InfluxDBSinkFunction
from schemas.geo_config import SRI_LANKA_BOUNDS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _invalid_wrapper(payload, reason: str):
    if isinstance(payload, dict):
        candidate = dict(payload)
    else:
        candidate = {"original_payload": str(payload)}
    candidate["_invalid_reason"] = reason
    return {"kind": "invalid", "payload": candidate}


def _cleaned_wrapper(payload: dict):
    return {"kind": "cleaned", "payload": payload}


def classify_raw_telemetry(value: str) -> str:
    """Split raw telemetry into CR1 cleaned candidates or telemetry-invalid records."""
    try:
        payload = json.loads(value)
    except Exception:
        return json.dumps(_invalid_wrapper(value, "MALFORMED_JSON"))

    if not isinstance(payload, dict):
        return json.dumps(_invalid_wrapper(payload, "MALFORMED_JSON"))

    try:
        lat = float(payload.get("lat"))
        lon = float(payload.get("lon"))
    except (TypeError, ValueError):
        return json.dumps(_invalid_wrapper(payload, "MISSING_OR_INVALID_COORDINATES"))

    if not SRI_LANKA_BOUNDS.contains(lat=lat, lon=lon):
        return json.dumps(_invalid_wrapper(payload, "OUT_OF_SRI_LANKA_BOUNDS"))

    try:
        speed = float(payload.get("speed", 0.0))
    except (TypeError, ValueError):
        return json.dumps(_invalid_wrapper(payload, "INVALID_SPEED"))

    if speed < 0 or speed > 200:
        return json.dumps(_invalid_wrapper(payload, "UNREALISTIC_SPEED"))

    return json.dumps(_cleaned_wrapper(payload))


def is_cleaned_wrapper(value: str) -> bool:
    return json.loads(value).get("kind") == "cleaned"


def is_invalid_wrapper(value: str) -> bool:
    return json.loads(value).get("kind") == "invalid"


def unwrap_payload_json(value: str) -> str:
    return json.dumps(json.loads(value)["payload"])

def run_telemetry_job():
    # 1. Setup execution environment
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_runtime_mode(RuntimeExecutionMode.STREAMING)
    env.set_parallelism(settings.flink_parallelism)
    env.enable_checkpointing(10000)  # flush Kafka sinks every 10 s

    # 2. Define Kafka Source for raw telemetry
    telemetry_source = KafkaSource.builder() \
        .set_bootstrap_servers(settings.kafka_broker_url) \
        .set_topics(settings.kafka_raw_topic) \
        .set_group_id(settings.kafka_consumer_group) \
        .set_starting_offsets(KafkaOffsetsInitializer.earliest()) \
        .set_value_only_deserializer(SimpleStringSchema()) \
        .build()

    # 3. Define Kafka Source for trip lifecycle events
    lifecycle_source = KafkaSource.builder() \
        .set_bootstrap_servers(settings.kafka_broker_url) \
        .set_topics(settings.kafka_lifecycle_topic) \
        .set_group_id(settings.kafka_lifecycle_consumer_group) \
        .set_starting_offsets(KafkaOffsetsInitializer.earliest()) \
        .set_value_only_deserializer(SimpleStringSchema()) \
        .build()

    # 4. Create DataStreams with Watermarks
    watermark_strategy = WatermarkStrategy \
        .for_bounded_out_of_orderness(Duration.of_seconds(5)) \
        .with_timestamp_assigner(GPSTimestampAssigner())

    raw_telemetry_ds = env.from_source(telemetry_source, watermark_strategy, "Kafka Raw Telemetry")
    lifecycle_ds = env.from_source(lifecycle_source, WatermarkStrategy.no_watermarks(), "Kafka Lifecycle Events")

    classified_ds = raw_telemetry_ds.map(
        classify_raw_telemetry,
        output_type=Types.STRING(),
    ).name("CR1 Physics Classifier")

    telemetry_ds = classified_ds \
        .filter(is_cleaned_wrapper) \
        .map(unwrap_payload_json, output_type=Types.STRING()) \
        .name("CR1 Cleaned Candidates")

    invalid_ds = classified_ds \
        .filter(is_invalid_wrapper) \
        .map(unwrap_payload_json, output_type=Types.STRING()) \
        .name("CR1 Invalid Telemetry")

    # 5. Union and Process
    # Both streams are strings (JSON), so we can union them and key by busId
    # Extract busId for keying
    def extract_bus_id(value):
        try:
            return json.loads(value)["busId"]
        except:
            return "unknown"

    processed_ds = telemetry_ds.union(lifecycle_ds) \
        .key_by(extract_bus_id) \
        .process(EnrichmentFunction(), output_type=Types.STRING())

    # 6. Sinks

    # - Redis Sink (Position Snapshot and Pub/Sub)
    processed_ds.map(RedisSinkFunction(), output_type=Types.STRING()).name("Redis Sink")

    # - InfluxDB Sink (Historical Data)
    processed_ds.map(InfluxDBSinkFunction(), output_type=Types.STRING()).name("InfluxDB Sink")

    # - Kafka Sink (Cleaned and Enriched stream for downstream services)
    kafka_sink = KafkaSink.builder() \
        .set_bootstrap_servers(settings.kafka_broker_url) \
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder()
                .set_topic(settings.kafka_cleaned_topic)
                .set_value_serialization_schema(SimpleStringSchema())
                .build()
        ) \
        .set_delivery_guarantee(DeliveryGuarantee.AT_LEAST_ONCE) \
        .build()

    processed_ds.sink_to(kafka_sink).name("Kafka Cleaned Sink")

    # - Kafka Sink (physics-invalid telemetry for observability)
    invalid_sink = KafkaSink.builder() \
        .set_bootstrap_servers(settings.kafka_broker_url) \
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder()
                .set_topic(settings.kafka_invalid_topic)
                .set_value_serialization_schema(SimpleStringSchema())
                .build()
        ) \
        .set_delivery_guarantee(DeliveryGuarantee.AT_LEAST_ONCE) \
        .build()

    invalid_ds.sink_to(invalid_sink).name("Kafka Invalid Telemetry Sink")

    # - Kafka Sink (ETA-enriched stream for ETA Service — transport-eta-features topic)
    eta_features_sink = KafkaSink.builder() \
        .set_bootstrap_servers(settings.kafka_broker_url) \
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder()
                .set_topic(settings.kafka_eta_features_topic)
                .set_value_serialization_schema(SimpleStringSchema())
                .build()
        ) \
        .set_delivery_guarantee(DeliveryGuarantee.AT_LEAST_ONCE) \
        .build()

    processed_ds.sink_to(eta_features_sink).name("Kafka ETA Features Sink")

    logger.info("Starting Flink stream processing job for Increment 1 Phase T2...")
    env.execute("OnTime GPS Telemetry Processing - Phase T2")

if __name__ == '__main__':
    run_telemetry_job()
