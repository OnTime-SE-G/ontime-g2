import hashlib
import json
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from pydantic import ValidationError

from schemas.geo_config import SRI_LANKA_BOUNDS
from schemas.gps import GPSLocationMessage, GPSMessage
from services.ingestion.app.config import settings


@dataclass
class ValidationResult:
    success: bool
    message: Optional[GPSMessage] = None
    location: Optional[GPSLocationMessage] = None
    error_reason: Optional[str] = None
    error_type: Optional[str] = None


def _parse_payload(raw_bytes: bytes) -> tuple[dict | None, ValidationResult | None]:
    try:
        decoded_string = raw_bytes.decode("utf-8")
        parsed_json = json.loads(decoded_string)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        return None, ValidationResult(
            success=False,
            error_reason=f"Failed to parse JSON: {error}",
            error_type="JSON_PARSE",
        )

    if not isinstance(parsed_json, dict):
        return None, ValidationResult(
            success=False,
            error_reason="Schema validation failed: payload must be a JSON object",
            error_type="SCHEMA_VALIDATION",
        )

    return parsed_json, None


def _missing_timestamp_result() -> ValidationResult:
    return ValidationResult(
        success=False,
        error_reason="Missing required event timestamp",
        error_type="MISSING_TIMESTAMP",
    )


def _validation_error_result(error: ValidationError) -> ValidationResult:
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


def _geo_bounds_result(location: GPSLocationMessage) -> ValidationResult | None:
    if SRI_LANKA_BOUNDS.contains(lat=location.lat, lon=location.lon):
        return None

    return ValidationResult(
        success=False,
        error_reason=f"Coordinates out of bounds: lat={location.lat}, lon={location.lon}",
        error_type="GEO_BOUNDS",
    )


def validate_gps_location_payload(raw_bytes: bytes) -> ValidationResult:
    """Validate the G1 MQTT GPS payload shape before trip enrichment."""
    parsed_json, error_result = _parse_payload(raw_bytes)
    if error_result:
        return error_result

    if "timestamp" not in parsed_json:
        return _missing_timestamp_result()

    try:
        location = GPSLocationMessage.model_validate(parsed_json)
    except ValidationError as error:
        return _validation_error_result(error)

    geo_error = _geo_bounds_result(location)
    if geo_error:
        return geo_error

    return ValidationResult(success=True, location=location)


def validate_gps_payload(raw_bytes: bytes) -> ValidationResult:
    """Validate an enriched GPS telemetry payload without side effects."""
    parsed_json, error_result = _parse_payload(raw_bytes)
    if error_result:
        return error_result

    if "timestamp" not in parsed_json:
        return _missing_timestamp_result()

    try:
        message = GPSMessage.model_validate(parsed_json)
    except ValidationError as error:
        return _validation_error_result(error)

    geo_error = _geo_bounds_result(message)
    if geo_error:
        return geo_error

    return ValidationResult(success=True, message=message, location=message)


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
