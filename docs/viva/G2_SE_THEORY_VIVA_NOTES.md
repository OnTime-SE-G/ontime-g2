# OnTime G2 Software Engineering Viva Notes

This document maps Software Engineering theory topics to what our G2 project
actually did. It is written for viva answers: simple, honest, and connected to
repo evidence.

## 1. Overall Process We Followed

The best description of our process is:

> We followed a hybrid software process. At the overall project level we used a
> plan-driven approach to define architecture, increments, contracts, services,
> ports, and ownership. Inside each subgroup and service we worked in an agile
> and Kanban-style way using user stories, tasks, branches, PRs, CI checks, and
> incremental delivery.

Why hybrid was suitable:

- The project had 20 students split into 4 subgroups.
- G2 had 5 members and several microservices.
- Cross-group interfaces had to be stable, so we needed early planning.
- Implementation details changed often, so each subgroup needed agile iteration.
- CI, PR reviews, and incremental releases helped us manage integration risk.

## 2. Requirements Engineering Process

### 2.1 What Requirements Engineering Means

Requirements Engineering is the process of discovering, analyzing, specifying,
validating, and managing what the system should do and under what constraints.

The common RE activities are:

1. Elicitation
2. Analysis and negotiation
3. Specification
4. Validation
5. Requirements management

### 2.2 How We Did Elicitation

Honest answer:

> We did not conduct formal stakeholder interviews with real passengers,
> drivers, or transport operators. Instead, we derived requirements from the
> project problem, SRS/business plan, lecturer feedback, cross-group meetings,
> and assumptions about the expected passenger, driver, admin, G1, G3, and G4
> needs.

Sources we used:

- SRS and business-plan documents.
- Project planning docs.
- Increment plans.
- CR1 and CR2 change request documents.
- Cross-group boundaries:
  - G1 gives GPS and heartbeat.
  - G3 needs REST and WebSocket data.
  - G4 handles Kong, auth, deployment, monitoring.
- Instructor/project feedback.
- Repo issues, branches, PRs, and CI failures.

Stakeholders we considered:

| Stakeholder | Need |
|---|---|
| Passenger | See routes, live buses, ETA, crowd level |
| Driver | Start/end trips, report delay/incidents |
| Admin/operator | Manage routes/fleet and monitor anomalies |
| G1 | Simple MQTT GPS/heartbeat contract |
| G3 | Stable REST/WebSocket APIs |
| G4 | Docker images, ports, probes, env vars, metrics |
| Developers | Clear service boundaries and shared schemas |

### 2.3 Functional Requirements We Identified

Functional requirements are what the system must do.

Main G2 FRs:

- Receive GPS from bus devices or simulator through MQTT.
- Validate GPS and heartbeat payloads.
- Publish valid GPS to Kafka.
- Send invalid GPS to a DLQ with reasons.
- Maintain/consume trip lifecycle state.
- Store and serve routes and stops.
- Manage buses, drivers, schedules, and planned trips.
- Allow driver trip start/end and incident/delay reporting.
- Process telemetry in Flink.
- Enrich GPS with route, trip, progress, and stop distance.
- Push live bus positions through WebSocket.
- Calculate ETA for upcoming stops.
- Detect anomalies such as off-route, stationary, unrealistic speed,
  communication loss, and erratic driving.
- Accept passenger crowd reports.
- Predict crowd occupancy using historical ML and live trust-weighted reports.

### 2.4 Non-Functional Requirements We Identified

Non-functional requirements are quality constraints.

Main G2 NFRs:

| NFR | How the repo addresses it |
|---|---|
| Performance | Kafka, Flink, Redis Pub/Sub, WebSocket live path |
| Scalability | Event-driven microservices; Kafka topics decouple producers/consumers |
| Reliability | DLQ, health/readiness endpoints, Docker health checks |
| Maintainability | Service folders, READMEs, shared schemas, config files |
| Testability | Unit tests, integration tests, E2E smoke test, BDD tests |
| Security boundary | G4 Kong/auth boundary; public traffic through API Gateway/WebSocket |
| Observability | `/metrics`, health endpoints, DLQ, telemetry-invalid topic |
| Configurability | Environment variables via `config.py` and `.env.example` |
| Evolvability | CR1/CR2 documents, model cascade fallbacks, MLflow registry |

### 2.5 Requirements Specification

We specified requirements using:

