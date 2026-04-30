FROM python:3.11-slim

WORKDIR /workspace

ENV PYTHONUNBUFFERED=1

COPY services/ingestion/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY schemas /workspace/schemas
COPY services/ingestion /workspace/services/ingestion

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health/live', timeout=3)"

CMD ["python", "-m", "services.ingestion.app.main"]
