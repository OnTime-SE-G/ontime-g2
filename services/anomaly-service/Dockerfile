FROM python:3.10-slim

WORKDIR /opt/anomaly-service

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

CMD ["python", "-m", "app.main"]
