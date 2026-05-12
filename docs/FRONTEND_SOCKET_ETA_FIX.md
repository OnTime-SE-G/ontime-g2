# Frontend Socket Service Fix — ETA always showing 0 min

## Root Cause

`consumer.py` (eta-service) emits ETA events to the `eta:live` Redis channel with payload:
```json
{ "event": "eta_update", "busId": "1", "eta_seconds": 315.0, "eta": 5.3, ... }
```

**websocket-service** now injects `eta` (minutes) via commit `a262f0f`. However
`socketService.ts` in both frontend repos constructs a full `BusLocation` from every
WebSocket message, using:

```ts
lat:   Number(raw.lat ?? 0),    // raw.lat is undefined for eta_update messages
lng:   Number(raw.lon ?? raw.lng ?? 0),  // → 0
speed: Number(raw.speed ?? 0),  // → 0
eta:   Number(raw.eta ?? 0),    // ← NOW WORKS (after a262f0f) but lat/lng/speed become 0
```

This means `eta_update` messages **clobber the stored bus with lat=0, lng=0, speed=0**
even though `eta` is now correctly populated.

## Fix Strategy

Keep a `busCache` Map inside `SocketService`. On every `bus:location`-type message
(i.e. when `raw.event !== "eta_update"`), update the cache with the full object.
On `eta_update` messages, retrieve the cached bus and merge only the `eta` field
before dispatching.

## Exact Patch — `src/lib/socket/socketService.ts` (passenger-web)

**File**: `src/lib/socket/socketService.ts`

Replace the class body `private listeners` section and `_open()` `onmessage` handler:

```diff
 class SocketService {
   private ws: WebSocket | null = null;
   private listeners: Listeners = new Map();
+  private busCache: Map<string, BusLocation> = new Map();
   private url = '';
   private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
   private reconnectAttempts = 0;
   private readonly maxReconnects = 5;
```

And in `onmessage`:

```diff
     this.ws.onmessage = (event) => {
       try {
         const raw = JSON.parse(event.data as string);
+
+        // --- eta_update: only refresh eta for an existing cached bus ---
+        if (raw.event === 'eta_update') {
+          const busId = String(raw.busId ?? raw.bus_id ?? '');
+          const cached = this.busCache.get(busId);
+          if (cached) {
+            const merged: BusLocation = { ...cached, eta: Number(raw.eta ?? cached.eta) };
+            this.busCache.set(busId, merged);
+            this._dispatch('bus:location', merged);
+          }
+          return;
+        }
+
         const location: BusLocation = {
           busId:      String(raw.busId ?? raw.bus_id ?? ''),
           routeId:    String(raw.routeId ?? raw.route_id ?? ''),
           lat:        Number(raw.lat ?? 0),
           lng:        Number(raw.lon ?? raw.lng ?? 0),
           speed:      Number(raw.speed ?? 0),
           heading:    Number(raw.heading ?? 0),
           timestamp:  Number(raw.timestamp ?? Date.now()),
           occupancy:  raw.occupancy ?? 'low',
           status:     raw.status ?? 'active',
           driverName: raw.driverName ?? 'Unknown',
           eta:        Number(raw.eta ?? 0),
         };
+        this.busCache.set(location.busId, location);
         this._dispatch('bus:location', location);
       } catch (e) {
         console.error('[Socket] Parse error:', e);
       }
     };
```

## Exact Patch — `lib/socket/socketService.ts` (admin-web)

**File**: `lib/socket/socketService.ts`  
**Identical changes** — same class, same `onmessage` handler, same `busCache` field.

## Commit Messages

```
fix(socket): merge eta_update into cached bus — prevent lat/lng/speed zero-clobber

eta_update WebSocket messages carry only {busId, eta, eta_seconds, event}.
Constructing a full BusLocation from them sets lat=lng=speed=0.

Fix: add busCache Map<busId, BusLocation>.
- fleet:live messages (bus:location events): update cache + dispatch as before
- eta_update messages: merge only `eta` into cached bus + dispatch merged object
  If no cached bus yet, skip dispatch (will arrive with next fleet:live tick)
```

## Testing

After this fix with the noderoad GPS simulation running:
1. Open tracking page for any bus
2. ETA stat card should show a non-zero value (e.g. "5.3 min")
3. Bus marker should not jump to (0, 0) when an eta_update arrives
4. Refreshing should immediately show the cached position
