"""Structured logging configuration for CloudTab."""

import logging
import sys
from datetime import UTC, datetime


class CloudTabFormatter(logging.Formatter):
    """Structured formatter with timestamp, level, module, and message."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        level = record.levelname.ljust(8)
        module = record.name
        message = record.getMessage()

        base = f"{timestamp} | {level} | {module} | {message}"

        if record.exc_info and record.exc_info[0] is not None:
            base += "\n" + self.formatException(record.exc_info)

        return base


def setup_logging(log_level: str = "INFO") -> None:
    """Configure application-wide logging."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates on reload
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler with structured format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(CloudTabFormatter())
    root_logger.addHandler(console_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("paramiko").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Ensure our app loggers propagate at the desired level
    logging.getLogger("app").setLevel(getattr(logging, log_level.upper(), logging.INFO))
