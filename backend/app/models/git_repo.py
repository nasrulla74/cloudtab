from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class GitRepo(TimestampMixin, Base):
    __tablename__ = "git_repos"

    instance_id: Mapped[int] = mapped_column(ForeignKey("odoo_instances.id"), nullable=False, unique=True)
    repo_url: Mapped[str] = mapped_column(String(500), nullable=False)
    branch: Mapped[str] = mapped_column(String(100), default="main")
    deploy_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)

    instance: Mapped["OdooInstance"] = relationship(back_populates="git_repo")
