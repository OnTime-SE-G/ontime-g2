# Route Service

Route Service owns static route, stop, and geometry data. It is a private G2
service; external clients should call it through the API Gateway.

## Responsibilities

- Store route and stop data in PostgreSQL/PostGIS.
- Import and replace routes from KML files.
- Serve route geometry and stop lists to the API Gateway.
- Serve internal route geometry snapshots to Flink and Anomaly Service.

## HTTP Endpoints

Public-facing through API Gateway:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/routes` | list route summaries |
| `GET` | `/api/v1/routes/search` | search routes by start/end proximity |
| `GET` | `/api/v1/routes/{route_id}` | route detail with GeoJSON geometry |
| `GET` | `/api/v1/routes/{route_id}/progress` | compute route progress for a point |
| `GET` | `/api/v1/routes/{route_id}/stops` | ordered stops for a route |
| `GET` | `/api/v1/routes/{route_id}/buses` | buses assigned to a route |
| `GET` | `/api/v1/stops` | all stops |
| `GET` | `/api/v1/stops/nearby` | nearby stops |
| `GET` | `/api/v1/stops/{stop_id}/routes` | routes serving a stop |

Admin endpoints, protected by G4/Kong `ADMIN` role when exposed:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/admin/routes/add-route` | import a route from KML |
| `PUT` | `/api/v1/admin/routes/{route_id}` | replace an existing route |
| `DELETE` | `/api/v1/admin/routes/{route_id}` | delete route and stops |

Internal-only endpoints:

| Method | Path | Consumer |
|---|---|---|
| `GET` | `/internal/routes/geometry` | Flink, Anomaly Service |
| `GET` | `/health` | G4 probes |
| `GET` | `/` | metadata |

## Kafka, MQTT, Redis

Route Service does not publish or consume Kafka topics and does not use MQTT.
It currently does not publish Redis events.

## Prometheus / Probes

| Endpoint | Status |
|---|---|
| `GET /health` | implemented |
| `GET /metrics` | not implemented yet |

## Environment Variables

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/ontime_db` | PostgreSQL/PostGIS connection string |

## Deployment Notes For G4

- Container port: `8002`.
- Keep direct service access private inside the cluster.
- API Gateway should be the external route-service facade for G3.
