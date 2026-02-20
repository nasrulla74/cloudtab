from datetime import datetime

from pydantic import BaseModel, Field


class DomainCreate(BaseModel):
    domain_name: str = Field(max_length=255)


class DomainRead(BaseModel):
    id: int
    instance_id: int
    domain_name: str
    status: str
    ssl_status: str
    ssl_expires_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
