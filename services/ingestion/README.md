# Ingestion Service

Receives GPS telemetry from MQTT, validates against the shared `GPSMessage` schema, and bridges valid messages to Kafka. Invalid messages are routed to a Dead Letter Queue (DLQ) with error metadata.

## Architecture

```
G1 Devices / Simulator ──MQTT──▶ Mosquitto ──▶ Ingestion Service ──▶ Kafka
                                                     │
                                                     └──▶ DLQ (invalid messages)
```

## Responsibilities

- Subscribe to MQTT topic `transport/bus/+/location`
- Validate GPS payloads against `GPSMessage` Pydantic schema
- Validate coordinates within Sri Lanka bounding box
- Detect duplicate messages, enforce rate limits, check timestamp sequence
- Produce valid messages to `transport-telemetry-raw` Kafka topic
- Route invalid messages to `transport-telemetry-dlq` with error reason
- Expose `/health` and `/metrics` endpoints on port 8001

## Kafka Topics (Output)

| Topic | Content |
|-------|---------|
| `transport-telemetry-raw` | Validated GPS messages (consumed by Natasha's Flink) |
| `transport-telemetry-dlq` | Invalid messages + error metadata (debug/monitoring) |

## Running Locally

```bash
# From repo root
cd services/ingestion
pip install -r requirements.txt
python main.py
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MQTT_BROKER_HOST` | `mqtt-broker` | Mosquitto broker hostname |
| `MQTT_BROKER_PORT` | `1883` | Mosquitto broker port |
| `MQTT_TOPIC_PATTERN` | `transport/bus/+/location` | MQTT subscription pattern |
| `KAFKA_BROKER_URL` | `broker:29092` | Kafka bootstrap server |
| `KAFKA_RAW_TOPIC` | `transport-telemetry-raw` | Output topic for valid messages |
| `KAFKA_DLQ_TOPIC` | `transport-telemetry-dlq` | Output topic for invalid messages |
| `SERVICE_PORT` | `8001` | Health/metrics endpoint port |

## Ownership and Review

- **Owner:** Janidu
- **Required reviewer:** Natasha (consumes from `transport-telemetry-raw`)
- **Optional reviewer:** Kusal (shared schemas, docker-compose)
