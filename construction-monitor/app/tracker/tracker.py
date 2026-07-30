"""
ByteTrack wrapper using the supervision library.

One CameraTracker instance per camera.

Features:
- Wraps supervision.ByteTracker for stable pip install on Python 3.10
- Assigns persistent track IDs to detected persons
- Track lifecycle: alerts only on FIRST detection, suppressed until track is lost
- Periodic cleanup of expired track entries (prevents memory leak)
- Thread-safe via lock
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.core.config import settings
from app.core.logging_config import get_logger
from app.detector.engine import Detection

logger = get_logger(__name__, "detection")


@dataclass
class TrackState:
    """Lifecycle state for one tracked person."""
    track_id: int
    first_seen_at: float = field(default_factory=time.monotonic)
    last_seen_at: float = field(default_factory=time.monotonic)
    active: bool = True


class CameraTracker:
    """
    Per-camera ByteTracker using supervision.

    Track lifecycle strategy:
    - When a track first appears → allow alert
    - While track is ACTIVE → cooldown suppresses repeat alerts
    - When track DISAPPEARS → mark inactive, clear cooldown
    - When same person RE-ENTERS → new track ID → new alert allowed

    This means: person walks in without helmet → ONE alert.
    Person exits, re-enters → new alert (because new track ID).
    """

    def __init__(self, camera_id: int) -> None:
        self.camera_id = camera_id
        self._tracker = None
        self._lock = threading.Lock()
        self._track_states: Dict[int, TrackState] = {}
        self._last_cleanup = time.monotonic()
        self._init_tracker()

    def _init_tracker(self) -> None:
        """Initialize supervision ByteTracker."""
        try:
            import supervision as sv
            self._tracker = sv.ByteTracker(
                track_activation_threshold=0.25,
                lost_track_buffer=30,
                minimum_matching_threshold=0.8,
                frame_rate=settings.DETECTION_FPS,
            )
            logger.info("ByteTracker initialized for camera %d", self.camera_id)
        except Exception as e:
            logger.error("Failed to init ByteTracker for camera %d: %s", self.camera_id, e)
            self._tracker = None

    def update(
        self,
        persons: List[Detection],
        frame_shape: Tuple[int, int],
    ) -> List[Detection]:
        """
        Update tracker with new person detections.

        Args:
            persons: List of person detections from DetectionEngine
            frame_shape: (height, width) of the frame

        Returns:
            Updated persons list with track_id assigned.
            Persons without a track ID are dropped.
        """
        if not persons or self._tracker is None:
            self._maybe_cleanup()
            return []

        try:
            import supervision as sv
        except ImportError:
            return persons  # fallback: return without tracking

        # Build supervision Detections object
        xyxy = np.array([[p.bbox.x1, p.bbox.y1, p.bbox.x2, p.bbox.y2] for p in persons])
        confidence = np.array([p.confidence for p in persons])
        class_id = np.zeros(len(persons), dtype=int)  # all persons = class 0

        sv_detections = sv.Detections(
            xyxy=xyxy,
            confidence=confidence,
            class_id=class_id,
        )

        with self._lock:
            try:
                tracked = self._tracker.update_with_detections(sv_detections)
            except Exception as e:
                logger.warning("ByteTracker update failed for camera %d: %s", self.camera_id, e)
                return []

            # Update track states
            active_ids = set()
            result: List[Detection] = []

            if tracked.tracker_id is not None:
                for i, tid in enumerate(tracked.tracker_id):
                    tid = int(tid)
                    active_ids.add(tid)

                    if tid not in self._track_states:
                        self._track_states[tid] = TrackState(track_id=tid)
                    else:
                        self._track_states[tid].last_seen_at = time.monotonic()
                        self._track_states[tid].active = True

                    # Match back to original detection
                    # Find closest person by bbox overlap
                    if i < len(persons):
                        det = Detection(
                            class_name=persons[min(i, len(persons) - 1)].class_name,
                            confidence=float(tracked.confidence[i]) if tracked.confidence is not None else persons[i].confidence,
                            bbox=persons[min(i, len(persons) - 1)].bbox,
                            track_id=tid,
                        )
                        result.append(det)

            # Mark tracks not seen this frame as inactive
            for tid, state in self._track_states.items():
                if tid not in active_ids:
                    state.active = False

        self._maybe_cleanup()
        return result

    def is_track_new(self, track_id: int) -> bool:
        """
        Return True if this track_id was just created (first detection).
        Used by violation service to determine if alert should fire.
        """
        state = self._track_states.get(track_id)
        if state is None:
            return True
        elapsed = time.monotonic() - state.first_seen_at
        return elapsed < (1.0 / settings.DETECTION_FPS + 0.1)  # within first frame window

    def _maybe_cleanup(self) -> None:
        """Periodically remove expired track entries to prevent memory leak."""
        now = time.monotonic()
        if now - self._last_cleanup < settings.TRACK_CLEANUP_INTERVAL_SECONDS:
            return

        expiry = settings.TRACK_EXPIRY_SECONDS
        with self._lock:
            expired = [
                tid for tid, state in self._track_states.items()
                if not state.active and (now - state.last_seen_at) > expiry
            ]
            for tid in expired:
                del self._track_states[tid]

        if expired:
            logger.debug(
                "Camera %d: cleaned up %d expired track entries",
                self.camera_id,
                len(expired),
            )
        self._last_cleanup = now

    def get_active_track_count(self) -> int:
        """Return number of currently active tracks."""
        return sum(1 for s in self._track_states.values() if s.active)
