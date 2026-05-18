FROM python:3.11-slim

WORKDIR /opt/anomaly-service

ENV PYTHONUNBUFFERED=1

COPY services/anomaly-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY ml /opt/ontime/ml
# Includes app/models/training/isolation_forest.joblib (canonical behavioral artifact).
COPY services/anomaly-service/app ./app

ENV PYTHONPATH=/opt/anomaly-service:/opt/ontime

EXPOSE 8006

HEALTHCHECK --interval=30s --timeout=5s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8006/health/live', timeout=3)"

CMD ["python", "-m", "app.main"]
