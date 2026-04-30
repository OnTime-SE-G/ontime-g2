from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from scripts.models.base import Base


class BusORM(Base):
    __tablename__ = "buses"

    id: Mapped[int] = mapped_column(primary_key=True)
    fleet_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    plate_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=50)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")

    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"), nullable=False)

    route = relationship("RouteORM", back_populates="buses")
