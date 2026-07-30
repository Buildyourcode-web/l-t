"""
Central configuration using Pydantic BaseSettings.
All values come from environment variables or .env file.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent.parent  # project root


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ─────────────────────────────────────────────────
    APP_TITLE: str = "Construction Site AI Monitor"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ── Database ─────────────────────────────────────────────────────
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "construction_monitor"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # ── AI Models ────────────────────────────────────────────────────
    MODEL_PPE_PATH: str = str(BASE_DIR / "models" / "ppe.pt")
    MODEL_FIRE_PATH: str = str(BASE_DIR / "models" / "fire.pt")
    MODEL_DEVICE: str = "0"  # "0" for GPU 0, "cpu" for CPU
    MODEL_CONF_THRESHOLD: float = 0.45
    MODEL_IOU_THRESHOLD: float = 0.45

    # ── PPE Violation Classes (extensible via env) ───────────────────
    # Comma-separated class names to monitor for violations
    # Boots/gloves can be enabled here without code changes
    VIOLATION_CLASSES: str = "helmet,vest"  # extend: "helmet,vest,boots,gloves"
    PPE_CLASS_NAMES: str = "boots,gloves,helmet,human,vest"  # matches data.yaml order
    PERSON_CLASS_NAME: str = "human"  # class name for person detection

    @property
    def violation_class_list(self) -> List[str]:
        return [c.strip() for c in self.VIOLATION_CLASSES.split(",")]

    @property
    def ppe_class_name_list(self) -> List[str]:
        return [c.strip() for c in self.PPE_CLASS_NAMES.split(",")]

    # ── Camera & Detection ───────────────────────────────────────────
    CAMERAS_CONFIG_PATH: str = str(BASE_DIR / "config" / "cameras.json")
    DETECTION_FPS: int = 2          # frames per second to run inference on
    FRAME_QUEUE_SIZE: int = 10      # bounded queue size per camera
    RTSP_RECONNECT_DELAY: int = 5   # seconds before reconnect attempt
    CAMERA_WATCHDOG_TIMEOUT: int = 10  # seconds of no frame = camera offline

    # ── Tracking & Alerts ────────────────────────────────────────────
    ALERT_COOLDOWN_SECONDS: int = 30
    TRACK_CLEANUP_INTERVAL_SECONDS: int = 300   # cleanup old tracks every 5 min
    TRACK_EXPIRY_SECONDS: int = 60              # tracks older than 60s are purged

    # ── Person-centric PPE Association ───────────────────────────────
    PPE_ASSOCIATION_IOU_THRESHOLD: float = 0.15  # min overlap to associate PPE with person
    PPE_ASSOCIATION_PROXIMITY_RATIO: float = 0.6  # proximity as fraction of person height

    # ── Screenshot Storage ───────────────────────────────────────────
    SCREENSHOT_DIR: str = str(BASE_DIR / "screenshots")
    SCREENSHOT_QUALITY: int = 85    # JPEG quality 0-100

    # ── Reports ──────────────────────────────────────────────────────
    REPORTS_DIR: str = str(BASE_DIR / "reports")
    REPORTS_RETENTION_DAYS: int = 90  # delete reports older than N days
    SCREENSHOTS_RETENTION_DAYS: int = 90  # delete screenshots older than N days

    # ── Logging ──────────────────────────────────────────────────────
    LOG_DIR: str = str(BASE_DIR / "logs")
    LOG_LEVEL: str = "INFO"
    LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10 MB
    LOG_BACKUP_COUNT: int = 5

    # ── API ──────────────────────────────────────────────────────────
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    # ── Performance ──────────────────────────────────────────────────
    TARGET_LATENCY_MS: int = 300  # target <300ms per processed frame


# Module-level singleton
settings = Settings()
