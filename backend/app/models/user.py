from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    servers: Mapped[list["Server"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    task_logs: Mapped[list["TaskLog"]] = relationship(back_populates="user", cascade="all, delete-orphan")
