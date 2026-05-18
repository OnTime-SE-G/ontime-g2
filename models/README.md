# Models

Production model artifacts are registered in **MLflow** (`ontime-eta-xgb`, `ontime-anomaly-if-*`, etc.).

## Local development fallbacks

- `services/eta-service/models/training/eta_model_xgb.joblib`
- `services/anomaly-service/app/models/training/isolation_forest*.joblib`

Shared training contracts and loaders live in [`ml/`](../ml/).

Do not commit very large binary artifacts directly unless agreed by the team.

## Ownership and Review

- Owner: Chamodh
- Required reviewer: Nidharshan
- Optional reviewer: Nathasha

