from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BusORM(Base):
    __tablename__ = "buses"

    id: Mapped[int] = mapped_column(primary_key=True)
    fleet_code: Mapped[str] = mapped_column(String(50), unique=True)
    plate_number: Mapped[str] = mapped_column(String(50), unique=True)

    capacity: Mapped[int] = mapped_column(Integer, default=50)

    status: Mapped[str] = mapped_column(String(20), default="IDLE")

    route_id: Mapped[int] = mapped_column(Integer, nullable=True)

    last_lat: Mapped[float] = mapped_column(nullable=True)
    last_lon: Mapped[float] = mapped_column(nullable=True)