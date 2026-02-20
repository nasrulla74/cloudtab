"""Shared utilities for Celery worker tasks."""

import json
import logging
from datetime import UTC, datetime

import paramiko

from app.core.database_sync import get_sync_db
from app.models.task_log import TaskLog

logger = logging.getLogger(__name__)

# Transient SSH exceptions that warrant automatic Celery retry
SSH_RETRYABLE = (
    paramiko.SSHException,
    ConnectionRefusedError,
    ConnectionResetError,
    TimeoutError,
    OSError,
)


def update_task_log(
    celery_task_id: str,
    status: str,
    result: dict | None = None,
) -> None:
    """Update a TaskLog record with current status and optional result.

    This is the single shared helper used by all worker tasks to update
    the task_logs table. Having one implementation avoids duplication across
    server_tasks, odoo_tasks, backup_tasks, domain_tasks, and git_tasks.
    """
    db = get_sync_db()
    try:
        task = (
            db.query(TaskLog)
            .filter(TaskLog.celery_task_id == celery_task_id)
            .first()
        )
        if task:
            task.status = status
            if status == "running":
                task.started_at = datetime.now(UTC)
            if status in ("success", "failed"):
                task.completed_at = datetime.now(UTC)
            if result is not None:
                task.result = json.dumps(result)
            db.commit()
    except Exception as e:
        logger.error(
            "Failed to update task log %s to status %s: %s",
            celery_task_id,
            status,
            e,
        )
    finally:
        db.close()


class TaskLogger:
    """Context-aware logger for Celery tasks.

    Prefixes all log messages with [task_id] and optional resource identifiers
    for easy correlation in logs.

    Usage:
        tlog = TaskLogger(task_id="abc123", instance_id=5)
        tlog.info("Starting deploy")
        tlog.error("Deploy failed: %s", err)
    """

    def __init__(
        self,
        task_id: str,
        *,
        server_id: int | None = None,
        instance_id: int | None = None,
        domain_id: int | None = None,
        repo_id: int | None = None,
        record_id: int | None = None,
    ):
        self.task_id = task_id
        self._logger = logging.getLogger("app.workers")

        # Build context prefix
        parts = [f"task={task_id[:12]}"]
        if server_id is not None:
            parts.append(f"server={server_id}")
        if instance_id is not None:
            parts.append(f"instance={instance_id}")
        if domain_id is not None:
            parts.append(f"domain={domain_id}")
        if repo_id is not None:
            parts.append(f"repo={repo_id}")
        if record_id is not None:
            parts.append(f"record={record_id}")
        self._prefix = "[" + " ".join(parts) + "]"

    def info(self, msg: str, *args) -> None:
        self._logger.info(f"{self._prefix} {msg}", *args)

    def warning(self, msg: str, *args) -> None:
        self._logger.warning(f"{self._prefix} {msg}", *args)

    def error(self, msg: str, *args) -> None:
        self._logger.error(f"{self._prefix} {msg}", *args)

    def debug(self, msg: str, *args) -> None:
        self._logger.debug(f"{self._prefix} {msg}", *args)
