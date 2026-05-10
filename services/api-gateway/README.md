# API Gateway

API Gateway is the G2 REST facade for G3. Public HTTP traffic should come from
G4 Kong to this service. It forwards business requests to private G2 services
and reads live snapshots from Redis where needed.

## Responsibilities

- Expose passenger, driver, and admin REST APIs under `/api/v1`.
- Proxy route queries to Route Service.
- Proxy fleet, trip, bus, driver, schedule, and incident actions to Fleet
  Management Service.
- Read live bus position snapshots from Redis for live map APIs.
- Expose `/health` and `/metrics` for G4.

## Public REST Endpoints Through Kong

Passenger/public for current scope:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/status` | gateway status |
| `GET` | `/api/v1/routes` | list routes |
| `GET` | `/api/v1/routes/search` | route search |
| `GET` | `/api/v1/routes/{route_id}` | route detail |
| `GET` | `/api/v1/routes/{route_id}/transit-data` | route + stops + buses aggregate |
| `GET` | `/api/v1/routes/all-transit-data` | full transit aggregate |
| `GET` | `/api/v1/routes/{route_id}/progress` | progress for a GPS point |
| `GET` | `/api/v1/routes/{route_id}/stops` | stops on route |
| `GET` | `/api/v1/routes/{route_id}/buses` | buses assigned to route |
| `GET` | `/api/v1/stops` | all stops |
| `GET` | `/api/v1/stops/nearby` | nearby stops |
| `GET` | `/api/v1/stops/{stop_id}/routes` | routes serving stop |
| `GET` | `/api/v1/buses/live` | latest live bus snapshots |
| `GET` | `/api/v1/buses/route/{route_id}` | buses on route |
| `GET` | `/api/v1/buses/{bus_id}` | bus detail |
| `GET` | `/api/v1/trips/{trip_id}/state` | planned trip state |

Driver routes, protected by Kong `DRIVER` role:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/driver/trips/today` | driver's planned trips |
| `POST` | `/api/v1/driver/trips/{trip_id}/start` | start trip; Fleet emits `trip.lifecycle` |
| `POST` | `/api/v1/driver/trips/{trip_id}/end` | end trip; Fleet emits `trip.lifecycle` |
| `POST` | `/api/v1/driver/trips/{trip_id}/report-delay` | delay report |
| `POST` | `/api/v1/driver/trips/{trip_id}/report-incident` | incident report |

Admin routes, protected by Kong `ADMIN` role:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/admin/routes/add-route` | import route |
| `PUT` | `/api/v1/admin/routes/{route_id}` | replace route |
| `DELETE` | `/api/v1/admin/routes/{route_id}` | delete route |
| `POST` | `/api/v1/admin/fleet/buses` | create bus |
| `PUT` | `/api/v1/admin/fleet/buses/{bus_id}` | update bus |
| `DELETE` | `/api/v1/admin/fleet/buses/{bus_id}` | delete bus |
| `GET` | `/api/v1/admin/fleet/buses` | list buses |
| `GET` | `/api/v1/admin/fleet/buses/{bus_id}` | bus detail |
| `GET` | `/api/v1/admin/fleet/buses/route/{route_id}` | route buses |
| `POST` | `/api/v1/admin/fleet/buses/{bus_id}/assign-route/{route_id}` | assign route via gateway |
| `POST` | `/api/v1/admin/fleet/buses/{bus_id}/unassign` | unassign route via gateway |
| `POST` | `/api/v1/admin/fleet/drivers` | create driver profile; auth integration planned |
| `GET` | `/api/v1/admin/fleet/drivers` | list drivers |
| `POST` | `/api/v1/admin/fleet/schedules` | create schedule |
| `GET` | `/api/v1/admin/fleet/schedules` | list schedules |
| `POST` | `/api/v1/admin/fleet/planned-trips/generate` | generate daily trips |
| `GET` | `/api/v1/admin/fleet/planned-trips/today` | today's planned trips |
| `GET` | `/api/v1/admin/fleet/planned-trips/{trip_id}` | trip detail |
| `PATCH` | `/api/v1/admin/fleet/planned-trips/{trip_id}/assign` | assign bus/driver |
| `POST` | `/api/v1/admin/fleet/planned-trips/{trip_id}/delay` | admin delay update |
| `POST` | `/api/v1/admin/fleet/planned-trips/{trip_id}/incident` | admin incident update |

## Operations

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | dependency summary |
| `GET` | `/metrics` | Prometheus text metrics |

## Environment Variables

| Variable | Default | Meaning |
|---|---|---|
| `ROUTE_SERVICE_URL` | `http://route-service:8002` | private Route Service URL |
| `FLEET_SERVICE_URL` | `http://fleet-management-service:8003` | private Fleet Service URL |
| `REDIS_URL` | `redis://redis:6379/0` | live bus snapshot Redis |
| `AUTH_SERVICE_URL` | planned `http://auth-service:8005` | future Auth wrapper/G4 Auth URL |
| `POSTGRES_HOST` | `localhost` | used by `/health` dependency check |
| `POSTGRES_PORT` | `5432` | used by `/health` dependency check |
| `REDIS_HOST` | `localhost` | used by `/health` dependency check |
| `REDIS_PORT` | `6379` | used by `/health` dependency check |
| `KAFKA_HOST` | `localhost` | used by `/health` dependency check |
| `KAFKA_PORT` | `9092` | used by `/health` dependency check |
| `INFLUXDB_HOST` | `localhost` | used by `/health` dependency check |
| `INFLUXDB_PORT` | `8086` | used by `/health` dependency check |

## Kafka, MQTT, Redis

- API Gateway does not directly publish or consume Kafka in the current code.
- API Gateway does not use MQTT.
- API Gateway reads Redis for live bus snapshots through route handlers.

## G4 / Kong Notes

- Expose API Gateway publicly through Kong.
- Enforce `ADMIN` on `/api/v1/admin/*`.
- Enforce `DRIVER` on `/api/v1/driver/*`.
- Keep private service URLs internal to the cluster.