- Root and service READMEs.
- `docs/PROJECT_PLAN.md`.
- Increment plans.
- `docs/CR_1.md` for event-driven architecture.
- `docs/CR2_MODEL_FORTIFICATION_PLAN.md` for model fortification.
- Shared Pydantic schemas in `schemas/`.
- Kafka topic names and payload examples.
- Redis channel/key contracts.
- Docker `.env.example`.
- API routes in FastAPI routers.
- CI workflow files.

Simple viva answer:

> Our requirements were not only in one SRS document. They were spread across
> SRS, increment plans, service READMEs, shared schemas, API routes, and CI
> checks. These together became our executable specification.

### 2.6 Requirements Validation

We validated requirements by:

- Reviewing PRs before merging.
- Running GitHub Actions CI.
- Writing unit tests for services.
- Writing integration tests for service interactions.
- Running a live pipeline E2E smoke test.
- Checking API contracts through FastAPI and tests.
- Running demo flows with Docker Compose.

### 2.7 Requirements Management and Change

Requirements changed during the project. We handled this with change request
documents and branches.

Important examples:

- CR1 moved the architecture toward event-driven "source of truth" processing
  using Flink.
- CR2 fortified ETA and anomaly models with smoothing, fallbacks, Isolation
  Forest, DBSCAN, and audience-specific anomaly routing.
- New crowd-sensing service was added later through its own branch and PR.
- CI failures and deployment failures led to hotfix branches.

Good viva sentence:

> We managed evolving requirements using change request documents, branches,
> PRs, and incremental releases instead of changing everything directly on main.

## 3. Software Process Model

### 3.1 Plan-Driven Part

At the beginning and at major architecture changes, we used plan-driven work.

Examples:

- Defined service ownership.
- Defined service ports.
- Defined Kafka topics.
- Defined Redis channels.
- Defined group boundaries.
- Defined Docker infrastructure.
- Created increment plans.
- Wrote architecture diagrams and service contracts.

Why plan-driven was needed:

- Many teams had to integrate.
- G1, G3, and G4 depended on our contracts.
- Changing topic names or API paths randomly would break other groups.

### 3.2 Agile/Kanban Part

Inside G2, implementation was more agile.

We worked using:

- user stories and tasks,
- Kanban board,
- branches per feature/fix,
- PRs,
- reviewer approvals,
- CI checks before merge,
- service-level ownership,
- incremental demoable outputs.

Typical Kanban columns:

- Backlog
- Ready
- In Progress
- Review
- Testing/CI
- Done

Good viva answer:

> We did not follow pure Scrum strictly. It was closer to hybrid agile with
> Kanban execution. We used planned increments and then pulled tasks through a
> board until they were implemented, reviewed, tested, and merged.

### 3.3 Incremental Delivery

The repo history shows incremental delivery:

| Increment/wave | What was delivered |
|---|---|
| Foundation | Docker, PostgreSQL/PostGIS, Redis, Kafka, scripts, route seeding |
| Ingestion | MQTT validation, Kafka raw/DLQ, metrics, tests |
| Route/Fleet | Route APIs, fleet CRUD, route assignment, planned trips |
| Live pipeline | Flink processing, Redis live state, WebSocket |
| Anomaly | Rule alerts, DLQ analysis, Isolation Forest, later CR2 DBSCAN |
| ETA | Physics, XGBoost, SARIMA, smoothing, Redis live ETA, DB persistence |
| MLOps | MLflow and Airflow/profile-based training support |
| Crowd sensing | Passenger reports, trust engine, hybrid occupancy prediction |
| Cleanup/evolution | Docs cleanup, config standardization, service standardization |

## 4. Project Planning, Estimation, and Velocity

### 4.1 Planning Approach

Planning was done in layers:

1. Identify high-level features from SRS and project goals.
2. Convert features into user stories and service tasks.
3. Group stories into increments/releases.
4. Assign service ownership to team members.
5. Track work using the Kanban board.
6. Use PRs and CI checks as merge gates.
7. Demo working increments.

### 4.2 Estimation Approach

We mainly used experience-based estimation and relative complexity.

This means:

- We estimated by comparing tasks to similar previous work.
- Small tasks included docs, config, simple endpoints, unit tests.
- Medium tasks included routers, service clients, DB models, CI workflows.
- Large tasks included Flink processing, ETA model cascade, anomaly model,
  end-to-end integration, Docker orchestration.

Honest viva answer:

> We did not use formal Function Point Analysis or COCOMO. Because this was a
> student project with fast-changing requirements, we used expert judgment and
> relative estimation based on complexity, dependencies, and uncertainty.

