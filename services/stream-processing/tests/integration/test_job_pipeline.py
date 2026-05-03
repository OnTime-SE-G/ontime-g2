import pytest
from unittest.mock import MagicMock, patch
from app.job import run_telemetry_job

@patch("app.job.StreamExecutionEnvironment.get_execution_environment")
@patch("app.job.KafkaSource.builder")
@patch("app.job.KafkaSink.builder")
@patch("app.job.KafkaOffsetsInitializer")
@patch("app.job.KafkaRecordSerializationSchema.builder")
def test_run_telemetry_job_wiring(mock_schema_builder, mock_offsets, mock_kafka_sink_builder, mock_kafka_source_builder, mock_get_env):
    """Test that the Flink job wires up the sources, transforms, and sinks correctly."""

    # Setup mocks
    mock_env = MagicMock()
    mock_get_env.return_value = mock_env

    mock_source = MagicMock()
    mock_kafka_source_builder.return_value.set_bootstrap_servers.return_value \
        .set_topics.return_value.set_group_id.return_value \
        .set_starting_offsets.return_value.set_value_only_deserializer.return_value \
        .build.return_value = mock_source

    mock_offsets.earliest.return_value = MagicMock()

    mock_sink = MagicMock()
    mock_kafka_sink_builder.return_value.set_bootstrap_servers.return_value \
        .set_record_serializer.return_value.set_delivery_guarantee.return_value \
        .build.return_value = mock_sink

    mock_schema_builder.return_value.set_topic.return_value \
        .set_value_serialization_schema.return_value \
        .build.return_value = MagicMock()

    mock_ds = MagicMock()
    mock_env.from_source.return_value = mock_ds
    mock_ds.union.return_value = mock_ds
    mock_ds.key_by.return_value = mock_ds
    mock_ds.process.return_value = mock_ds
    mock_ds.map.return_value = mock_ds

    # Execute wiring
    run_telemetry_job()

    # Verify environment setup
    mock_get_env.assert_called_once()
    mock_env.set_parallelism.assert_called_with(1)

    # Verify sources are created (one for telemetry, one for lifecycle)
    assert mock_env.from_source.call_count == 2

    # Verify union and processing
    mock_ds.union.assert_called()
    mock_ds.process.assert_called()

    # Verify sinks are added
    assert mock_ds.map.call_count == 2 # Redis and InfluxDB
    mock_ds.sink_to.assert_called_with(mock_sink)

    # Verify execution
    mock_env.execute.assert_called_once()

    print(f"\n>>> PIPELINE WIRED SUCCESSFULLY: Sources={mock_env.from_source.call_count}, Transforms={mock_ds.process.call_count}, Sinks={mock_ds.map.call_count} + KafkaSink")
