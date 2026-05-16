# CR2: Model Fortification Plan

This document outlines the end-to-end plan for fortifying the machine learning and deterministic models within the OnTime G2 backend, focusing heavily on the ETA and Anomaly services.

---

## 1. Current State vs. Delivered Architecture

### **A. ETA Service**
| Feature | Current State | Delivered Architecture (CR2) | Why it's Best |
| :--- | :--- | :--- | :--- |
| **Data Smoothing** | Processes single, instantaneous speed/distance readings. Highly vulnerable to GPS jitter. | **Configurable Moving Average Buffer:** Maintains a rolling window of events per bus (default 10) with a **Time-To-Live (TTL)** check to discard stale data. | Smooths out sudden GPS spikes. The TTL prevents wildly inaccurate ETAs caused by averaging ancient speeds if a bus loses connection (e.g., in a tunnel). |
| **Model Hierarchy** | `SARIMA -> XGBoost -> Physics` | `XGBoost -> SARIMA -> Physics` | SARIMA ignores real-time speed. XGBoost uses real-time features. Putting XGBoost first ensures the ETA responds instantly to traffic, falling back to SARIMA only when real-time features are unavailable or corrupt. |

### **B. Anomaly Service**
| Feature | Current State | Delivered Architecture (CR2) | Why it's Best |
| :--- | :--- | :--- | :--- |
| **Behavioral Anomalies** | `IsolationForest` detecting erratic driving natively. | No change to the underlying forest, but fed by a more stable window. | Proven and works well for finding mathematical outliers in acceleration/speed variance. |
| **Stationary Rule** | Blindly fires if speed < 2.0 km/h for 5 mins. Generates massive false positives for known traffic lights or major bus stops. | **Spatial Clustering (DBSCAN):** Evaluates stationary points against offline-generated dense spatial clusters. Includes a **safe fallback** if clusters are missing. | No need for manual mapping APIs. The system learns organic traffic chokepoints from its own telemetry. If stopped outside a cluster, it's a real anomaly. |
| **Alert Visibility** | All anomalies fire into the `transport-anomalies` topic with no audience context, risking passenger panic on minor operational issues. | **Secure Audience Targeting:** Classifies anomalies and physically routes them to isolated topics (`anomaly:admin`, `anomaly:passenger`). | Prevents false alarms and guarantees security. Sensitive internal alerts are physically impossible for a passenger client to intercept. |

---

## 2. Technical Refinements (PR Review Feedback)

Based on team reviews, the following 6 production-grade safeguards are integrated into the execution plan:

1. **State Cleanup (Memory Leak Prevention):** The ETA service will actively listen for `TRIP_ENDED` events and explicitly clear the sliding window deque for that trip from memory.
2. **Robustness of Clustering (Safe Fallbacks):** The Anomaly Service will catch `FileNotFoundError` if the `stationary_clusters.json` artifact is missing (e.g., in a fresh deployment) and safely fall back to the default 5-minute rule rather than crashing.
3. **Configurable Window Size:** The window size is abstracted to an environment variable (`ETA_SMOOTHING_WINDOW_SIZE=10`), allowing DevOps to tune smoothing sensitivity without code changes.
4. **Time-Staleness TTL:** Before averaging speeds, the ETA service will purge any events in the buffer older than 60 seconds. This ensures old data from disconnected periods does not ruin the ETA.
5. **Strict Topic Isolation (Security):** The backend will explicitly route alerts to separate Redis/Kafka topics (e.g., `anomaly:passenger`, `anomaly:driver`) instead of relying on frontend hiding logic.
6. **External Contract Coordination:** The frontend G3 team is verified to handle the new fields (or safely ignore them) to prevent UI parsing crashes.

---

## 3. Managing Existing PRs

We have two pending PRs that affect this pipeline:
- **PR #120:** `feat(eta+anomaly): SARIMA ETA forecasting + IsolationForest anomaly detection + websocket eta fix`
- **PR #122:** `Add eta-service to workflow deploy step`

### Workflow Strategy
1. **Merge or Close Strategy:** 
   - We will **NOT** modify PR #120 directly. Since PR #120 has failing CI checks (in the Anomaly Service tests), the cleanest approach is to branch off `main` and fold the *fixes* for PR #120 into this new CR2 branch (`feature/cr2-model-fortification`). 
2. **PR #122 Integration:** 
   - This deployment PR is isolated to GitHub actions/Kubernetes manifests. It should be merged independently by the DevOps owner.

---

## 4. Implementation Steps for CR2

### Phase 1: ETA Service Fortification
1. **Configurable Sliding Window & TTL:** Update `services/eta-service/consumer.py` to maintain a `deque(maxlen=ETA_SMOOTHING_WINDOW_SIZE)`. Filter stale entries, then calculate the moving average.
2. **Memory Cleanup:** Add logic to clear the deque when a `TRIP_ENDED` lifecycle event arrives.
3. **Cascading Fallback:** Update `_predict_eta()` to prioritize `models.ml_eta_xgb` over `models.sarima_eta`.

### Phase 2: Anomaly Service Spatial Clustering (DBSCAN)
1. **Offline Training Script:** Create an offline script (`train_dbscan.py`) that queries InfluxDB for zero-speed telemetry, runs `sklearn.cluster.DBSCAN`, and saves the centroids to an artifact.
2. **Real-Time Inference Integration:** Update `anomaly_model.py` with Safe Fallbacks. When evaluating the `STATIONARY` rule:
   - Check distance to nearest DBSCAN cluster centroid.
   - If distance < 50 meters: Extend the stationary threshold to 15 minutes.
   - If distance > 50 meters: Keep the 5-minute threshold and fire the `DRIVER_STATUS_PROMPT` alert.

### Phase 3: Anomaly Audience Targeting & Topic Isolation
1. Update `_create_alert()` in `anomaly_model.py` to append an `audience` field.
   - `ERRATIC_DRIVING` -> `ADMIN`
   - `PERSISTENT_OFF_ROUTE` -> `ADMIN`, `DRIVER`
   - `STATIONARY` -> `DRIVER` (as `DRIVER_STATUS_PROMPT`)
2. Update the `AnomalyService` publisher to route messages to distinct isolated topics/channels based on the audience tag.