### 4.3 Velocity

Velocity is how much work a team completes in a time period.

How we can explain our velocity:

- We measured progress by completed user stories, PRs merged, and services
  passing CI.
- At service level, velocity was visible through completed branches and commits.
- At release level, velocity was visible through increments: ingestion, route,
  fleet, stream processing, anomaly, ETA, crowd sensing.
- CI passing was part of "done", so a story was not counted complete only
  because code was written.

Example viva phrasing:

> Our practical velocity metric was completed and merged PRs per increment,
> plus whether the service passed its unit/integration tests. We used this
> because our tasks were service-based and not all tasks had equal size.

### 4.4 Definition of Done

A task or service was considered done when:

- implementation was complete,
- configuration was added,
- service README/docs were updated,
- unit tests were added or updated,
- integration tests were added for risky flows,
- Docker build or compose config worked where relevant,
- CI checks passed,
- PR was reviewed and merged.

## 5. Design and Implementation

### 5.1 Architecture Style

The main architecture style is:

- microservices,
- event-driven architecture,
- stream processing,
- model-based intelligence services,
- REST plus WebSocket delivery.

### 5.2 Main Design Decisions

| Decision | Reason |
|---|---|
| Microservices | Each team member/service has clear ownership and can be tested separately |
| Kafka topics | Decouple producers and consumers |
| MQTT for GPS | Fits IoT device communication |
| Flink for stream processing | Handles real-time event-time processing and enrichment |
| Redis Pub/Sub | Fast live updates to WebSocket |
| PostgreSQL/PostGIS | Good for relational and route geometry data |
| InfluxDB | Good for telemetry history and ML training |
| MLflow | Model registry and artifact loading |
| Docker Compose | Repeatable local environment |
| GitHub Actions | Automated verification before merge |

### 5.3 Separation of Concerns

We separated responsibilities:

- Ingestion validates input and sends Kafka messages.
- Flink cleans/enriches real-time telemetry.
- Route Service owns routes/stops.
- Fleet Service owns buses/trips.
- ETA Service owns ETA prediction.
- Anomaly Service owns anomaly detection.
- WebSocket Service owns connected clients.
- API Gateway owns REST aggregation.
- Crowd Sensing owns passenger reports and occupancy prediction.

Good viva answer:

> Each service owns one bounded context. If another service needs the data, it
> uses REST or Kafka instead of reading another service's database directly.

### 5.4 Design Patterns and Practices

Practices used in the repo:

- Layered FastAPI services with routers, services, models/schemas.
- Pydantic settings in `config.py`.
- Shared schemas for cross-service contracts.
- Producer/consumer pattern with Kafka.
- Pub/Sub pattern with Redis.
- Repository/database helpers in data-heavy services.
- Fallback model cascade in ETA.
- Sliding window feature extraction in Anomaly.
- Dependency injection/mocking in tests.
- Health/readiness/metrics endpoints for operations.

### 5.5 Implementation Technologies

| Area | Technology |
|---|---|
| REST APIs | FastAPI |
| Data validation | Pydantic |
| Config | pydantic-settings, env vars |
| Message broker | Kafka-compatible broker |
| IoT input | MQTT/Mosquitto |
| Stream processing | PyFlink |
| Live state | Redis |
| Relational DB | PostgreSQL |
| Spatial DB | PostGIS |
| Time-series | InfluxDB |
| ML | XGBoost, SARIMA, Isolation Forest, DBSCAN in CR2 |
| ML registry | MLflow |
| Containers | Docker, Docker Compose |
| CI/CD | GitHub Actions |

## 6. Testing, Verification, and Validation

### 6.1 Difference Between Verification and Validation

Verification asks:

> Are we building the product right?

Validation asks:

> Are we building the right product?

### 6.2 Verification in Our Project

Verification activities:

- Unit tests for individual functions/classes.
- Config tests to ensure env vars load correctly.
- API router tests.
- Model logic tests.
- CI workflows for each service.
- Docker build workflows.
- PR reviews.
- Static contract checks through schemas and tests.

Examples from repo:

- Ingestion tests for validator, MQTT subscriber, producer, health/metrics,
  trip lifecycle cache, config consumer.
- Stream-processing tests for Flink job logic, enrichment, geo calculations,
  route client, stop resolution, dwell calculation.
