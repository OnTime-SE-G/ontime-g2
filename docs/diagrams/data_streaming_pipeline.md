# Data Streaming Pipeline Diagram

This diagram isolates the high-speed, real-time data flow of the telemetry pipeline. It deliberately omits standard CRUD REST APIs to focus purely on how thousands of GPS pings per second are processed through Kafka, Flink, and delivered out to WebSockets.

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
    
    Broker -->|Subscribe| Ingest["Ingestion Service<br>(MQTT to Kafka Bridge)"]:::ingest
    Ingest -->|Invalid Schema| DLQ[("Kafka Topic<br>telemetry-dlq")]:::kafka
    Ingest -->|Valid JSON| Raw[("Kafka Topic<br>transport-telemetry-raw")]:::kafka
    
    FleetService["Fleet Management Service"]:::service -->|Trip Events| Lifecycle[("Kafka Topic<br>trip.lifecycle")]:::kafka
    RouteService["Route Service"]:::service -.->|Startup Cache| Flink
    FleetService -.->|Startup Cache| Flink
    
    Raw --> Flink["Apache Flink<br>(Stream Processing)"]:::flink
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
    
    Kong -->|WebSockets/REST APIs| Dashboard["G3 Frontend"]:::g1
```
