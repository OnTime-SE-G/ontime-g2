FROM python:3.10-slim

WORKDIR /opt/anomaly-service

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create directory for the IsolationForest artifact (mounted or built-in at deploy time)
RUN mkdir -p /opt/anomaly-service/app/models/training
ENV ANOMALY_ISOLATION_FOREST_ARTIFACT_PATH=/opt/anomaly-service/app/models/training/isolation_forest.joblib

COPY app ./app

CMD ["python", "-m", "app.main"]