- Anomaly tests for anomaly model, config, feature extraction.
- ETA tests for consumer, endpoint, physics, XGBoost, SARIMA, inference router.
- API Gateway tests for routes, stops, buses, driver, admin fleet, config.
- Fleet tests for fleet APIs, trips, health, lifespan, route service.
- Crowd tests for endpoints, consumer, trust engine, validation.

### 6.3 Validation in Our Project

Validation activities:

- E2E live pipeline smoke test.
- Integration tests with Docker, Kafka, MQTT, Redis, route/fleet/websocket.
- BDD scenarios for crowd sensing.
- Demo flows through Docker Compose.
- Cross-group contract checks with G1/G3/G4 expectations.

Main E2E flow tested:

```text
Fleet creates route/bus/driver/trip
  -> trip starts
  -> MQTT GPS is published
  -> Ingestion writes raw Kafka telemetry
  -> Flink publishes cleaned enriched telemetry
  -> Redis stores latest bus position
  -> WebSocket returns live snapshot
```

Good viva answer:

> Unit tests verified isolated logic. Integration tests verified service
> interaction. E2E smoke tests validated that the user-visible live tracking
> pipeline works from trip start to WebSocket output.

### 6.4 CI Before Merging

The repo uses GitHub Actions workflows such as:

- `test_ingestion.yml`
- `test_api_gateway.yml`
- `test_stream_processing.yml`
- `test_anomaly_service.yml`
- `test_eta_service.yml`
- `test_crowd_sensing.yml`
- `test_live_pipeline_e2e.yml`
- `fleet_ci.yml`
- `route-service-ci.yml`
- `websocket-service-ci.yml`
- `image_publish.yml`

Why this matters:

- PRs are checked automatically.
- Broken tests block safe merging.
- Different service owners can work independently.
- CI gives repeatable verification.

### 6.5 Testing Limitations

Honest limitations:

- Some E2E tests need Docker, so they are slower and more fragile.
- Load testing is planned but not as complete as unit/integration testing.
- Real stakeholder acceptance testing was limited.
- Some docs and branches need cleanup to match current implementation.

## 7. Project Management

### 7.1 Team Organization

The project had 20 members split into 4 subgroups. G2 had 5 members. G2 work
was divided mostly by service ownership.

Service ownership advantages:

- Reduced merge conflicts.
- Clear responsibility.
- Easier testing.
- Easier PR review because each service has one main owner.

### 7.2 Coordination

Coordination happened through:

- Kanban board,
- GitHub branches and PRs,
- service READMEs,
- shared schemas,
- Docker `.env.example`,
- architecture plans,
- CI workflows,
- cross-group meetings.

### 7.3 Risk Management

Main risks and mitigations:

| Risk | Mitigation |
|---|---|
| G1 hardware delay | GPS simulator and MQTT test data |
| Cross-group mismatch | Contract-first topics, REST paths, schemas, README docs |
| ML model uncertainty | Physics fallback and model cascade |
| Integration failure | Docker Compose and E2E smoke tests |
| Service coupling | Kafka/Redis/REST boundaries instead of direct DB sharing |
| Deployment failure | Dockerfiles, health endpoints, CI/CD workflows |
| Scope creep | Increment planning and CR documents |

### 7.4 Release Planning

We planned work as releases/increments:

- Increment 0: infrastructure and skeletons.
- Increment 1: GPS pipeline, route/fleet, live map, trip lifecycle.
- Increment 2: streaming architecture, ETA, anomaly, source-of-truth pipeline.
- Later increments: MLOps, crowd sensing, model fortification, cleanup.

Each increment aimed to create a working version, not only documentation.

## 8. Software Evolution Plan

Software evolution means how the system will change after the current version.

### 8.1 Short-Term Evolution

Immediate next steps:

1. Merge anomaly CR2 if tests remain green.
2. Update `chore/docs-cleanup` from latest `main`.
3. Fix root and service READMEs to match actual code.
4. Standardize service folder structures.
5. Standardize all runtime config through `config.py`.
6. Align WebSocket docs/code with anomaly audience channels.
7. Remove tracked generated artifacts such as local test DB files.

### 8.2 Medium-Term Evolution

Next technical improvements:

- Add API Gateway endpoints for ETA/crowd where needed by G3.
- Add anomaly alert history APIs for admin.
- Improve Kubernetes readiness and metrics.
- Add load tests for many buses and WebSocket clients.
- Add dashboard-level monitoring for Kafka lag, Redis health, Flink jobs, and
  model latency.
- Add DB migrations instead of ad-hoc schema creation.
- Add versioned schemas for Kafka payload compatibility.

