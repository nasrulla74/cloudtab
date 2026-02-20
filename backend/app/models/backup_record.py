from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class BackupRecord(TimestampMixin, Base):
    __tablename__ = "backup_records"

    instance_id: Mapped[int] = mapped_column(ForeignKey("odoo_instances.id"), nullable=False, index=True)
    schedule_id: Mapped[int | None] = mapped_column(ForeignKey("backup_schedules.id"), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    storage_type: Mapped[str] = mapped_column(String(20), default="local")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | running | success | failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    instance: Mapped["OdooInstance"] = relationship(back_populates="backup_records")
    schedule: Mapped["BackupSchedule | None"] = relationship(back_populates="records")
