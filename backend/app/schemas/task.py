from datetime import datetime

from pydantic import BaseModel


class TaskRead(BaseModel):
    id: int
    celery_task_id: str
    task_type: str
    target_id: int | None
    target_type: str | None
    status: str
    result: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskTriggerResponse(BaseModel):
    task_id: str  # celery_task_id for polling
    message: str
