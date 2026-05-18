# Crowd Sensing Microservice

The `crowd-sensing` service is a core component of the OnTime G2 architecture. It provides highly accurate, stop-by-stop bus occupancy predictions by implementing a **Hybrid Prediction Engine** that blends historical Machine Learning forecasts with live crowdsourced passenger feedback.

---

## 1. How Reporting is Done (Data Ingestion)

When a passenger indicates how crowded a bus is using the frontend application, the system processes it securely and asynchronously:

1. **Authentication Handshake**: The user logs in via Keycloak. The API Gateway intercepts their JWT, validates the cryptographic signature, and forwards the immutable `sub` claim as the verified `passenger_id` in a secure header.
2. **API Endpoint (`POST /api/v1/crowd/report`)**: The report is received containing the `route_id`, `stop_id`, and `occupancy_score` (0-100).
3. **Geographical Integrity Check**: The endpoint performs a real-time network loopback call to the internal `route-service`. If the `route_id` doesn't exist or the `stop_id` is not associated with that route, the request is immediately blocked (400/404) to prevent database corruption.
4. **Asynchronous Kafka Queue**: To prevent API bottlenecks during rush-hour traffic spikes, the valid report is instantly published to the `crowd-reports` Kafka topic, and the API returns a `202 Accepted` to the user immediately.
5. **Background Consumer**: A dedicated worker thread (`crowd_report_consumer.py`) pulls messages from Kafka, runs the **Passenger Trust Engine** calibration, and persists the record safely into PostgreSQL (`crowd_sensing_db`).

---

## 2. Passenger Trust Engine (Anti-Spam Safeguards)

To protect the platform from anomalous inputs and trolls, the system maintains dynamic reputation scores for every passenger.

- **Passenger Profiles**: Housed in the `passenger_profiles` table, every unique Keycloak `passenger_id` starts with a baseline `trust_score` of `0.8`.
- **Consensus Evaluation (`trust_engine.py`)**: When a new report is processed, the engine fetches all other reports submitted at that exact stop within the last 20 minutes.
  - **Reward**: If the passenger's score matches the running consensus ($\le 30$ points difference), their trust score increases by `+0.02` (capped at `1.0`).
  - **Penalty**: If the passenger submits an extreme outlier (e.g., claiming a bus is empty when 5 other passengers say it is full), their trust score drops by `-0.05`.

---

## 3. How Models are Trained & Tested (Machine Learning)

The core predictive power comes from an **XGBoost Classifier** (`train_crowd_model.py`) that learns long-term transit behavior.

1. **Feature Engineering**: The script pulls historical reports from PostgreSQL and engineers features that dictate human commuting behavior, independent of physical road geometry:
   - *Temporal*: `hour_of_day`, `day_of_week`, `is_weekend`
   - *Spatial*: `route_id`, `stop_id`, `stop_sequence`
2. **Synthetic Bootstrapping**: A new deployment lacks human data. We seed the database with 500 synthetic bootstrap training records simulating realistic rush-hour peaks. The training script automatically detects if $\ge 100$ organic human reports exist; if so, it purges the synthetic data from training, transitioning exclusively to real human behavior.
3. **Training & MLflow Logging**: The `XGBClassifier` is trained and evaluated using standard metrics (Accuracy, F1-Score). These metrics, alongside model artifacts, are logged directly to the central **MLflow Model Registry** under `CrowdOccupancyModel`.

---

## 4. How Prediction is Done (Hybrid Blending)

When a user requests a prediction (`GET /api/v1/crowd/predict`), the service does not rely on a single source of truth. It uses a **Hybrid Predictor** (`hybrid_predictor.py`) to fuse historical knowledge with real-world volatility.

1. **Historical Forecast**: The service loads the latest `CrowdOccupancyModel` version from MLflow and asks the XGBoost model: *"Historically, what is the expected crowd at this route/stop/time?"*
2. **Live Condition Fetch**: The service queries PostgreSQL for any live passenger reports submitted for that exact stop within the last **20 minutes**.
3. **Trust-Weighted Aggregation**: If $\ge 5$ live reports exist, a simple average is not used. Instead, the scores are multiplied by the reporters' `trust_scores`. This ensures anomalous reports from low-trust passengers are mathematically minimized, while verified regulars heavily influence the result:
   $$\text{Weighted Live Average} = \frac{\sum (\text{Occupancy Score}_i \cdot \text{Trust Score}_i)}{\sum \text{Trust Score}_i}$$
