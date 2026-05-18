from sqlalchemy import Column, Integer, String, DateTime, Float, func
from app.database.connection import Base

class CrowdReport(Base):
    __tablename__ = "crowd_reports"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(String(64), index=True)
    route_id = Column(Integer, nullable=False, index=True)
    direction_id = Column(Integer)
    stop_id = Column(Integer, nullable=False, index=True)
    stop_sequence = Column(Integer)
    occupancy_score = Column(Integer, nullable=False)
    occupancy_label = Column(String(16))
    passenger_id = Column(String(128), index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())

class PassengerProfile(Base):
    __tablename__ = "passenger_profiles"

    passenger_id = Column(String(128), primary_key=True, index=True)
    # User's dynamic reputation score, calibrated dynamically by consensus
    trust_score = Column(Float, default=0.8, nullable=False)
    # Total historical crowd reports submitted by this passenger
    total_reports = Column(Integer, default=0, nullable=False)
    # Reports that matched or were close to the running passenger consensus
    verified_reports = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
