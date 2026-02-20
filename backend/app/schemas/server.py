from datetime import datetime

from pydantic import BaseModel, Field


class ServerCreate(BaseModel):
    name: str = Field(max_length=100)
    host: str = Field(max_length=255)
    port: int = Field(default=22, ge=1, le=65535)
    ssh_user: str = Field(default="root", max_length=100)
    ssh_key: str  # Raw private key — will be encrypted before storage


class ServerUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    host: str | None = Field(default=None, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    ssh_user: str | None = Field(default=None, max_length=100)
    ssh_key: str | None = None


class ServerRead(BaseModel):
    id: int
    name: str
    host: str
    port: int
    ssh_user: str
    status: str
    last_connected_at: datetime | None
    os_version: str | None
    cpu_cores: int | None
    ram_total_bytes: int | None
    disk_total_bytes: int | None
    docker_version: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ServerSystemInfo(BaseModel):
    os_version: str | None = None
    cpu_cores: int | None = None
    cpu_model: str | None = None
    ram_total_bytes: int | None = None
    ram_used_bytes: int | None = None
    disk_total_bytes: int | None = None
    disk_used_bytes: int | None = None
    docker_version: str | None = None
    uptime: str | None = None
