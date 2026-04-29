import json
from dataclasses import dataclass
from typing import Optional

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
