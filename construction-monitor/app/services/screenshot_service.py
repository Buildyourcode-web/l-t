"""
Screenshot service — saves violation frames to disk.

Storage structure:
    screenshots/
        {YYYY-MM-DD}/
            {camera_name}/
                {violation_type}/
                    {HH-MM-SS-mmm}.jpg

Features:
- JPEG compression at configurable quality (default 85)
- Automatic directory creation
- Returns relative path (for DB storage)
- Safe filename generation (no special chars)
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__, "detection")


def _safe_name(name: str) -> str:
    """Replace non-alphanumeric chars with underscore for filesystem safety."""
    return re.sub(r"[^\w]", "_", name).strip("_")


def save_screenshot(
    frame: np.ndarray,
    camera_name: str,
    violation_type: str,
    timestamp: Optional[datetime] = None,
) -> Optional[str]:
    """
    Save a violation frame as a JPEG screenshot.

    Args:
        frame: BGR numpy array from OpenCV
        camera_name: Human-readable camera name
        violation_type: e.g. "no_helmet", "no_vest", "fire"
        timestamp: Violation timestamp (defaults to now UTC)

    Returns:
        Relative path to saved image (from project root), or None on error.
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    date_str = timestamp.strftime("%Y-%m-%d")
    time_str = timestamp.strftime("%H-%M-%S-%f")[:15]  # HH-MM-SS-mmm

    safe_cam = _safe_name(camera_name)
    safe_type = _safe_name(violation_type)

    # Build directory path
    output_dir = (
        Path(settings.SCREENSHOT_DIR)
        / date_str
        / safe_cam
        / safe_type
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{time_str}.jpg"
    file_path = output_dir / filename

    try:
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, settings.SCREENSHOT_QUALITY]
        success, buf = cv2.imencode(".jpg", frame, encode_params)
        if not success:
            logger.error("Failed to encode screenshot for %s/%s", camera_name, violation_type)
            return None

        file_path.write_bytes(buf.tobytes())

        # Return relative path from project root
        rel_path = str(file_path.relative_to(Path(settings.SCREENSHOT_DIR).parent))
        return rel_path

    except Exception as exc:
        logger.error(
            "Failed to save screenshot for %s/%s: %s",
            camera_name,
            violation_type,
            exc,
        )
        return None
