import logging
import os
import tempfile
from datetime import UTC, datetime, timedelta

from app.core.database_sync import get_sync_db
from app.core.encryption import decrypt_value
from app.models.backup_record import BackupRecord
from app.models.backup_schedule import BackupSchedule
from app.models.odoo_instance import OdooInstance
from app.models.server import Server
from app.services.s3_service import (
    delete_from_s3,
    download_file_from_s3,
    parse_s3_uri,
    upload_file_to_s3,
)
from app.services.ssh_service import SSHService
from app.workers.celery_app import celery_app
from app.workers.utils import TaskLogger, update_task_log

logger = logging.getLogger(__name__)


def _get_schedule_storage_info(db, schedule_id: int | None) -> dict:
    """Look up the schedule to determine storage type and S3 settings.

    Returns dict with keys: storage_type, s3_bucket, s3_prefix
    """
    if schedule_id is None:
        return {"storage_type": "local", "s3_bucket": None, "s3_prefix": None}
    schedule = (
        db.query(BackupSchedule)
        .filter(BackupSchedule.id == schedule_id)
        .first()
    )
    if not schedule:
        return {"storage_type": "local", "s3_bucket": None, "s3_prefix": None}
    return {
        "storage_type": schedule.storage_type,
        "s3_bucket": schedule.s3_bucket,
        "s3_prefix": schedule.s3_prefix,
    }


def _upload_backup_to_s3(
    ssh: SSHService,
    remote_file: str,
    bucket: str,
    s3_key: str,
    tlog: TaskLogger | None = None,
) -> tuple[str, int | None]:
    """Download backup from remote server via SSH, then upload to S3.

    Returns (s3_uri, file_size_bytes).
    """
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=True) as tmp:
        local_tmp = tmp.name

    # SCP the backup file from remote server to local temp
    if tlog:
        tlog.info("Downloading backup from server to worker: %s", remote_file)
    ssh.download_file(remote_file, local_tmp)

    try:
        # Get file size
        file_size = os.path.getsize(local_tmp)

        # Upload to S3
        if tlog:
            tlog.info("Uploading to S3: s3://%s/%s (%d bytes)", bucket, s3_key, file_size)
        s3_uri = upload_file_to_s3(local_tmp, bucket, s3_key)
        return s3_uri, file_size
    finally:
        # Clean up local temp file
        try:
            os.remove(local_tmp)
        except OSError:
            pass


def _download_s3_to_remote(
    ssh: SSHService,
    s3_uri: str,
    remote_path: str,
    tlog: TaskLogger | None = None,
) -> None:
    """Download a backup from S3, then SCP it to the remote server."""
    bucket, s3_key = parse_s3_uri(s3_uri)

    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=True) as tmp:
        local_tmp = tmp.name

    try:
        # Download from S3 to local
        if tlog:
            tlog.info("Downloading from S3: %s", s3_uri)
        download_file_from_s3(bucket, s3_key, local_tmp)

        # Upload to remote server via SCP
        if tlog:
            tlog.info("Uploading to remote server: %s", remote_path)
        ssh.upload_file(local_tmp, remote_path)
    finally:
        try:
            os.remove(local_tmp)
        except OSError:
            pass


