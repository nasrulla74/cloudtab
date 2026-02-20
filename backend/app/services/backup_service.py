from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.backup_record import BackupRecord
from app.models.backup_schedule import BackupSchedule
from app.schemas.backup import BackupScheduleCreate, BackupScheduleUpdate


def _calculate_next_run(frequency: str) -> datetime:
    """Calculate the next run time based on frequency."""
    now = datetime.now(UTC)
    if frequency == "daily":
        return now + timedelta(days=1)
    elif frequency == "weekly":
        return now + timedelta(weeks=1)
    elif frequency == "monthly":
        return now + timedelta(days=30)
    return now + timedelta(days=1)


async def list_schedules(db: AsyncSession, instance_id: int) -> list[BackupSchedule]:
    result = await db.execute(
        select(BackupSchedule)
        .where(BackupSchedule.instance_id == instance_id)
        .order_by(BackupSchedule.created_at.desc())
    )
    return list(result.scalars().all())


async def create_schedule(
    db: AsyncSession, instance_id: int, data: BackupScheduleCreate
) -> BackupSchedule:
    schedule = BackupSchedule(
        instance_id=instance_id,
        frequency=data.frequency,
        retention_days=data.retention_days,
        storage_type=data.storage_type,
        s3_bucket=data.s3_bucket,
        s3_prefix=data.s3_prefix,
        next_run_at=_calculate_next_run(data.frequency),
    )
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return schedule


async def update_schedule(
    db: AsyncSession, schedule: BackupSchedule, data: BackupScheduleUpdate
) -> BackupSchedule:
    if data.frequency is not None:
        schedule.frequency = data.frequency
        schedule.next_run_at = _calculate_next_run(data.frequency)
    if data.retention_days is not None:
        schedule.retention_days = data.retention_days
    if data.is_active is not None:
        schedule.is_active = data.is_active
    await db.commit()
    await db.refresh(schedule)
    return schedule


async def delete_schedule(db: AsyncSession, schedule: BackupSchedule) -> None:
    await db.delete(schedule)
    await db.commit()


async def get_schedule(db: AsyncSession, schedule_id: int) -> BackupSchedule | None:
    result = await db.execute(
        select(BackupSchedule).where(BackupSchedule.id == schedule_id)
    )
    return result.scalar_one_or_none()


async def get_backup_record(db: AsyncSession, record_id: int) -> BackupRecord | None:
    result = await db.execute(
        select(BackupRecord).where(BackupRecord.id == record_id)
    )
    return result.scalar_one_or_none()


async def list_backup_records(db: AsyncSession, instance_id: int) -> list[BackupRecord]:
    result = await db.execute(
        select(BackupRecord)
        .where(BackupRecord.instance_id == instance_id)
        .order_by(BackupRecord.created_at.desc())
        .limit(50)
    )
    return list(result.scalars().all())
