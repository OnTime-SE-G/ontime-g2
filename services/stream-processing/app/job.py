import logging
import os
import json
from datetime import datetime
from pyflink.common import WatermarkStrategy, Duration
from pyflink.common.watermark_strategy import TimestampAssigner
from pyflink.datastream import StreamExecutionEnvironment, RuntimeExecutionMode
from pyflink.datastream.connectors.kafka import KafkaSource, KafkaOffsetsInitializer
from pyflink.common.serialization import SimpleStringSchema

from app.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

def run_telemetry_job():
    # 1. Setup execution environment
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_runtime_mode(RuntimeExecutionMode.STREAMING)
    env.set_parallelism(1)  # Start with 1 for development
    
    # 2. Define Kafka Source for raw telemetry
    source = KafkaSource.builder() \
        .set_bootstrap_servers(settings.kafka_broker_url) \
        .set_topics(settings.kafka_raw_topic) \
        .set_group_id("stream-processing-group") \
        .set_starting_offsets(KafkaOffsetsInitializer.earliest()) \
        .set_value_only_deserializer(SimpleStringSchema()) \
        .build()

    # 3. Create DataStream with Watermarks
    watermark_strategy = WatermarkStrategy \
        .for_bounded_out_of_orderness(Duration.of_seconds(5)) \
        .with_timestamp_assigner(GPSTimestampAssigner())

    ds = env.from_source(source, watermark_strategy, "Kafka Raw Telemetry")

    # 4. Processing logic (Placeholder for Phase T2/T3)
    # Print the stream to verify consumption
    ds.print()
    
    logger.info("Starting Flink stream processing job...")
    
    # 5. Execute
    env.execute("OnTime GPS Telemetry Processing")

if __name__ == '__main__':
    run_telemetry_job()
