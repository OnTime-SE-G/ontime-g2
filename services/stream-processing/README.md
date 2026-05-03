# Stream Processing Service (PyFlink)

PyFlink job for event-time stream processing of GPS telemetry.

## Responsibilities

- **Clean Telemetry**: Deduplicate, apply watermarks, and filter out-of-bounds coordinates.
- **Enrich GPS**: Map `trip_id` to `route_id` and calculate route progress percentage.
- **Live State**: Write latest positions to Redis and publish updates via Redis Pub/Sub.
- **Historical Data**: Write cleaned telemetry to InfluxDB.
- **Cleaned Stream**: Publish enriched messages to Kafka topic `transport-telemetry-cleaned`.

## Folder Structure

```text
services/stream-processing/
├── app/
│   ├── transforms/    # Data transformation and enrichment logic
│   ├── utils/         # Helper clients (Redis, InfluxDB, etc.)
│   ├── config.py      # Service configuration
│   ├── job.py         # Main PyFlink job entry point
│   └── schema.py      # Flink schemas for Kafka sources/sinks
├── tests/             # Unit and integration tests
├── Dockerfile         # PyFlink-based image
└── requirements.txt   # Python dependencies
```

## Ownership and Review

- **Primary Owner**: Natasha
- **Secondary Responsibility**: Kusal (Infrastructure)
- **Reviewers**: Chamodh, Nidharshan
