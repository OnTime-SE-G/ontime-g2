# Flink CR1 Scaffold

This folder hosts the CR1 scaffold for the event-driven source-of-truth stage.

Current behavior in `job.py`:

- Defines canonical topic names:
  - `transport-telemetry-raw`
  - `transport-telemetry-cleaned`
  - `telemetry-invalid`
  - `trip.lifecycle`
- Provides pure helper functions for:
  - physics classification (`classify_physics`)
  - lifecycle cache updates (`route_lifecycle_event`)
  - trip-context enrichment (`enrich_with_trip_context`)
- Adds startup-cache hydration from microservice REST endpoints:
  - `fetch_startup_cache(route_service_url, fleet_service_url)`
  - `parse_route_cache_response(...)`
  - `parse_active_trip_cache_response(...)`

Notes:

- The file is import-safe without PyFlink installed, so unit tests can run in
  local CI environments.
- Kafka source/sink wiring and RocksDB-backed keyed state are intentionally not
  implemented in this scaffold yet.
