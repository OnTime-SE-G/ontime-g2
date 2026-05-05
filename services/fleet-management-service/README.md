# Fleet Management Service

Fleet Management Service owns buses, drivers, schedules, planned trips, and trip
lifecycle transitions. It is a private G2 service; external clients should use
API Gateway.

## Responsibilities

- Create and manage fleet buses.
- Assign/unassign buses to routes after validating Route Service.
- Create drivers and schedules.
- Generate planned trips.
- Start/end driver trips.
- Publish trip lifecycle events to Kafka for ingestion and Flink.
- Expose health and Prometheus metrics.

## HTTP Endpoints

Private Fleet API:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/fleet/buses` | create bus |
| `GET` | `/api/v1/fleet/buses` | list buses |
| `GET` | `/api/v1/fleet/buses/{bus_id}` | bus detail |
| `PATCH` | `/api/v1/fleet/buses/{bus_id}/assign-route/{route_id}` | assign bus to route |
| `PATCH` | `/api/v1/fleet/buses/{bus_id}/unassign` | unassign bus route |
| `GET` | `/api/v1/fleet/buses/route/{route_id}` | buses assigned to route |
| `POST` | `/api/v1/fleet/drivers` | create driver profile |
| `GET` | `/api/v1/fleet/drivers` | list drivers |
| `POST` | `/api/v1/fleet/schedules` | create schedule |
| `GET` | `/api/v1/fleet/schedules` | list schedules |
| `POST` | `/api/v1/fleet/planned-trips/generate` | generate trips for a date |
| `GET` | `/api/v1/fleet/planned-trips/today` | today's trips |
| `GET` | `/api/v1/fleet/planned-trips/{trip_id}` | trip detail |
| `PATCH` | `/api/v1/fleet/planned-trips/{trip_id}/assign` | assign bus and driver |
| `POST` | `/api/v1/fleet/planned-trips/{trip_id}/start` | start trip |
| `POST` | `/api/v1/fleet/planned-trips/{trip_id}/end` | end trip |
| `POST` | `/api/v1/fleet/planned-trips/{trip_id}/delay` | report delay |
| `POST` | `/api/v1/fleet/planned-trips/{trip_id}/incident` | report incident |

Operations:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | DB-aware health |
| `GET` | `/health/live` | liveness |
| `GET` | `/health/ready` | readiness |
| `GET` | `/metrics` | Prometheus metrics |

## Kafka Topics

| Topic | Direction | Purpose |
|---|---|---|
| `trip.lifecycle` | produce | trip start/end/incident lifecycle events |

Trip start event example:

```json
{
  "event": "TRIP_STARTED",
  "busId": "1",
  "tripId": "TRIP-001",
  "routeId": "202",
  "timestamp": "2026-05-05T08:00:00Z"
}
```

`TRIP_ENDED` removes the bus from active-trip caches in ingestion and stream
processing.

## Environment Variables

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` / `FLEET_DATABASE_URL` | `postgresql://postgres:postgres@postgres:5432/fleet_db` | Fleet DB URL |
| `KAFKA_BROKER_URL` / `FLEET_KAFKA_BROKER_URL` | `broker:29092` | Kafka bootstrap server |
| `KAFKA_TRIP_LIFECYCLE_TOPIC` / `FLEET_KAFKA_TRIP_LIFECYCLE_TOPIC` | `trip.lifecycle` | lifecycle output topic |
| `ROUTE_SERVICE_URL` | `http://route-service:8002` | route validation API |

## MQTT / Redis

Fleet Management Service does not use MQTT or Redis directly.

## Driver Auth Plan

The current driver table stores transport driver profile data. Passwords and
login credentials should be created through Auth/Keycloak and linked to Fleet by
`auth_user_id` in the planned auth integration.
