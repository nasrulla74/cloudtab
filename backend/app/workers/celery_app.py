from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "cloudtab",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Retry policy for transient failures
    task_default_retry_delay=60,
    task_max_retries=3,
    # Redis connection resilience — survive transient Redis restarts
    broker_connection_retry_on_startup=True,
    redis_retry_on_timeout=True,
    redis_socket_connect_timeout=10,
    redis_socket_timeout=10,
    result_backend_transport_options={
        "retry_policy": {
            "timeout": 5.0,
        },
    },
)

# Celery Beat periodic tasks
celery_app.conf.beat_schedule = {
    "process-due-backups": {
        "task": "backup.process_due_backups",
        "schedule": crontab(minute="*/5"),  # Check every 5 minutes
    },
    "cleanup-expired-backups": {
        "task": "backup.cleanup_expired_backups",
        "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM UTC
    },
}

celery_app.autodiscover_tasks([
    "app.workers.server_tasks",
    "app.workers.odoo_tasks",
    "app.workers.backup_tasks",
    "app.workers.domain_tasks",
    "app.workers.git_tasks",
])
