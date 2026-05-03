from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HeartbeatMessage(BaseModel):
    """Device-status heartbeat sent by G1 GPS modules over MQTT."""

    model_config = ConfigDict(populate_by_name=True)

    bus_id: str = Field(..., min_length=1, max_length=50, alias="busId")
    timestamp: datetime
    device_id: str | None = Field(default=None, max_length=80, alias="deviceId")
    gps_fix: bool | None = Field(default=None, alias="gpsFix")
    satellites: int | None = Field(default=None, ge=0, le=100)
    signal_quality: float | None = Field(default=None, ge=0, alias="signalQuality")
    battery_voltage: float | None = Field(default=None, ge=0, alias="batteryVoltage")
    firmware_version: str | None = Field(default=None, max_length=80, alias="firmwareVersion")
