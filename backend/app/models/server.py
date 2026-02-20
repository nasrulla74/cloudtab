from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Server(TimestampMixin, Base):
    __tablename__ = "servers"

    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=22)
    ssh_user: Mapped[str] = mapped_column(String(100), default="root")
    ssh_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="unknown")
    last_connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Cached system info
    os_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cpu_cores: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ram_total_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    disk_total_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    docker_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    owner: Mapped["User"] = relationship(back_populates="servers")
    instances: Mapped[list["OdooInstance"]] = relationship(back_populates="server", cascade="all, delete-orphan")
