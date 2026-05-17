FROM python:3.10-slim

WORKDIR /opt/anomaly-service

COPY services/anomaly-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY ml /opt/ontime/ml
COPY services/anomaly-service/app ./app

ENV PYTHONPATH=/opt/anomaly-service:/opt/ontime

CMD ["python", "-m", "app.main"]
