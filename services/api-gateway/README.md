# API Gateway Service

Entry point for client-facing APIs.

## Responsibilities

- REST endpoints (`/health`, `/metrics`, `/api/v1/...`)
- WebSocket live feed endpoint
- Request validation and response shaping
- Authentication integration (with G4 security stack)

## Suggested structure

- `app/main.py` - FastAPI startup
- `app/api/` - route handlers
- `app/schemas/` - Pydantic models
- `tests/` - unit and integration tests for gateway behavior

## Ownership and Review

- Owner: Nathasha
- Required reviewer: Nidharshan
- Optional reviewer: Janidu


