from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.task_log import TaskLog
from app.models.user import User
from app.schemas.task import TaskRead

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{celery_task_id}", response_model=TaskRead)
async def get_task_status(
    celery_task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(TaskLog).where(
            TaskLog.celery_task_id == celery_task_id,
            TaskLog.user_id == current_user.id,
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
