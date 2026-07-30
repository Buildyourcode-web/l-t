"""
Logging configuration with daily rotating file handlers.
Creates logs/{YYYY-MM-DD}/{name}.log structure.
"""
from __future__ import annotations

import logging
import logging.handlers
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.core.config import settings


class DailyDirectoryHandler(logging.handlers.RotatingFileHandler):
    """
    A rotating file handler that writes to a daily subdirectory.
    Example: logs/2026-07-23/camera.log
    """

    def __init__(self, log_name: str, **kwargs):
        self.log_name = log_name
        self.base_log_dir = Path(settings.LOG_DIR)
        log_path = self._get_log_path()
        super().__init__(
            filename=str(log_path),
            maxBytes=settings.LOG_MAX_BYTES,
            backupCount=settings.LOG_BACKUP_COUNT,
            encoding="utf-8",
        )

    def _get_log_path(self) -> Path:
        today = datetime.now().strftime("%Y-%m-%d")
        daily_dir = self.base_log_dir / today
        daily_dir.mkdir(parents=True, exist_ok=True)
        return daily_dir / f"{self.log_name}.log"

    def emit(self, record: logging.LogRecord) -> None:
        """Re-check date on each emit to handle midnight rollover."""
        new_path = self._get_log_path()
        if str(new_path) != self.baseFilename:
            self.baseFilename = str(new_path)
            if self.stream:
                self.stream.close()
                self.stream = None
        super().emit(record)


def get_logger(name: str, log_file: str) -> logging.Logger:
    """
    Return a logger that writes to both console and a daily rotating file.

    Args:
        name: Logger name (usually __name__)
        log_file: Log file base name without extension (e.g. 'camera')

    Returns:
        Configured logging.Logger instance
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # already configured

    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    logger.addHandler(console_handler)

    # Daily rotating file handler
    try:
        file_handler = DailyDirectoryHandler(log_name=log_file)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)
    except Exception as exc:
        logger.warning(f"Could not create file log handler for '{log_file}': {exc}")

    logger.propagate = False
    return logger


def setup_root_logging() -> None:
    """Configure the root logger and suppress noisy third-party loggers."""
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("ultralytics").setLevel(logging.WARNING)
    logging.getLogger("supervision").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.INFO)
