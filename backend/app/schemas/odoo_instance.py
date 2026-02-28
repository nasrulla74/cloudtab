from datetime import datetime

from pydantic import BaseModel, Field


class InstanceCreate(BaseModel):
    name: str = Field(max_length=100)
    odoo_version: str = Field(max_length=10)  # e.g. "17.0"
    edition: str = Field(default="community", pattern="^(community|enterprise)$")
    host_port: int = Field(ge=1024, le=65535)
    odoo_config: dict | None = None  # Optional odoo.conf overrides


class InstanceUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    odoo_config: dict | None = None


class InstanceRead(BaseModel):
    id: int
    server_id: int
    name: str
    odoo_version: str
    edition: str
    container_name: str
    container_id: str | None
    host_port: int
    status: str
    odoo_config: str | None
    addons_path: str | None
    pg_container_name: str | None
    pg_port: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class OdooConfigApply(BaseModel):
    updates: dict[str, str]
