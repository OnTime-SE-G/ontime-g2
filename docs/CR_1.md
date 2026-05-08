# Architecture Change Request (CR 1): The Event-Driven Source of Truth

**Date:** 2026-05-06
**Status:** On Hold
**Scope:** Re-architecting the telemetry pipeline to define strict boundaries between structural validation, physical integrity, and behavioral ML analysis.

## 1. The Core Philosophy

This architecture shifts away from a "smart ingestion" model to a highly scalable, distributed **"Source of Truth"** pipeline powered by Apache Flink. We divide our data processing into three distinct layers:
1. **The Dumb Pipe:** Ingestion Service (Stateless)
2. **The Physics & Reality Engine:** Stream Processing / Flink (Stateful)
3. **The Behavioral Layer:** ETA & Anomaly Services (ML / Rules)

---

## 2. Telemetry Pipeline Architecture

```mermaid
graph TD
    classDef g1 fill:#f9d0c4,stroke:#333,stroke-width:2px;
    classDef mqtt fill:#f8cecc,stroke:#b85450,stroke-width:2px;
    classDef ingest fill:#dae8fc,stroke:#6c8ebf,stroke-width:2px;
    classDef kafka fill:#d5e8d4,stroke:#82b366,stroke-width:2px;
    classDef flink fill:#ffe6cc,stroke:#d79b00,stroke-width:2px;
    classDef redis fill:#e1d5e7,stroke:#9673a6,stroke-width:2px;
    classDef service fill:#fff2cc,stroke:#d6b656,stroke-width:2px;
    classDef ws fill:#e1d5e7,stroke:#9673a6,stroke-width:2px;
    classDef db fill:#b1ddf0,stroke:#10739e,stroke-width:2px;

    G1["G1 IoT Device"]:::g1 -->|MQTT Stream| Broker["G4 MQTT Broker<br>(Rate Limits)"]:::mqtt
    
    Broker -->|Subscribe| Ingest["Ingestion Service<br>(Dumb Pipe)"]:::ingest
    Ingest -->|Invalid Schema| DLQ[("Kafka Topic<br>telemetry-dlq")]:::kafka
    Ingest -->|Valid JSON| Raw[("Kafka Topic<br>transport-telemetry-raw")]:::kafka
    
    FleetService["Fleet Management Service"]:::service -->|Trip Events| Lifecycle[("Kafka Topic<br>trip.lifecycle")]:::kafka
    RouteService["Route Service"]:::service -.->|Startup Cache| Flink
    FleetService -.->|Startup Cache| Flink
    
    Raw --> Flink["Apache Flink<br>(The Source of Truth)"]:::flink
    Lifecycle --> Flink
    
    Flink -->|Physics Violated| Invalid[("Kafka Topic<br>telemetry-invalid")]:::kafka
    Flink -->|History Sink| InfluxDB[("InfluxDB<br>(ML Training)")]:::db
    Flink -->|Live Map| RedisLive[("Redis PubSub<br>(fleet:live)")]:::redis
    Flink -->|Enriched JSON| Cleaned[("Kafka Topic<br>transport-telemetry-cleaned")]:::kafka
    
    Cleaned --> ETA["ETA Service<br>(SARIMA Inference)"]:::service
    Cleaned --> Anomaly["Anomaly Service<br>(Rolling Window + Isolation Forest)"]:::service
    
    InfluxDB -.->|Offline Models| ETA
    InfluxDB -.->|Offline Models| Anomaly
    
    DLQ --> Elastic[("Elasticsearch<br>(Log Aggregation)")]:::db
    Invalid --> Elastic
    
    ETA -->|Predictions| RedisETA[("Redis PubSub<br>(eta:live)")]:::redis
    ETA -->|Persistent| ETADb[("PostgreSQL<br>(eta_db)")]:::db
    
    Anomaly -->|Live Alerts| RedisAnomaly[("Redis PubSub<br>(anomaly:live)")]:::redis
    Anomaly -->|Persistent| AnomalyDb[("PostgreSQL<br>(anomaly_db)")]:::db
    
    %% Kong API Gateway Bypass
    RedisLive -->|Subscribes| Kong["G4 Kong API Gateway"]:::ws
    RedisETA -->|Subscribes| Kong
    RedisAnomaly -->|Subscribes| Kong
    
    Kong -->|WebSockets| Dashboard["G3 Frontend"]:::g1
```

---

