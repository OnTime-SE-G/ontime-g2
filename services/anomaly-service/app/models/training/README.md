# Anomaly Training Scaffold

This folder contains the offline training pieces for the CR1 anomaly service
follow-up.

Current pieces:

- `feature_extraction.py` converts a sliding window of telemetry dictionaries
  into a summary vector for unsupervised learning.
- `train_isolation_forest.py` trains an `IsolationForest` model from a CSV of
  summary vectors and writes a `joblib` artifact.

Expected artifact at runtime:

- `isolation_forest.joblib`

Expected CSV schema:

- `max_acceleration`
- `min_acceleration`
- `speed_variance`
- `heading_variance`
- `average_speed`
- `sample_count`