4. **The Blend**: The service dynamically blends the **Trust-Weighted Live Average (70%)** with the **Historical AI Forecast (30%)**.
5. **Dynamic Confidence**: The final API response flags `"live_adjustment": true` and dynamically scales the statistical `confidence` metric based on the average reputation of the contributing passengers.

---

## 5. Codebase Walkthrough & Algorithms

Here is a line-by-line breakdown of the core algorithmic blocks that power the service.

### A. The Trust Calibration Engine (`app/utils/trust_engine.py`)
This script evaluates incoming reports against a 20-minute consensus.

```python
# 1. Fetch other reports at this exact stop from the last 20 mins, excluding the current passenger
stmt = select(CrowdReport.occupancy_score).where(
    CrowdReport.route_id == route_id,
    CrowdReport.stop_id == stop_id,
    CrowdReport.passenger_id != passenger_id,
    CrowdReport.timestamp >= window_start
)
other_scores = list(db.execute(stmt).scalars().all())

# 2. Require at least 2 other reports to form a statistical "consensus"
if len(other_scores) >= 2:
    consensus_avg = sum(other_scores) / len(other_scores)
    diff = abs(new_report_score - consensus_avg)
    
    # 3. Consensus Reward: If the passenger is within 30 points of the average, increase their trust (+0.02)
    if diff <= 30.0:
        profile.trust_score = min(1.0, profile.trust_score + 0.02)
        profile.verified_reports += 1
        
    # 4. Outlier Penalty: If the passenger is wildly inaccurate (anomalous), decrease their trust (-0.05)
    else:
        profile.trust_score = max(0.0, profile.trust_score - 0.05)
```

### B. The Trust-Weighted Hybrid Predictor (`app/prediction/hybrid_predictor.py`)
This script mathematically fuses AI historical models with live, trust-weighted human reality.

```python
# 1. Ask the XGBoost ML Model for the historical baseline forecast
hist_score = self._predict_historical(route_id, direction_id, stop_id, dt)

# 2. Fetch all live passenger reports and their respective authors' trust scores
live_reports = self._get_live_reports(route_id, stop_id, dt)
report_count = len(live_reports)

if report_count >= 5:
    # 3. Calculate Trust-Weighted Average
    # Multiplies each passenger's reported score by their personal trust level
    weighted_sum = sum(score * trust for score, trust in live_reports)
    total_trust = sum(trust for _, trust in live_reports)
    avg_live_score = weighted_sum / total_trust
    
    # 4. Final Blend: 70% Real-time Average + 30% Historical Baseline
    final_score = (0.7 * avg_live_score) + (0.3 * hist_score)
    
    # 5. Dynamic Confidence: Scale confidence metric by the average reputation of reporters
    avg_trust = total_trust / report_count
    confidence = min(0.95, 0.70 + (report_count * 0.05 * avg_trust))
```

### C. Route Geographical Integrity Validation (`app/utils/validation.py`)
This script prevents data corruption by verifying coordinates against the central `route-service`.

```python
def validate_route_stop(route_id: int, stop_id: int):
    # 1. Fire an internal network loopback query to the central Route Service
    url = f"{settings.route_service_url}/api/v1/routes/{route_id}/stops"
    req = urllib.request.Request(url, method="GET")
    
    with urllib.request.urlopen(req, timeout=5.0) as response:
        # 2. Parse the Route Service response
        data = json.loads(response.read().decode())
        valid_stop_ids = [s["id"] for s in data.get("stops", [])]
        
        # 3. Block anomalous requests instantly with a 400 Bad Request
        if stop_id not in valid_stop_ids:
            raise HTTPException(
                status_code=400, 
                detail=f"Stop ID {stop_id} is not associated with Route ID {route_id}."
            )
```
