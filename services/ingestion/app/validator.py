import hashlib
import json
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from pydantic import ValidationError

from schemas.geo_config import SRI_LANKA_BOUNDS
from schemas.gps import GPSMessage
from services.ingestion.app.config import settings


@dataclass
class ValidationResult:
    success: bool
    message: Optional[GPSMessage] = None
    error_reason: Optional[str] = None
    error_type: Optional[str] = None


def validate_gps_payload(raw_bytes: bytes) -> ValidationResult:
    """Validate a raw GPS telemetry payload without side effects."""
    try:
        decoded_string = raw_bytes.decode("utf-8")
        parsed_json = json.loads(decoded_string)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        return ValidationResult(
            success=False,
            error_reason=f"Failed to parse JSON: {error}",
            error_type="JSON_PARSE",
        )

    try:
        message = GPSMessage.model_validate(parsed_json)
    except ValidationError as error:
        errors = error.errors()
        error_messages = [
            f"{entry['loc'][0]}: {entry['msg']}" if entry["loc"] else entry["msg"]
            for entry in errors
        ]
        return ValidationResult(
            success=False,
            error_reason=f"Schema validation failed: {'; '.join(error_messages)}",
            error_type="SCHEMA_VALIDATION",
        )

    if not SRI_LANKA_BOUNDS.contains(lat=message.lat, lon=message.lon):
        return ValidationResult(
            success=False,
            error_reason=f"Coordinates out of bounds: lat={message.lat}, lon={message.lon}",
            error_type="GEO_BOUNDS",
        )

    return ValidationResult(success=True, message=message)


@dataclass
class BusIngestionState:
    last_timestamp: datetime
    last_receive_time: float
    recent_hashes: deque


class StatefulValidator:
    def __init__(
        self,
        *,
        duplicate_cache_size: Optional[int] = None,
        min_message_interval_seconds: Optional[float] = None,
    ):
        self._bus_state: dict[str, BusIngestionState] = {}
        self._duplicate_cache_size = (
            duplicate_cache_size
            if duplicate_cache_size is not None
            else settings.duplicate_cache_size
        )
        self._min_message_interval_seconds = (
            min_message_interval_seconds
            if min_message_interval_seconds is not None
            else settings.min_message_interval_seconds
        )

    def validate(self, raw_bytes: bytes) -> ValidationResult:
        result = validate_gps_payload(raw_bytes)
        if not result.success or not result.message:
            return result

        message = result.message
        bus_id = message.bus_id
        payload_hash = hashlib.sha256(
            f"{bus_id}_{message.timestamp.isoformat()}_{message.lat}_{message.lon}".encode("utf-8")
        ).hexdigest()

        state = self._bus_state.get(bus_id)
        current_time = time.monotonic()

        if state is None:
            self._bus_state[bus_id] = BusIngestionState(
                last_timestamp=message.timestamp,
                last_receive_time=current_time,
                recent_hashes=deque([payload_hash], maxlen=self._duplicate_cache_size),
            )
            return result

        if payload_hash in state.recent_hashes:
            return ValidationResult(
                success=False,
                error_reason="Duplicate payload hash detected within recent window",
                error_type="DUPLICATE",
            )

        if current_time - state.last_receive_time < self._min_message_interval_seconds:
            return ValidationResult(
                success=False,
                error_reason=f"Rate limit exceeded for bus {bus_id}",
                error_type="RATE_LIMIT",
            )

        if message.timestamp <= state.last_timestamp:
            return ValidationResult(
                success=False,
                error_reason=(
                    f"Message out of sequence: {message.timestamp} <= {state.last_timestamp}"
                ),
                error_type="SEQUENCE_ERROR",
            )

        state.last_timestamp = message.timestamp
        state.last_receive_time = current_time
        state.recent_hashes.append(payload_hash)
        return result
