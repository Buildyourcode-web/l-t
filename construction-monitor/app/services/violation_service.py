"""
Violation Service — alert deduplication with track lifecycle + cooldown.

Algorithm:
    1. Track Lifecycle (primary): Alert fires once per track entry.
       When ByteTrack assigns a new track ID to a person → new alert is allowed.
       When the track disappears and re-appears → new track ID → new alert.
    2. Cooldown (secondary): For same track still visible > ALERT_COOLDOWN_SECONDS,
       suppress repeat alerts (e.g., person standing still for 5 minutes).
    3. Fire detection: Bypasses tracking entirely.
       Uses per-camera cooldown based on region similarity.

Memory:
    - Cooldown map: {(camera_id, track_id, violation_type) -> last_alert_time}
    - Alerted tracks: {(camera_id, track_id) -> set of alerted violation types}
    - Both maps cleaned every TRACK_CLEANUP_INTERVAL_SECONDS
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, Optional, Set, Tuple

from app.core.config import settings
from app.core.logging_config import get_logger
from app.detector.engine import FireResult, ViolationResult

logger = get_logger(__name__, "detection")

# Type aliases
CooldownKey = Tuple[int, str, str]  # (camera_id, track_id, violation_type)
AlertedKey = Tuple[int, str]         # (camera_id, track_id)


@dataclass
class AlertEvent:
    """Represents a new alert that should be processed."""
    camera_id: int
    camera_name: str
    track_id: str
    violation_type: str
    confidence: float
    frame_ref: object  # numpy frame (weakref not used — we copy before saving)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_fire: bool = False


class ViolationService:
    """
    Per-application singleton that decides whether to emit an alert.

    Thread-safe: uses a threading lock for in-memory maps.
    Async-safe: alert_handler is an async coroutine called via asyncio.
    """

    def __init__(self) -> None:
        # Cooldown: (camera_id, track_id, violation_type) → monotonic time of last alert
        self._cooldown_map: Dict[CooldownKey, float] = {}
        # Track lifecycle: (camera_id, track_id) → set of violation types already alerted
        self._alerted_tracks: Dict[AlertedKey, Set[str]] = {}
        # Fire cooldown per camera (fire has no track ID)
        self._fire_cooldown: Dict[int, float] = {}  # camera_id → last fire alert time

        self._last_cleanup = time.monotonic()
        self._lock = asyncio.Lock()  # asyncio lock since we call from async context

    async def evaluate_ppe_violation(
        self,
        *,
        camera_id: int,
        camera_name: str,
        violation: ViolationResult,
        alert_handler: Callable,
    ) -> None:
        """
        Evaluate a person-centric PPE violation.

        Fires alert_handler for each new violation type on this track.
        Suppresses duplicates based on track lifecycle + cooldown.

        Args:
            camera_id: ID of the source camera
            camera_name: Name of the source camera
            violation: ViolationResult from DetectionEngine
            alert_handler: async callable(camera_id, camera_name, track_id, violation_type, confidence)
        """
        if violation.track_id is None:
            return

        track_id_str = str(violation.track_id)
        alerted_key: AlertedKey = (camera_id, track_id_str)
        now = time.monotonic()

        await self._maybe_cleanup()

        async with self._lock:
            alerted_types = self._alerted_tracks.setdefault(alerted_key, set())

            for vtype in violation.violations:
                cooldown_key: CooldownKey = (camera_id, track_id_str, vtype)

                # Check track lifecycle: already alerted for this violation on this track?
                if vtype in alerted_types:
                    # Still within cooldown? Suppress.
                    last_alert = self._cooldown_map.get(cooldown_key, 0)
                    if (now - last_alert) < settings.ALERT_COOLDOWN_SECONDS:
                        continue
                    # Cooldown expired: allow re-alert (person standing still for long time)

                # New alert!
                alerted_types.add(vtype)
                self._cooldown_map[cooldown_key] = now

                # Call handler outside lock to avoid deadlock
                try:
                    await alert_handler(
                        camera_id=camera_id,
                        camera_name=camera_name,
                        track_id=track_id_str,
                        violation_type=vtype,
                        confidence=violation.confidence,
                    )
                except Exception as e:
                    logger.error("Alert handler error: %s", e)

    async def evaluate_fire(
        self,
        *,
        camera_id: int,
        camera_name: str,
        fire: FireResult,
        alert_handler: Callable,
    ) -> None:
        """
        Evaluate a fire detection.

        Fire bypasses tracking — immediately alerts with per-camera cooldown.
        High-priority alert.

        Args:
            camera_id: Source camera ID
            camera_name: Source camera name
            fire: FireResult from DetectionEngine
            alert_handler: async callable
        """
        now = time.monotonic()

        async with self._lock:
            last_fire = self._fire_cooldown.get(camera_id, 0)
            if (now - last_fire) < settings.ALERT_COOLDOWN_SECONDS:
                return  # suppress duplicate fire alert

            self._fire_cooldown[camera_id] = now

        try:
            await alert_handler(
                camera_id=camera_id,
                camera_name=camera_name,
                track_id="FIRE",
                violation_type="fire",
                confidence=fire.confidence,
            )
        except Exception as e:
            logger.error("Fire alert handler error: %s", e)

    def clear_track(
        self, camera_id: int, track_id: int
    ) -> None:
        """
        Clear alert state for a track that has disappeared.
        Called by tracker when a track_id is no longer seen.
        Allows fresh alerts if the person re-enters.
        """
        track_id_str = str(track_id)
        alerted_key: AlertedKey = (camera_id, track_id_str)

        # Remove from alerted tracks (allow re-entry alert)
        self._alerted_tracks.pop(alerted_key, None)

        # Remove cooldown entries for this track
        keys_to_remove = [
            k for k in self._cooldown_map if k[0] == camera_id and k[1] == track_id_str
        ]
        for k in keys_to_remove:
            del self._cooldown_map[k]

    async def _maybe_cleanup(self) -> None:
        """Periodically purge expired entries to prevent memory leak."""
        now = time.monotonic()
        if now - self._last_cleanup < settings.TRACK_CLEANUP_INTERVAL_SECONDS:
            return

        cutoff = now - settings.TRACK_EXPIRY_SECONDS

        async with self._lock:
            # Remove cooldown entries older than TRACK_EXPIRY_SECONDS
            expired_keys = [
                k for k, ts in self._cooldown_map.items() if ts < cutoff
            ]
            for k in expired_keys:
                del self._cooldown_map[k]

            # Remove alerted tracks whose cooldown entries are all gone
            all_tracked = set((k[0], k[1]) for k in self._cooldown_map)
            orphaned = [
                ak for ak in self._alerted_tracks if ak not in all_tracked
            ]
            for ak in orphaned:
                del self._alerted_tracks[ak]

        logger.debug(
            "ViolationService cleanup: removed %d cooldown entries, %d track entries",
            len(expired_keys),
            len(orphaned),
        )
        self._last_cleanup = now


# Module-level singleton
violation_service = ViolationService()
