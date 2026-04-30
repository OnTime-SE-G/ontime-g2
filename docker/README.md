# Docker

Container and compose configuration for local infrastructure and services.

The ingestion setup now includes:

- `mqtt-broker` for G1 and simulator telemetry input
- `broker` for Kafka-compatible output
- `ingestion-service` for the validated MQTT-to-Kafka bridge

## Planned files

- `docker-compose.yml` for Kafka, PostgreSQL/PostGIS, Redis, and local services
- Service Dockerfiles either here or inside each service folder

Use `.env` values to keep environment-specific settings out of committed files.

From the repo root you can start the ingestion slice with:

```bash
docker compose -f docker/docker-compose.yml up -d broker mqtt-broker ingestion-service
```

## Ownership and Review

- Owner: Janidu
- Required reviewer: Nathasha
- Optional reviewer: Nidharshan

