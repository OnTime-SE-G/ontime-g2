# CR2: Model Fortification Plan

This document outlines the end-to-end plan for fortifying the machine learning and deterministic models within the OnTime G2 backend, focusing heavily on the ETA and Anomaly services.

---

## 1. Current State vs. Delivered Architecture

### **A. ETA Service**
| Feature | Current State | Delivered Architecture (CR2) | Why it's Best |
| :--- | :--- | :--- | :--- |
| **Data Smoothing** | Processes single, instantaneous speed/distance readings. Highly vulnerable to GPS jitter. | **10-Event Moving Average Buffer:** Maintains a rolling window of 10 events per bus. | Smooths out sudden GPS spikes or momentary stops, leading to an ETA that doesn't jump wildly up and down. |
| **Model Hierarchy** | `SARIMA -> XGBoost -> Physics` | `XGBoost -> SARIMA -> Physics` | SARIMA ignores real-time speed. XGBoost uses real-time features. Putting XGBoost first ensures the ETA responds instantly to traffic, falling back to SARIMA only when real-time features are unavailable or corrupt. |

### **B. Anomaly Service**
| Feature | Current State | Delivered Architecture (CR2) | Why it's Best |
| :--- | :--- | :--- | :--- |
| **Behavioral Anomalies** | `IsolationForest` detecting erratic driving natively. | No change to the underlying forest, but fed by a more stable 10-event window. | Proven and works well for finding mathematical outliers in acceleration/speed variance. |
| **Stationary Rule** | Blindly fires if speed < 2.0 km/h for 5 mins. Generates massive false positives for known traffic lights or major bus stops. | **Spatial Clustering (DBSCAN):** Evaluates stationary points against offline-generated dense spatial clusters. | No need for manual mapping APIs. The system learns organic traffic chokepoints from its own telemetry. If stopped outside a cluster, it's a real anomaly. |
| **Alert Visibility** | All anomalies fire into the `transport-anomalies` topic with no audience context, risking passenger panic on minor operational issues. | **Audience Targeting (`visibility` flag):** Classifies anomalies for `ADMIN`, `DRIVER`, or `PASSENGER`. | Prevents false alarms for passengers. Example: the `STATIONARY` anomaly prompts the driver to confirm a breakdown before the passenger ever sees an alert. |

---

## 2. Managing Existing PRs

We have two pending PRs that affect this pipeline:
- **PR #120:** `feat(eta+anomaly): SARIMA ETA forecasting + IsolationForest anomaly detection + websocket eta fix`
- **PR #122:** `Add eta-service to workflow deploy step`

### Workflow Strategy
1. **Merge or Close Strategy:** 
   - We will **NOT** modify PR #120 directly. Since PR #120 has failing CI checks (in the Anomaly Service tests), the cleanest approach is to branch off `main` and fold the *fixes* for PR #120 into this new CR2 branch (`feature/cr2-model-fortification`). 
   - Alternatively, we can fix the failing test in PR #120, merge it into `main`, and then rebase our CR2 branch. Given we are fundamentally changing the anomaly rules, we should merge PR 120 as a baseline (once tests pass) and build on top of it.
2. **PR #122 Integration:** 
   - This deployment PR is isolated to GitHub actions/Kubernetes manifests. It should be merged independently by the DevOps owner, as it does not conflict with our Python model code.

---

## 3. Implementation Steps for CR2

### Phase 1: ETA Service Fortification
1. **10-Event Sliding Window:** Update `services/eta-service/consumer.py` to maintain a `deque(maxlen=10)` per `trip_id`. Calculate the moving average of `speed_ms` and `distance_to_next_stop` before inference.
2. **Cascading Fallback:** Update `_predict_eta()` to prioritize `models.ml_eta_xgb` over `models.sarima_eta`.

### Phase 2: Anomaly Service Spatial Clustering (DBSCAN)
1. **Offline Training Script:** Create an offline script (`train_dbscan.py`) that queries InfluxDB for zero-speed telemetry, runs `sklearn.cluster.DBSCAN`, and saves the dense cluster centroids to an artifact (`stationary_clusters.json` or `.joblib`).
2. **Real-Time Inference Integration:** Update `anomaly_model.py`. When evaluating the `STATIONARY` rule:
   - Check distance to nearest DBSCAN cluster centroid.
   - If distance < 50 meters: Extend the stationary threshold to 15 minutes (assuming severe traffic).
   - If distance > 50 meters: Keep the 5-minute threshold and fire the `DRIVER_STATUS_PROMPT` alert.

### Phase 3: Anomaly Audience Targeting
1. Update `_create_alert()` in `anomaly_model.py` to append an `audience` field.
   - `ERRATIC_DRIVING` -> `ADMIN`
   - `PERSISTENT_OFF_ROUTE` -> `ADMIN`, `DRIVER`
   - `STATIONARY` -> `DRIVER` (as `DRIVER_STATUS_PROMPT`)
