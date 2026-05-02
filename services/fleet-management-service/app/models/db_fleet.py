from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FleetBusORM(Base):
    __tablename__ = "buses"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Unique identifiers
    fleet_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    plate_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    # Static configuration
    capacity: Mapped[int] = mapped_column(Integer, default=50)

    # Assignment (can be null if not assigned yet)
    route_id: Mapped[int] = mapped_column(Integer, nullable=True)