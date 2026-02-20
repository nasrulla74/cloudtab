from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class BackupSchedule(TimestampMixin, Base):
    __tablename__ = "backup_schedules"

    instance_id: Mapped[int] = mapped_column(ForeignKey("odoo_instances.id"), nullable=False, index=True)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)  # daily | weekly | monthly
    retention_days: Mapped[int] = mapped_column(Integer, default=30)
    storage_type: Mapped[str] = mapped_column(String(20), default="local")  # local | s3
    s3_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    s3_prefix: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    instance: Mapped["OdooInstance"] = relationship(back_populates="backup_schedules")
    records: Mapped[list["BackupRecord"]] = relationship(back_populates="schedule")
