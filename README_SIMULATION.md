# Simulation Guide — Node-RED as a Virtual G1 Device

This guide explains how to simulate a real G1 bus IoT device using **Node-RED running
on your laptop**. Your laptop acts as the physical bus, publishing GPS data to the
**Mosquitto MQTT broker** that is already running on your DigitalOcean server as a
Docker container — no third-party broker needed.

---

## Architecture (What Runs Where)

```
YOUR LAPTOP (Local)                |  DIGITAL OCEAN SERVER (Cloud)
-----------------------------------|-----------------------------------------------
  Node-RED (Docker)                |   Mosquitto MQTT Broker  :1883
  - reads KML route file           |   Ingestion Service      :8001
  - generates fake GPS packets     |   Flink (stream-processing)
  - publishes to MQTT every 5s     |   Kafka + Zookeeper
        │                          |   Redis
        │  MQTT plaintext :1883    |   Route Service          :8002
        └──────────────────────────►   Fleet Service          :8003
                                   |   WebSocket Service      :8004
                                   |   ETA Service            :8005
                                   |   PostgreSQL + PostGIS
```

**Your laptop only publishes MQTT. It never connects to Kafka, Redis, or any other
backend service directly.** Mosquitto is the only entry point from the outside world.

> ⚠️ Make sure port **1883** is open in your DigitalOcean firewall for inbound TCP
> connections from your laptop's IP.

---

## Understanding busId and routeId — Read This First!

### busId

The `busId` in every MQTT packet must be the **PostgreSQL auto-increment integer ID**
of the bus, serialized as a string.

```
Step 1: You create a bus via Fleet API
Step 2: PostgreSQL assigns it an integer primary key, e.g. id = 12
Step 3: Fleet publishes Kafka lifecycle events as:  bus_id = "12"
Step 4: Node-RED must publish MQTT packets with:    "busId": "12"
```

**Not** `fleet_code` (like `"BUS-E2E-001"`) — that is only a human label.

After calling `POST /api/v1/fleet/buses`, the response JSON contains `"id": 12`.
That integer, as a string, is your `SIM_BUS_ID`.

### routeId

Node-RED **never sends a routeId**. The route is linked to the bus on the server side:

```
1. You upload a KML → Route Service stores it → returns "id": 5
2. You assign bus 12 to route 5 via the API
3. When the trip starts, Fleet publishes: { bus_id:"12", route_id:"5" } to Kafka
4. Flink loads that route's geometry and starts map-matching bus 12 to it
5. Node-RED just walks the same KML coordinates — Flink handles everything else
```

| Thing you configure | Value |
| --- | --- |
| `SIM_BUS_ID` in `.env` | Integer `id` from Fleet API response (e.g., `12`) |
| KML in Node-RED | Same `.kml` file you uploaded to Route Service |
| `routeId` | Never sent by Node-RED — server handles it |

---

## Step-by-Step Setup

### Step 1 — Server-Side Setup (Run Once)

Run these PowerShell commands from your laptop. Replace `<host>` with your server IP.

```powershell
$ROUTE  = "http://<host>:8002"
$FLEET  = "http://<host>:8003"
$TODAY  = Get-Date -Format "yyyy-MM-dd"
$SUFFIX = (Get-Random)
```

**1a. Verify server health**
```powershell
Invoke-RestMethod "$ROUTE/health"
Invoke-RestMethod "$FLEET/health/ready"
```

**1b. Upload your route KML**
This must be the same KML that Node-RED will walk through.
```powershell
$routeRes = curl.exe -s -X POST "$ROUTE/api/v1/admin/routes/add-route" `
  -F "route_name=Sim Route $SUFFIX" `
  -F "file=@C:\Users\jpaba\Documents\GitHub\ontime-g2\data\202_gampaha_kirindiwela.kml;type=application/vnd.google-earth.kml+xml" `
  | ConvertFrom-Json

$ROUTE_ID = "$($routeRes.id)"
Write-Host "✅ Route ID: $ROUTE_ID"
```

**1c. Create the bus**
```powershell
$bus = Invoke-RestMethod -Method Post "$FLEET/api/v1/fleet/buses" `
  -ContentType "application/json" `
  -Body (@{ fleet_code="BUS-SIM-$SUFFIX"; plate_number="WP-SIM-$SUFFIX"; capacity=48 } | ConvertTo-Json)

$BUS_ID = "$($bus.id)"    # ← integer ID as string — this is your SIM_BUS_ID
Write-Host "✅ Bus ID (set as SIM_BUS_ID): $BUS_ID"
```

**1d. Create a driver**
```powershell
$driver = Invoke-RestMethod -Method Post "$FLEET/api/v1/fleet/drivers" `
  -ContentType "application/json" `
  -Body (@{ name="Sim Driver $SUFFIX"; license_number="LIC-$SUFFIX"; phone="0770000000" } | ConvertTo-Json)

$DRIVER_ID = $driver.id
Write-Host "✅ Driver ID: $DRIVER_ID"
```

**1e. Assign bus to route**
```powershell
Invoke-RestMethod -Method Patch "$FLEET/api/v1/fleet/buses/$BUS_ID/assign-route/$ROUTE_ID"
```

**1f. Create a schedule for today**
```powershell
# DayOfWeek: 0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat
$DAY = [int](Get-Date).DayOfWeek

$schedule = Invoke-RestMethod -Method Post "$FLEET/api/v1/fleet/schedules" `
  -ContentType "application/json" `
  -Body (@{ route_id=[int]$ROUTE_ID; scheduled_time="10:00:00"; day_of_week=$DAY } | ConvertTo-Json)

