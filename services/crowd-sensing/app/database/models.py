from sqlalchemy import Column, Integer, String, DateTime, func
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
    passenger_id = Column(String(128))
    timestamp = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())
