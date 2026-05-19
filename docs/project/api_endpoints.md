# Backend API Endpoints

Here is a comprehensive list of all existing endpoints currently defined in your `ontime-g2` backend services, organized by service.

## API Gateway
*Serves as the entry point and provides aggregated health/metrics.*
- `GET /health` - Gateway health check and dependencies status.
- `GET /metrics` - Prometheus metrics for gateway requests.
- `GET /api/v1/status` - Basic API v1 status.

## Route Service
*Manages static route configurations, geospatial data, and stops.*
- `GET /` - Root endpoint, returns service metadata.
- `GET /health` - Route service health check.
- `GET /api/v1/routes` - List all available routes (summaries).
- `GET /api/v1/routes/search` - Search routes by proximity to start/end points.
- `GET /api/v1/routes/{route_id}` - Get full route GeoJSON (geometry and stops).
- `GET /api/v1/routes/{route_id}/progress` - Calculate bus progress along a route toward a target stop.
- `GET /api/v1/routes/{route_id}/stops` - List stops for a specific route in order.
- `GET /api/v1/routes/{route_id}/buses` - List buses currently assigned to a route (Currently a placeholder).

### Admin Routes
- `POST /api/v1/admin/routes/add-route` - Import a new route from a KML file.
- `PUT /api/v1/admin/routes/{route_id}` - Replace an existing route from a new KML file.
- `DELETE /api/v1/admin/routes/{route_id}` - Delete a route and its stops.

## Fleet Management Service
*Manages the bus fleet and static configurations.*
- `GET /health` - Fleet management service health check.
- `POST /api/v1/fleet/buses` - Create a new bus.
- `GET /api/v1/fleet/buses` - List all buses.
- `GET /api/v1/fleet/buses/{bus_id}` - Get details of a specific bus.
- `PATCH /api/v1/fleet/buses/{bus_id}/assign-route/{route_id}` - Assign a bus to a specific route.
- `PATCH /api/v1/fleet/buses/{bus_id}/unassign` - Unassign a bus from its current route.
- `GET /api/v1/fleet/buses/route/{route_id}` - Get all buses currently assigned to a specific route.

## Ingestion Service
*Handles incoming raw telemetry data from MQTT.*
- `GET /health` - Basic ingestion service health check.
- `GET /health/live` - Liveness probe.
- `GET /health/ready` - Readiness probe (checks MQTT and Kafka connections).
- `GET /metrics` - Prometheus metrics for ingestion pipeline.