## 3. The "Classify, Don't Drop" Rule

A fundamental shift in this architecture is how we handle "bad" behavior. 

**Rule:** If a GPS ping disobeys the laws of physics (e.g. going 200km/h or teleporting), Flink drops it into `telemetry-invalid` for observability. **However**, if a ping obeys physics but behaves badly (e.g., bus is off route, or moving while the trip is marked INACTIVE), Flink **classifies it** and passes it on.

### The Flow:
1. **Flink's Job:** Map matches the GPS. Finds the bus is off-route. It appends `on_route = false` to the JSON payload and pushes it to `transport-telemetry-cleaned`.
2. **ETA Service's Job:** Sees `on_route = false` and safely ignores the event (it cannot calculate an ETA).
3. **Anomaly Service's Job:** Sees `on_route = false` and immediately fires a "Route Deviation Anomaly" alert to the WebSockets.

This prevents silent data loss and ensures our ML and anomaly models have full visibility into unauthorized bus movements.

### 3.1 Anomaly Service: Feature Extraction for Unsupervised ML

The Anomaly Service uses an **Isolation Forest** to detect erratic driving patterns. Because an Isolation Forest does not natively understand "time" (it expects a single feature vector like `[X, Y, Z]`), we cannot simply feed it raw coordinates and timestamps from a sliding window of GPS pings.

**The Feature Extraction Workflow:**
1. **Sliding Window:** The service maintains a sliding window of the last 10-20 GPS pings.
2. **Summary Vector:** When a new ping arrives, it calculates a summary vector representing the behavior within that window. Example metrics include:
   - `max_acceleration`: Did they floor the gas pedal?
   - `min_acceleration`: Did they slam on the brakes?
   - `speed_variance`: Is their speed fluctuating wildly?
   - `heading_variance`: Are they swerving?
3. **Inference:** Instead of feeding raw pings, the service feeds this single summary vector (e.g., `[4.2, -5.1, 12.5, 45.0]`) into the Isolation Forest.
4. **Detection:** The model, which was trained offline on millions of normal 10-second summary vectors, evaluates if the current vector looks "normal". If the driver is slamming the brakes and swerving, the vector lands far outside the normal cluster, the model outputs `-1`, and an `ERRATIC_DRIVING` alert is instantly fired.

---

## 4. Why Apache Flink & How it gets Data

To avoid overloading the Postgres databases with thousands of queries per second, we are relying heavily on Flink. 

**Microservice Independence (No direct DB coupling):**
You correctly pointed out that Flink should NOT directly read the Fleet/Route Postgres databases. That breaks microservice rules! Instead:
1. **Startup Cache via REST:** When Flink boots up, it makes a one-time `GET` request to the Route Service and Fleet Service REST APIs to download the route geometries and active trips. It stores these in its highly-optimized internal **RocksDB memory**.
2. **Event-Driven Updates via Kafka (`trip.lifecycle`):** When a driver starts or ends a trip, the Fleet Service publishes an event to the `trip.lifecycle` Kafka topic. Flink consumes this topic in real-time to update its internal RocksDB cache without ever hitting the REST API again.

This ensures Flink calculates geo-math in microseconds while strictly respecting microservice boundaries.

---

## 5. Storage and Observability Matrix

| Component | Technology | Purpose in System |
| :--- | :--- | :--- |
| **Relational Ground Truth** | `PostgreSQL` | Defines active buses, trips, ETA configurations, and user metadata. |
| **Spatial Ground Truth** | `PostGIS` | Holds route polylines and stop coordinates. |
| **Live State / WebSockets** | `Redis` | Powers zero-latency map updates (`fleet:live`). If G2 API Gateway is bypassed, **Kong directly subscribes to Redis** via Lua plugins to push WS frames to clients. |
| **Offline ML Training** | `InfluxDB` | Sinks all valid telemetry for data scientists to train SARIMA and Isolation Forest models. |
| **Observability / Logs** | `Elasticsearch` / `Postgres JSONB` | Sinks the DLQ and Invalid topics so engineers can debug G1 firmware errors. |

---

## 6. Microservice Independence

This architecture adds **no new microservices** beyond the previously defined Increment plan. Instead, it rebalances the workload:
- `Ingestion` becomes purely stateless (easy to scale).
- `Flink` becomes the heavy-lifting state engine.
- `ETA` and `Anomaly` become isolated, specialized analytic consumers. 

*(End of CR 1 Document)*
