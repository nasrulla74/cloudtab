from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Domain(TimestampMixin, Base):
    __tablename__ = "domains"

    instance_id: Mapped[int] = mapped_column(ForeignKey("odoo_instances.id"), nullable=False, index=True)
    domain_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    ssl_status: Mapped[str] = mapped_column(String(20), default="none")
    ssl_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    instance: Mapped["OdooInstance"] = relationship(back_populates="domains")
