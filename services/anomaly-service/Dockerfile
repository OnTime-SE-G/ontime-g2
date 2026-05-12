FROM python:3.10-slim

WORKDIR /opt/anomaly-service

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create directory for the IsolationForest artifact (mounted or built-in at deploy time)
RUN mkdir -p /opt/anomaly-service/if_artifacts
ENV ANOMALY_IF_ARTIFACT_PATH=/opt/anomaly-service/if_artifacts/isolation_forest.joblib

COPY app ./app

CMD ["python", "-m", "app.main"]