@celery_app.task(bind=True, name="backup.restore_backup")
def restore_backup(self, record_id: int) -> dict:
    """Restore an Odoo instance from a backup record (pg_restore + filestore).

    Supports both local and S3 backup records. For S3 backups, the file is
    downloaded from S3 to the remote server before extraction.
    """
    task_id = self.request.id
    tlog = TaskLogger(task_id, record_id=record_id)
    update_task_log(task_id, "running")

    db = get_sync_db()
    try:
        record = db.query(BackupRecord).filter(BackupRecord.id == record_id).first()
        if not record:
            result = {"error": "Backup record not found"}
            tlog.error("Backup record %d not found", record_id)
            update_task_log(task_id, "failed", result)
            return result

        if record.status != "success" or not record.file_path:
            result = {"error": "Backup record is not in a restorable state"}
            tlog.error("Record %d not restorable (status=%s)", record_id, record.status)
            update_task_log(task_id, "failed", result)
            return result

        instance = db.query(OdooInstance).filter(OdooInstance.id == record.instance_id).first()
        if not instance:
            result = {"error": "Instance not found"}
            tlog.error("Instance not found for record %d", record_id)
            update_task_log(task_id, "failed", result)
            return result

        # Update tlog with instance context
        tlog = TaskLogger(task_id, instance_id=instance.id, record_id=record_id)

        server = db.query(Server).filter(Server.id == instance.server_id).first()
        if not server:
            result = {"error": "Server not found"}
            tlog.error("Server not found for instance %d", instance.id)
            update_task_log(task_id, "failed", result)
            return result

        ssh = SSHService(
            host=server.host,
            port=server.port,
            username=server.ssh_user,
            private_key_pem=decrypt_value(server.ssh_key_encrypted),
        )

        is_s3 = record.storage_type == "s3" and record.file_path.startswith("s3://")

        try:
            with ssh:
                odoo_name = instance.container_name
                pg_name = instance.pg_container_name
                data_dir = f"/opt/cloudtab/{odoo_name}/data"
                restore_tmp = f"/tmp/{odoo_name}_restore"
                sql_dump = f"{restore_tmp}/{odoo_name}_dump.sql"

                # If S3 backup, download to server first
                if is_s3:
                    backup_file = f"/tmp/{odoo_name}_s3_restore.tar.gz"
                    tlog.info("Downloading S3 backup to server: %s", record.file_path)
                    _download_s3_to_remote(ssh, record.file_path, backup_file, tlog)
                else:
                    backup_file = record.file_path
                    # Verify local backup file exists
                    _, _, exit_code = ssh.execute(f"test -f {backup_file}", timeout=5)
                    if exit_code != 0:
                        raise RuntimeError(
                            f"Backup file not found on server: {backup_file}"
                        )

                # Stop Odoo container to prevent writes during restore
                tlog.info("Stopping Odoo container %s for restore", odoo_name)
                ssh.execute(f"docker stop {odoo_name}", timeout=60)

                # Create temp extraction dir
                ssh.execute(
                    f"rm -rf {restore_tmp} && mkdir -p {restore_tmp}", timeout=10
                )

                # Extract tarball
                tlog.info("Extracting backup %s", backup_file)
                stdout, stderr, exit_code = ssh.execute(
                    f"tar -xzf {backup_file} -C {restore_tmp}",
                    timeout=600,
                )
                if exit_code != 0:
                    raise RuntimeError(f"tar extract failed: {stderr}")

                # Restore PostgreSQL database
                tlog.info("Restoring database via %s", pg_name)
                # Terminate active connections then drop+recreate
                ssh.execute(
                    f"docker exec {pg_name} psql -U odoo -d postgres -c "
                    "\"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = 'odoo' AND pid <> pg_backend_pid();\"",
                    timeout=30,
                )
                ssh.execute(
                    f"docker exec {pg_name} psql -U odoo -d postgres "
                    "-c \"DROP DATABASE IF EXISTS odoo;\"",
                    timeout=30,
                )
                ssh.execute(
                    f"docker exec {pg_name} psql -U odoo -d postgres "
                    "-c \"CREATE DATABASE odoo OWNER odoo;\"",
                    timeout=30,
                )

                # Copy SQL dump into container and restore
                ssh.execute(
                    f"docker cp {sql_dump} {pg_name}:/tmp/restore.sql",
                    timeout=60,
                )
                stdout, stderr, exit_code = ssh.execute(
                    f"docker exec {pg_name} psql -U odoo -d odoo -f /tmp/restore.sql",
                    timeout=600,
                )
                if exit_code != 0:
                    tlog.warning("psql restore warnings: %s", stderr)

                ssh.execute(
                    f"docker exec {pg_name} rm -f /tmp/restore.sql", timeout=5
                )

                # Restore filestore
                tlog.info("Restoring filestore")
                ssh.execute(f"rm -rf {data_dir}/filestore", timeout=30)
                _, _, has_filestore = ssh.execute(
                    f"test -d {restore_tmp}/filestore", timeout=5
                )
                if has_filestore == 0:
                    ssh.execute(
                        f"cp -a {restore_tmp}/filestore {data_dir}/filestore",
                        timeout=120,
                    )

                # Clean up temp files
                ssh.execute(f"rm -rf {restore_tmp}", timeout=10)
                if is_s3:
                    ssh.execute(f"rm -f {backup_file}", timeout=10)

                # Restart Odoo container
                tlog.info("Starting Odoo container %s after restore", odoo_name)
                ssh.execute(f"docker start {odoo_name}", timeout=60)

                result = {
                    "status": "success",
                    "message": f"Restored from {record.file_path}",
                    "record_id": record_id,
                    "storage_type": record.storage_type,
                }
                tlog.info("Restore complete")
                update_task_log(task_id, "success", result)
                return result

        except Exception as e:
            # Try to restart the container even if restore fails
            try:
                with SSHService(
                    host=server.host,
                    port=server.port,
                    username=server.ssh_user,
                    private_key_pem=decrypt_value(server.ssh_key_encrypted),
                ) as recovery_ssh:
                    recovery_ssh.execute(
                        f"docker start {instance.container_name}", timeout=60
                    )
            except Exception:
                tlog.error("Failed to restart container after failed restore")

            result = {"error": str(e)}
            tlog.error("Restore failed: %s", e)
            update_task_log(task_id, "failed", result)
            return result

    except Exception as e:
        result = {"error": str(e)}
        tlog.error("Restore failed (outer): %s", e)
        update_task_log(task_id, "failed", result)
        return result
    finally:
        db.close()


