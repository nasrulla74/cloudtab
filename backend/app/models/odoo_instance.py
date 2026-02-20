from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class OdooInstance(TimestampMixin, Base):
    __tablename__ = "odoo_instances"

    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    odoo_version: Mapped[str] = mapped_column(String(10), nullable=False)  # e.g. "17.0"
    edition: Mapped[str] = mapped_column(String(20), default="community")  # community | enterprise
    container_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    container_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    host_port: Mapped[int] = mapped_column(Integer, nullable=False)  # Port exposed on host
    status: Mapped[str] = mapped_column(String(20), default="pending")
    odoo_config: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON odoo.conf overrides
    addons_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Postgres container for this instance
    pg_container_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pg_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pg_password: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Encrypted

    server: Mapped["Server"] = relationship(back_populates="instances")
    domains: Mapped[list["Domain"]] = relationship(back_populates="instance", cascade="all, delete-orphan")
    backup_schedules: Mapped[list["BackupSchedule"]] = relationship(back_populates="instance", cascade="all, delete-orphan")
    backup_records: Mapped[list["BackupRecord"]] = relationship(back_populates="instance", cascade="all, delete-orphan")
    git_repo: Mapped["GitRepo | None"] = relationship(back_populates="instance", uselist=False, cascade="all, delete-orphan")
