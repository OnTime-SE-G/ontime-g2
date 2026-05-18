
This guide explains how to run the edge device simulation using Node-RED and HiveMQ Cloud to feed data into the OnTime G2 ingestion service.

## 1. Prerequisites
- **Docker & Docker Compose** installed and running.
- **HiveMQ Cloud Cluster** credentials (Username: `chamodh`, Password: `Noobmaster69`).

## 2. Configuration
The simulation uses environment variables from the `docker/.env` file. Ensure it contains the following settings:

```env
# HiveMQ Cloud Cluster Settings
MQTT_BROKER_HOST=94f82b369e4a40e3a5f0725c0850c6f4.s1.eu.hivemq.cloud
MQTT_BROKER_PORT=8883
MQTT_USERNAME=chamodh
MQTT_PASSWORD=Noobmaster69
MQTT_TLS_ENABLED=true

# Node-RED Dashboard Port
NODERED_PORT=1880

# Ingestion Logic (Strict mode: only allow data for buses with active trips)
INGESTION_REQUIRE_ACTIVE_TRIP=false
```

> [!TIP]
> Setting `INGESTION_REQUIRE_ACTIVE_TRIP=false` is recommended for initial testing to see data flow without needing to manually start trips in the Fleet Management service.

## 3. Starting the Simulation
Run the following command in the `docker/` directory to start the ingestion service and the Node-RED simulator:

```powershell
docker compose up -d ingestion-service nodered
```

## 4. How the Simulation Works
1.  **Node-RED** starts and automatically loads the KML file from `data/202_gampaha_kirindiwela.kml`.
2.  It parses the path coordinates and begins cycling through them every **5 seconds**.
3.  Telemetry data is published to the HiveMQ Cloud topic: `transport/bus/BUS001/location`.
4.  Heartbeats are sent every **30 seconds** to: `transport/bus/BUS001/heartbeat`.
5.  The **Ingestion Service** subscribes to these topics and processes the data into Kafka.

## 5. Monitoring
- **Node-RED UI**: Access the flow editor at [http://localhost:1880](http://localhost:1880). You can see the live points being sent in the Debug sidebar.
- **Ingestion Stats**: Run the following command to see a live count of received and validated messages:
  ```powershell
  docker exec ontime_ingestion python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8001/health').read().decode())"
  ```
- **Ingestion Logs**: Follow the logs to see any errors or processing info:
  ```powershell
  docker logs -f ontime_ingestion
  ```

## 6. Troubleshooting
- **Connection Failed in Node-RED**: Check the logs (`docker logs ontime_nodered`). If you see DNS errors, ensure your system can resolve the HiveMQ hostname.
- **Messages Rejected**: If `messages_rejected` increases in the health check, ensure `INGESTION_REQUIRE_ACTIVE_TRIP` is set to `false` or that a trip is active for `BUS001`.