### 8.3 ML Evolution

Model improvements:

- Retrain ETA models from InfluxDB history.
- Improve XGBoost features using route segment, time of day, day of week,
  traffic/crowd signals.
- Tune SARIMA per route/stop.
- Use MLflow stages for model promotion.
- Retrain Isolation Forest with larger normal-driving windows.
- Use DBSCAN/stationary cluster artifacts from real historical zero-speed data.
- Improve crowd model with more organic passenger reports.

### 8.4 Evolution Safety Rules

To safely evolve the system:

- Keep old env var aliases when renaming config fields.
- Do not change Kafka payloads without updating schemas and consumers.
- Add new fields in a backward-compatible way when possible.
- Keep physics fallback if ML fails.
- Keep DLQ for rejected data.
- Run CI before merging.
- Update docs with code changes.

Good viva answer:

> Our evolution plan is to keep the architecture stable while improving models,
> observability, documentation, and deployment. We protect compatibility through
> shared schemas, config aliases, CI tests, and fallbacks.

## 9. Common Viva Questions and Suggested Answers

### Q1: What software process did you follow?

We followed a hybrid process. Architecture, increments, contracts, and service
ownership were planned up front. Inside each subgroup we used agile/Kanban
execution with user stories, tasks, feature branches, PRs, CI, and incremental
delivery.

### Q2: Did you do requirements elicitation?

We did not do formal real-world stakeholder interviews. We elicited
requirements from the SRS/business plan, project problem, lecturer feedback,
cross-group meetings, assumptions about passengers/drivers/admins, and the
integration needs of G1, G3, and G4.

### Q3: Give examples of FRs and NFRs.

FRs include GPS ingestion, live bus tracking, route/stop APIs, trip start/end,
ETA prediction, anomaly detection, and crowd occupancy prediction. NFRs include
performance, scalability, reliability, maintainability, security boundaries,
observability, and testability.

### Q4: What is verification in your project?

Verification was checking that the implementation matched the design and
contracts. We used unit tests, config tests, service tests, CI workflows, PR
reviews, and Docker build checks.

### Q5: What is validation in your project?

Validation was checking that the system solved the intended user problem. We
used integration tests, E2E live pipeline smoke tests, BDD tests for crowd
sensing, demo flows, and cross-group contract checking.

### Q6: Why microservices?

Because the project had multiple domains and multiple team members. Route,
Fleet, Ingestion, Stream, ETA, Anomaly, WebSocket, and Crowd Sensing each have
different responsibilities. Microservices gave ownership, independent testing,
and cleaner scaling.

### Q7: Why Kafka and Redis?

Kafka is used for durable event streams and decoupling services. Redis is used
for low-latency live state and Pub/Sub fan-out to WebSocket clients.

### Q8: Why Flink?

Flink handles real-time stream processing with event-time logic, deduplication,
physics validation, route enrichment, and high-throughput output to Redis,
Kafka, and InfluxDB.

### Q9: How did you estimate work?

We used experience-based and relative estimation. We classified tasks by
complexity and uncertainty, then tracked completion through Kanban and merged
PRs. We did not use formal COCOMO or function points.

### Q10: How did you measure velocity?

We measured practical velocity using completed tasks/stories, merged PRs, and
CI-passing service increments. A task was not considered done until tests and
review passed.

### Q11: What did you do for project management?

We used increment planning, service ownership, Kanban board tracking, GitHub
branches/PRs, CI gates, risk mitigation, and release-focused planning.

### Q12: What would you improve?

I would align all docs with the latest code, standardize every service folder,
finish API coverage for ETA/crowd/anomaly history, add stronger load testing,
improve monitoring dashboards, and mature DB migrations and model retraining.

## 10. Best Final Viva Summary

Use this as a closing answer:

> Our G2 project is an event-driven microservice backend for live public
> transport intelligence. We planned the overall architecture and increments
> first because many groups depended on stable contracts. Then we implemented
> services iteratively using agile/Kanban practices, GitHub branches, PRs, CI,
> and tests. Requirements came from the SRS, lecturer feedback, cross-group
> integration needs, and assumed passenger/driver/admin needs. We verified the
> system through unit tests, service tests, CI, and code reviews, and validated
> it through integration and E2E smoke tests proving the GPS-to-WebSocket flow.
> The system can evolve because services are decoupled by Kafka, Redis, REST,
> shared schemas, environment config, and model fallbacks.