@celery_app.task(bind=True, name="backup.run_backup")
def run_backup(self, instance_id: int, schedule_id: int | None = None) -> dict:
    """Run a backup of an Odoo instance (pg_dump + filestore).

    Supports both local and S3 storage. When the schedule specifies S3 storage,
    the backup is first created locally on the server, then uploaded to S3, and
    the local copy is removed.
    """
    task_id = self.request.id
    tlog = TaskLogger(task_id, instance_id=instance_id)
    update_task_log(task_id, "running")

    db = get_sync_db()
    try:
        instance = db.query(OdooInstance).filter(OdooInstance.id == instance_id).first()
        if not instance:
            result = {"error": "Instance not found"}
            tlog.error("Instance %d not found", instance_id)
            update_task_log(task_id, "failed", result)
            return result

        server = db.query(Server).filter(Server.id == instance.server_id).first()
        if not server:
            result = {"error": "Server not found"}
            tlog.error("Server not found for instance %d", instance_id)
            update_task_log(task_id, "failed", result)
            return result

        # Determine storage type from schedule
        storage_info = _get_schedule_storage_info(db, schedule_id)
        storage_type = storage_info["storage_type"]
        s3_bucket = storage_info["s3_bucket"]
        s3_prefix = storage_info["s3_prefix"] or ""

        tlog.info(
            "Starting backup for %s (storage=%s, schedule=%s)",
            instance.container_name, storage_type, schedule_id,
        )

        # Create backup record
        record = BackupRecord(
            instance_id=instance_id,
            schedule_id=schedule_id,
            storage_type=storage_type,
            status="running",
            started_at=datetime.now(UTC),
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        ssh = SSHService(
            host=server.host,
            port=server.port,
            username=server.ssh_user,
            private_key_pem=decrypt_value(server.ssh_key_encrypted),
        )

        try:
            with ssh:
                odoo_name = instance.container_name
                pg_name = instance.pg_container_name
                timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
                backup_dir = f"/opt/cloudtab/{odoo_name}/backups"
                backup_filename = f"{odoo_name}_{timestamp}.tar.gz"
                backup_file = f"{backup_dir}/{backup_filename}"

                # Create backup directory
                ssh.execute(f"mkdir -p {backup_dir}", timeout=10)

                # Dump PostgreSQL database
                tlog.info("Dumping PostgreSQL via %s", pg_name)
                sql_dump = f"/tmp/{odoo_name}_dump.sql"
                stdout, stderr, exit_code = ssh.execute(
                    f"docker exec {pg_name} pg_dumpall -U odoo > {sql_dump}",
                    timeout=300,
                )
                if exit_code != 0:
                    raise RuntimeError(f"pg_dump failed: {stderr}")

                # Create tarball with SQL dump + filestore
                tlog.info("Creating tarball %s", backup_file)
                data_dir = f"/opt/cloudtab/{odoo_name}/data"
                stdout, stderr, exit_code = ssh.execute(
                    f"tar -czf {backup_file} "
                    f"-C /tmp {odoo_name}_dump.sql "
                    f"-C {data_dir} .",
                    timeout=600,
                )
                if exit_code != 0:
                    raise RuntimeError(f"tar failed: {stderr}")

                # Clean up temp SQL dump
                ssh.execute(f"rm -f {sql_dump}", timeout=5)

                # Get file size from remote server
                size_out, _, _ = ssh.execute(
                    f"stat -c%s {backup_file}", timeout=5
                )
                file_size = int(size_out) if size_out.strip().isdigit() else None

                # Handle S3 upload if storage type is s3
                final_path = backup_file
                if storage_type == "s3" and s3_bucket:
                    # Build S3 key: prefix/container_name/filename
                    s3_key_parts = [s3_prefix.strip("/"), backup_filename]
                    s3_key = "/".join(p for p in s3_key_parts if p)

                    s3_uri, s3_size = _upload_backup_to_s3(
                        ssh, backup_file, s3_bucket, s3_key, tlog
                    )
                    final_path = s3_uri
                    if s3_size:
                        file_size = s3_size

                    # Remove local backup after successful S3 upload
                    ssh.execute(f"rm -f {backup_file}", timeout=10)
                    tlog.info("S3 upload complete, local copy removed")

                # Update record
                record.status = "success"
                record.completed_at = datetime.now(UTC)
                record.file_path = final_path
                record.file_size_bytes = file_size
                db.commit()

                result = {
                    "status": "success",
                    "storage_type": storage_type,
                    "file_path": final_path,
                    "file_size_bytes": file_size,
                }
                tlog.info("Backup complete: %s (%s bytes)", final_path, file_size)
                update_task_log(task_id, "success", result)
                return result

        except Exception as e:
            record.status = "failed"
            record.completed_at = datetime.now(UTC)
            record.error_message = str(e)
            db.commit()

            result = {"error": str(e)}
            tlog.error("Backup failed: %s", e)
            update_task_log(task_id, "failed", result)
            return result

    except Exception as e:
        result = {"error": str(e)}
        tlog.error("Backup failed (outer): %s", e)
        update_task_log(task_id, "failed", result)
        return result
    finally:
        db.close()


def _calculate_next_run(frequency: str) -> datetime:
    """Calculate the next run time based on schedule frequency."""
    now = datetime.now(UTC)
    if frequency == "daily":
        return now + timedelta(days=1)
    elif frequency == "weekly":
        return now + timedelta(weeks=1)
    elif frequency == "monthly":
        return now + timedelta(days=30)
    return now + timedelta(days=1)


@celery_app.task(name="backup.process_due_backups")
def process_due_backups() -> dict:
    """Periodic task: find all active backup schedules that are due and trigger backups."""
    db = get_sync_db()
    try:
        now = datetime.now(UTC)
        due_schedules = (
            db.query(BackupSchedule)
            .filter(
                BackupSchedule.is_active.is_(True),
                BackupSchedule.next_run_at <= now,
            )
            .all()
        )

        triggered = []
        errors = []

        for schedule in due_schedules:
            try:
                # Verify the instance still exists
                instance = (
                    db.query(OdooInstance)
                    .filter(OdooInstance.id == schedule.instance_id)
                    .first()
                )
                if not instance:
                    logger.warning(
                        "Schedule %d references missing instance %d, skipping",
                        schedule.id,
                        schedule.instance_id,
                    )
                    continue

                if instance.status != "running":
                    logger.info(
                        "Instance %d (%s) not running, skipping scheduled backup",
                        instance.id,
                        instance.name,
                    )
                    continue

                # Dispatch the backup task
                task = run_backup.delay(schedule.instance_id, schedule.id)
                triggered.append({
                    "schedule_id": schedule.id,
                    "instance_id": schedule.instance_id,
                    "task_id": task.id,
                })

                # Advance next_run_at to prevent re-triggering
                schedule.next_run_at = _calculate_next_run(schedule.frequency)
                db.commit()

                logger.info(
                    "Triggered scheduled backup for instance %s "
                    "(schedule=%d, task=%s)",
                    instance.name,
                    schedule.id,
                    task.id,
                )
            except Exception as e:
                logger.error(
                    "Failed to trigger backup for schedule %d: %s",
                    schedule.id,
                    e,
                )
                errors.append({"schedule_id": schedule.id, "error": str(e)})

        return {
            "checked_at": now.isoformat(),
            "due_count": len(due_schedules),
            "triggered": triggered,
            "errors": errors,
        }

    except Exception as e:
        logger.error("process_due_backups failed: %s", e)
        return {"error": str(e)}
    finally:
        db.close()


@celery_app.task(name="backup.cleanup_expired_backups")
def cleanup_expired_backups() -> dict:
    """Periodic task: delete backup files older than their schedule's retention_days.

    Handles both local (SSH rm) and S3 (boto3 delete) storage types.
    """
    db = get_sync_db()
    try:
        now = datetime.now(UTC)
        cleaned = []
        errors = []

        # Find all schedules with retention policies
        schedules = (
            db.query(BackupSchedule)
            .filter(BackupSchedule.retention_days > 0)
            .all()
        )

        for schedule in schedules:
            cutoff = now - timedelta(days=schedule.retention_days)

            expired_records = (
                db.query(BackupRecord)
                .filter(
                    BackupRecord.schedule_id == schedule.id,
                    BackupRecord.status == "success",
                    BackupRecord.created_at < cutoff,
                    BackupRecord.file_path.isnot(None),
                )
                .all()
            )

            if not expired_records:
                continue

            # Separate S3 and local records
            s3_records = [
                r for r in expired_records
                if r.storage_type == "s3" and r.file_path.startswith("s3://")
            ]
            local_records = [r for r in expired_records if r not in s3_records]

            # Clean up S3 records (no SSH needed)
            for record in s3_records:
                try:
                    bucket, s3_key = parse_s3_uri(record.file_path)
                    if delete_from_s3(bucket, s3_key):
                        record.file_path = None
                        record.file_size_bytes = None
                        db.commit()
                        cleaned.append({
                            "record_id": record.id,
                            "schedule_id": schedule.id,
                            "storage": "s3",
                        })
                        logger.info(
                            "Cleaned up expired S3 backup record %d "
                            "(schedule=%d, retention=%dd)",
                            record.id,
                            schedule.id,
                            schedule.retention_days,
                        )
                    else:
                        errors.append({
                            "record_id": record.id,
                            "error": "S3 delete failed",
                        })
                except Exception as e:
                    logger.error(
                        "Failed to clean S3 backup record %d: %s", record.id, e
                    )
                    errors.append({"record_id": record.id, "error": str(e)})

            # Clean up local records (needs SSH)
            if local_records:
                instance = (
                    db.query(OdooInstance)
                    .filter(OdooInstance.id == schedule.instance_id)
                    .first()
                )
                if not instance:
                    continue

                server = (
                    db.query(Server)
                    .filter(Server.id == instance.server_id)
                    .first()
                )
                if not server:
                    continue

                try:
                    ssh = SSHService(
                        host=server.host,
                        port=server.port,
                        username=server.ssh_user,
                        private_key_pem=decrypt_value(server.ssh_key_encrypted),
                    )
                    with ssh:
                        for record in local_records:
                            try:
                                ssh.execute(
                                    f"rm -f {record.file_path}", timeout=10
                                )
                                record.file_path = None
                                record.file_size_bytes = None
                                db.commit()
                                cleaned.append({
                                    "record_id": record.id,
                                    "schedule_id": schedule.id,
                                    "storage": "local",
                                })
                                logger.info(
                                    "Cleaned up expired local backup record %d "
                                    "(schedule=%d, retention=%dd)",
                                    record.id,
                                    schedule.id,
                                    schedule.retention_days,
                                )
                            except Exception as e:
                                logger.error(
                                    "Failed to clean backup record %d: %s",
                                    record.id,
                                    e,
                                )
                                errors.append({
                                    "record_id": record.id,
                                    "error": str(e),
                                })

                except Exception as e:
                    logger.error(
                        "SSH connection failed for cleanup on server %d: %s",
                        server.id,
                        e,
                    )
                    errors.append({"server_id": server.id, "error": str(e)})

        return {
            "cleaned_at": now.isoformat(),
            "cleaned_count": len(cleaned),
            "cleaned": cleaned,
            "errors": errors,
        }

    except Exception as e:
        logger.error("cleanup_expired_backups failed: %s", e)
        return {"error": str(e)}
    finally:
        db.close()
