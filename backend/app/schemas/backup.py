from datetime import datetime

from pydantic import BaseModel, Field


class BackupScheduleCreate(BaseModel):
    frequency: str = Field(pattern="^(daily|weekly|monthly)$")
    retention_days: int = Field(default=30, ge=1)
    storage_type: str = Field(default="local", pattern="^(local|s3)$")
    s3_bucket: str | None = None
    s3_prefix: str | None = None


class BackupScheduleUpdate(BaseModel):
    frequency: str | None = Field(default=None, pattern="^(daily|weekly|monthly)$")
    retention_days: int | None = Field(default=None, ge=1)
    is_active: bool | None = None
    storage_type: str | None = Field(default=None, pattern="^(local|s3)$")
    s3_bucket: str | None = None
    s3_prefix: str | None = None


class BackupScheduleRead(BaseModel):
    id: int
    instance_id: int
    frequency: str
    retention_days: int
    storage_type: str
    s3_bucket: str | None
    s3_prefix: str | None
    is_active: bool
    next_run_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BackupRecordRead(BaseModel):
    id: int
    instance_id: int
    schedule_id: int | None
    file_path: str | None
    file_size_bytes: int | None
    storage_type: str
    status: str
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
