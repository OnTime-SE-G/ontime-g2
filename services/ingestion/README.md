# Ingestion Service

Receives telemetry and validates message contracts before publishing events.

## Responsibilities

- MQTT or simulator intake
- Schema validation
- Dead-letter routing for invalid payloads
- Publish clean events to Kafka topics

## Expected outputs

- `transport-telemetry-raw`
- `transport-telemetry-dlq`

## Ownership and Review

- Owner: Chamodh
- Required reviewer: Nathasha
- Optional reviewer: Janidu


