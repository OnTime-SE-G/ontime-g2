# Entity-Relationship Diagram (ERD)

This diagram illustrates the logical database schema across the isolated G2 microservice databases. 
Note: While these tables physically reside in separate logical databases (`route_db`, `fleet_db`, `eta_db`, `anomaly_db`) to enforce microservice boundaries, they relate to each other logically via foreign keys like `route_id` and `vehicle_id`.

```mermaid
erDiagram
    %% Route Service Database (route_db)
    ROUTES {
        varchar route_id PK
        varchar route_number
        varchar name_en
        geometry route_polyline
        boolean is_active
    }
    
    HALTS {
        varchar halt_id PK
        varchar route_id FK
        varchar halt_name_en
        geometry location
        int halt_sequence
    }

    %% Fleet Management Service Database (fleet_db)
    VEHICLES {
        varchar vehicle_id PK
        varchar route_id FK "Assigned Route"
        varchar registration_plate
        varchar operator_name
        varchar status
    }
    
    TRIPS {
        uuid trip_id PK
        varchar vehicle_id FK
        varchar route_id FK
        varchar status "e.g., EN_ROUTE"
        timestamp start_time
        timestamp end_time
    }

    %% ETA Service Database (eta_db)
    ETA_RECORDS {
        uuid id PK
        uuid trip_id FK
        varchar vehicle_id FK
        varchar route_id FK
        varchar halt_id FK
        int eta_seconds
        float confidence_score
        timestamp created_at
    }

    %% Anomaly Service Database (anomaly_db)
    ANOMALY_RECORDS {
        uuid id PK
        varchar vehicle_id FK
        uuid trip_id FK
        varchar anomaly_type "e.g., OFF_ROUTE"
        varchar severity
        jsonb feature_vector
        timestamp created_at
    }

    %% Relationships
    ROUTES ||--o{ HALTS : "contains"
    ROUTES ||--o{ VEHICLES : "assigned to"
    ROUTES ||--o{ TRIPS : "followed by"
    VEHICLES ||--o{ TRIPS : "performs"
    TRIPS ||--o{ ETA_RECORDS : "generates"
    TRIPS ||--o{ ANOMALY_RECORDS : "triggers"
    HALTS ||--o{ ETA_RECORDS : "predicted for"
```
