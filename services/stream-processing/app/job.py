import logging
import os
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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_telemetry_job():
    # 1. Setup execution environment
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_runtime_mode(RuntimeExecutionMode.STREAMING)
    env.set_parallelism(1)

    # 2. Define Kafka Source for raw telemetry
    telemetry_source = KafkaSource.builder() \
        .set_bootstrap_servers(settings.kafka_broker_url) \
        .set_topics(settings.kafka_raw_topic) \
        .set_group_id("stream-processing-group") \
        .set_starting_offsets(KafkaOffsetsInitializer.earliest()) \
        .set_value_only_deserializer(SimpleStringSchema()) \
        .build()

    # 3. Define Kafka Source for trip lifecycle events
    lifecycle_source = KafkaSource.builder() \
        .set_bootstrap_servers(settings.kafka_broker_url) \
        .set_topics(settings.kafka_lifecycle_topic) \
        .set_group_id("stream-processing-lifecycle-group") \
        .set_starting_offsets(KafkaOffsetsInitializer.earliest()) \
        .set_value_only_deserializer(SimpleStringSchema()) \
        .build()

    # 4. Create DataStreams with Watermarks
    watermark_strategy = WatermarkStrategy \
        .for_bounded_out_of_orderness(Duration.of_seconds(5)) \
        .with_timestamp_assigner(GPSTimestampAssigner())

    telemetry_ds = env.from_source(telemetry_source, watermark_strategy, "Kafka Raw Telemetry")
    lifecycle_ds = env.from_source(lifecycle_source, WatermarkStrategy.no_watermarks(), "Kafka Lifecycle Events")

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

    logger.info("Starting Flink stream processing job for Increment 1 Phase T2...")
    env.execute("OnTime GPS Telemetry Processing - Phase T2")

if __name__ == '__main__':
    run_telemetry_job()
