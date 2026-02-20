from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.backup import (
    BackupRecordRead,
    BackupScheduleCreate,
    BackupScheduleRead,
    BackupScheduleUpdate,
)
from app.schemas.task import TaskTriggerResponse
from app.services.backup_service import (
    create_schedule,
    delete_schedule,
    get_backup_record,
    get_schedule,
    list_backup_records,
    list_schedules,
    update_schedule,
)
from app.services.odoo_service import get_instance
from app.services.server_service import create_task_log, get_server
from app.workers.backup_tasks import restore_backup, run_backup

router = APIRouter(tags=["backups"])


async def _verify_instance_ownership(instance_id: int, db: AsyncSession, user: User):
    instance = await get_instance(db, instance_id)
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")
    server = await get_server(db, instance.server_id, user)
    if not server:
        raise HTTPException(status_code=404, detail="Instance not found")
    return instance


@router.get("/instances/{instance_id}/backup-schedules", response_model=list[BackupScheduleRead])
async def list_schedules_endpoint(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_instance_ownership(instance_id, db, current_user)
    return await list_schedules(db, instance_id)


@router.post(
    "/instances/{instance_id}/backup-schedules",
    response_model=BackupScheduleRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_schedule_endpoint(
    instance_id: int,
    data: BackupScheduleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_instance_ownership(instance_id, db, current_user)
    return await create_schedule(db, instance_id, data)


@router.patch("/backup-schedules/{schedule_id}", response_model=BackupScheduleRead)
async def update_schedule_endpoint(
    schedule_id: int,
    data: BackupScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    schedule = await get_schedule(db, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await _verify_instance_ownership(schedule.instance_id, db, current_user)
    return await update_schedule(db, schedule, data)


@router.delete("/backup-schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule_endpoint(
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    schedule = await get_schedule(db, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await _verify_instance_ownership(schedule.instance_id, db, current_user)
    await delete_schedule(db, schedule)


@router.post("/instances/{instance_id}/backup-now", response_model=TaskTriggerResponse)
async def trigger_backup(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_instance_ownership(instance_id, db, current_user)
    task = run_backup.delay(instance_id)
    await create_task_log(db, task.id, current_user, "run_backup", instance_id, "instance")
    return TaskTriggerResponse(task_id=task.id, message="Backup started")


@router.get("/instances/{instance_id}/backup-records", response_model=list[BackupRecordRead])
async def list_records_endpoint(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_instance_ownership(instance_id, db, current_user)
    return await list_backup_records(db, instance_id)


@router.post("/backup-records/{record_id}/restore", response_model=TaskTriggerResponse)
async def restore_backup_endpoint(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = await get_backup_record(db, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Backup record not found")
    await _verify_instance_ownership(record.instance_id, db, current_user)

    if record.status != "success" or not record.file_path:
        raise HTTPException(
            status_code=400,
            detail="Only successful backups with a file path can be restored",
        )

    task = restore_backup.delay(record.id)
    await create_task_log(
        db, task.id, current_user, "restore_backup", record.id, "backup_record"
    )
    return TaskTriggerResponse(task_id=task.id, message="Backup restore started")