$SCHEDULE_ID = $schedule.id
Write-Host "✅ Schedule ID: $SCHEDULE_ID"
```

**1g. Generate today's planned trip**
```powershell
Invoke-RestMethod -Method Post "$FLEET/api/v1/fleet/planned-trips/generate?target_date=$TODAY"

$trips  = Invoke-RestMethod "$FLEET/api/v1/fleet/planned-trips/today?target_date=$TODAY"
$trip   = $trips | Where-Object { $_.schedule_id -eq $SCHEDULE_ID } | Select-Object -First 1
$TRIP_ID = $trip.id
Write-Host "✅ Trip ID: $TRIP_ID"
```

**1h. Assign bus + driver to the trip**
```powershell
Invoke-RestMethod -Method Patch "$FLEET/api/v1/fleet/planned-trips/$TRIP_ID/assign?bus_id=$BUS_ID&driver_id=$DRIVER_ID"
```

---

### Step 2 — Configure Node-RED on Your Laptop

Edit `docker/.env` in the repo (copy from `docker/.env.example` if missing):

```env
# ── MQTT Broker ─────────────────────────────────────────────────────────────
# Point to the Mosquitto container running on your DigitalOcean server.
# No username/password unless you configured mosquitto.conf to require it.
MQTT_BROKER_HOST=<your-digitalocean-ip>
MQTT_BROKER_PORT=1883
MQTT_TLS_ENABLED=false
# MQTT_USERNAME=              # leave empty unless Mosquitto requires auth
# MQTT_PASSWORD=              # leave empty unless Mosquitto requires auth

# ── Node-RED Simulator ──────────────────────────────────────────────────────
NODERED_PORT=1880
NODERED_MQTT_CLIENT_ID=ontime-sim-node-red

# ⬇️  MOST IMPORTANT: integer id from the bus you created in Step 1c
# Example: if Fleet returned { "id": 12 }, set SIM_BUS_ID=12
SIM_BUS_ID=<integer-id-from-step-1c>

# KML file Node-RED walks through (must be the same file you uploaded in 1b)
SIM_KML_PATH=/data/kml/202_gampaha_kirindiwela.kml
```

---

### Step 3 — Start Node-RED Locally

Run **only** the Node-RED container on your laptop. Everything else stays on the server.

```powershell
cd C:\Users\jpaba\Documents\GitHub\ontime-g2\docker
docker compose up -d --force-recreate nodered
docker logs -f ontime_nodered
```

Expected output:
```
Connected to MQTT broker at <server-ip>:1883
Publishing to transport/bus/12/location  ← your SIM_BUS_ID
```

---

### Step 4 — Activate the Trip on the Server

This is the most important step. Until you do this, Flink will ignore all GPS packets.

```powershell
Invoke-RestMethod -Method Post "$FLEET/api/v1/fleet/planned-trips/$TRIP_ID/start"
```

Expected: `"status": "EN_ROUTE"`

This publishes a `TRIP_STARTED` Kafka event. Flink will now accept telemetry for
bus `$BUS_ID` and start map-matching it against route `$ROUTE_ID`.

---

### Step 5 — Verify the Full Pipeline

**Ingestion is receiving packets from Mosquitto:**
```powershell
Invoke-RestMethod "http://<host>:8001/health"
# messages_received  → increasing every 5 seconds
# messages_validated → increasing (means Flink trip cache has the bus active)
# mqtt_broker_up     → true
```

**Redis has live position (run on server):**
```bash
redis-cli HGETALL bus:12:position
# Shows lat/lon that update every 5 seconds
```

**WebSocket live stream:**
```
ws://<host>:8004/v1/live
```
The bus should appear moving on the frontend map.

**Flink job is running:**
```
http://<host>:8081
# Should show one running job: "OnTime GPS Telemetry Processing"
```

---

## What Node-RED Publishes (MQTT Packet Format)

### Location: `transport/bus/{SIM_BUS_ID}/location`  — every 5 seconds

```json
{
  "busId": "12",
  "lat": 7.0873,
  "lon": 80.0144,
  "speed": 38.5,
  "heading": 145.0,
  "timestamp": "2026-05-12T05:30:00.000Z"
}
```

| Field | Type | Constraint | Notes |
| --- | --- | --- | --- |
| `busId` | `string` | Must match Fleet DB `id` | `"12"` not `"BUS-001"` |
| `lat` | `float` | `-90.0` to `90.0` | GPS latitude |
| `lon` | `float` | `-180.0` to `180.0` | GPS longitude |
| `speed` | `float` | `0.0` to `200.0` | km/h |
| `heading` | `float` | `0.0` to `360.0` | degrees, 0=North |
| `timestamp` | `string` | ISO 8601, ends with `Z` | UTC time |

### Heartbeat: `transport/bus/{SIM_BUS_ID}/heartbeat`  — every 30 seconds

```json
{
  "busId": "12",
  "status": "online",
  "timestamp": "2026-05-12T05:30:00.000Z"
}
```

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
| --- | --- | --- |
| Node-RED cannot connect | Port 1883 not open on server firewall | Open TCP 1883 in DigitalOcean firewall |
| `messages_received = 0` | Mosquitto container not running | SSH to server: `docker ps \| grep ontime_mqtt` |
| `messages_validated = 0` | Trip not started yet | Run Step 4 — start the trip |
| `messages_rejected` going up | Wrong `busId` format or bad JSON | Ensure `busId` = integer ID as string |
| Bus not on map | Flink not running or route not loaded | Check `http://<host>:8081`, restart Flink if needed |
| ETA not computed | `SIM_BUS_ID` mismatch with Fleet `bus_id` | Confirm `SIM_BUS_ID = str(bus.id)` from Step 1c |
