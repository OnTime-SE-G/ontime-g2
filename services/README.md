# Services
.
This folder contains all microservices owned by G2.

## Service list

- `api-gateway` - public REST and WebSocket APIs
- `ingestion` - GPS/event validation and ingestion
- `stream-processing` - stream transformations and feature pipelines
- `route-service` - route and stop data APIs
- `eta-service` - ETA prediction APIs (future increment)
- `anomaly-service` - anomaly detection APIs (future increment)

Each service should keep its own source code, tests, config, and Dockerfile.

When a service grows beyond a couple of files, prefer a dedicated `app/` package for runtime code. The ingestion service now follows that layout under `services/ingestion/app/`.

## Ownership and Review

- API integration and route service owner: Nathasha
- Data pipeline service owner: Chamodh
- Required cross-service reviewer: Nidharshan
- Infra reviewer for service runtime concerns: Janidu

