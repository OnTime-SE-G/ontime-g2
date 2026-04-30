import json
import time
import hashlib
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict

from pydantic import ValidationError

from schemas.geo_config import SRI_LANKA_BOUNDS
from schemas.gps import GPSMessage


@dataclass
class ValidationResult:
    success: bool
    message: Optional[GPSMessage] = None
    error_reason: Optional[str] = None
    error_type: Optional[str] = None


def validate_gps_payload(raw_bytes: bytes) -> ValidationResult:
    """
    Pure function to validate a GPS telemetry payload.
    No Kafka, no MQTT, no side effects.
    """
    # 1. JSON parseable?
    try:
        decoded_string = raw_bytes.decode("utf-8")
        parsed_json = json.loads(decoded_string)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return ValidationResult(
            success=False,
            error_reason=f"Failed to parse JSON: {str(e)}",
            error_type="JSON_PARSE"
        )

    # 2. Matches GPSMessage Pydantic model?
    try:
        # Pydantic will validate types, missing required fields, and speed bounds
        message = GPSMessage.model_validate(parsed_json)
    except ValidationError as e:
        # Extract a readable error message from Pydantic
        errors = e.errors()
        error_msgs = [f"{err['loc'][0]}: {err['msg']}" if err['loc'] else err['msg'] for err in errors]
        return ValidationResult(
            success=False,
            error_reason=f"Schema validation failed: {'; '.join(error_msgs)}",
            error_type="SCHEMA_VALIDATION"
        )

    # 3. Inside SRI_LANKA_BOUNDS?
    if not SRI_LANKA_BOUNDS.contains(lat=message.lat, lon=message.lon):
        return ValidationResult(
            success=False,
            error_reason=f"Coordinates out of bounds: lat={message.lat}, lon={message.lon}",
            error_type="GEO_BOUNDS"
        )

    return ValidationResult(success=True, message=message)


@dataclass
class BusIngestionState:
    last_timestamp: datetime
    last_receive_time: float
    recent_hashes: deque = field(default_factory=lambda: deque(maxlen=100))


class StatefulValidator:
    def __init__(self):
        self._bus_state: Dict[str, BusIngestionState] = {}

    def validate(self, raw_bytes: bytes) -> ValidationResult:
        # Step 1-3: existing pure validation (JSON, schema, geo)
        result = validate_gps_payload(raw_bytes)
        if not result.success or not result.message:
            return result

        msg = result.message
        bus_id = msg.bus_id
        
        # Step 4: Duplicate detection
        # Hash = sha256(busId + timestamp + lat + lon)
        hash_str = f"{bus_id}_{msg.timestamp.isoformat()}_{msg.lat}_{msg.lon}"
        payload_hash = hashlib.sha256(hash_str.encode("utf-8")).hexdigest()

        state = self._bus_state.get(bus_id)
        current_time = time.monotonic()

        if state is None:
            state = BusIngestionState(
                last_timestamp=msg.timestamp,
                last_receive_time=current_time
            )
            state.recent_hashes.append(payload_hash)
            self._bus_state[bus_id] = state
            return result

        if payload_hash in state.recent_hashes:
            return ValidationResult(
                success=False,
                error_reason="Duplicate payload hash detected within recent window",
                error_type="DUPLICATE"
            )

        # Step 5: Rate limiting
        # If last message from same busId was < 1 second ago -> RATE_LIMIT
        if current_time - state.last_receive_time < 1.0:
            return ValidationResult(
                success=False,
                error_reason=f"Rate limit exceeded for bus {bus_id}",
                error_type="RATE_LIMIT"
            )

        # Step 6: Timestamp sequence
        # If message timestamp <= last timestamp from same busId -> SEQUENCE_ERROR
        if msg.timestamp <= state.last_timestamp:
            return ValidationResult(
                success=False,
                error_reason=f"Message out of sequence: {msg.timestamp} <= {state.last_timestamp}",
                error_type="SEQUENCE_ERROR"
            )

        # All passed -> update bus state
        state.last_timestamp = msg.timestamp
        state.last_receive_time = current_time
        state.recent_hashes.append(payload_hash)
        
        return result
