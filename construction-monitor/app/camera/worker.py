"""
CameraWorker — ONE dedicated OS thread per camera.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHY DEDICATED THREADS — NOT ThreadPoolExecutor
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

cv2.VideoCapture.read() is a BLOCKING C CALL:
  - It cannot be awaited (not an asyncio coroutine)
  - Calling it on the event loop would freeze the entire server
  - asyncio.to_thread() works but is semantically wrong here

ThreadPoolExecutor is also WRONG for RTSP streams:
  - ThreadPoolExecutor is designed for SHORT tasks that complete quickly
  - A camera thread runs FOREVER (blocking in cap.read() 25x/sec)
  - Putting 25 never-ending tasks in a pool would exhaust all workers
  - Other short tasks (screenshots, health checks) could never get a thread

THE CORRECT DESIGN:
  - CameraManager creates ONE dedicated threading.Thread per camera
  - Each thread owns its cv2.VideoCapture exclusively
  - Threads run until stop_event is set (application shutdown)
  - If a thread dies unexpectedly, the watchdog restarts it

PIPELINE:
  Thread1 (Camera 1)  ─┐
  Thread2 (Camera 2)  ─┤─→ queue.Queue(maxsize=10) → Detection Pipeline
  ...                 ─┤        (shared, thread-safe)
  Thread25 (Camera 25)─┘

Bounded queue with drop-oldest policy:
  - If detection is slow and queue fills up, the oldest frame is dropped
  - Ensures real-time behavior (process latest frames, not stale ones)
  - Prevents unbounded memory growth under load

RESILIENCE:
  - Each camera is completely isolated — camera 5 dying doesn't affect cameras 1-4 or 6-25
  - Auto-reconnect with configurable delay (RTSP_RECONNECT_DELAY)
  - Watchdog marks camera OFFLINE after CAMERA_WATCHDOG_TIMEOUT seconds of silence
"""
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__, "camera")


@dataclass
class CameraConfig:
    """Configuration for a single camera."""
    id: int
    name: str
    rtsp: str


class FramePacket:
    """A frame with metadata, put into the detection queue."""
    __slots__ = ("camera_id", "camera_name", "frame", "timestamp", "frame_number")

    def __init__(
        self,
        camera_id: int,
        camera_name: str,
        frame: np.ndarray,
        timestamp: float,
        frame_number: int,
    ) -> None:
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.frame = frame
        self.timestamp = timestamp
        self.frame_number = frame_number


class CameraWorker:
    """
    One dedicated OS thread for one RTSP camera.

    Lifecycle:
        start()  → spawns threading.Thread(daemon=True)
        _run()   → connect → read loop → reconnect on failure → repeat
        stop_event.set() → thread exits cleanly

    Frame sampling:
        Reads at full camera FPS (e.g., 25fps)
        Only pushes every Nth frame to achieve DETECTION_FPS target
        N is recalculated every 5 seconds based on actual FPS

    Queue policy (industry standard for real-time video):
        queue.put_nowait()  →  if full: drop oldest, insert newest
        This ensures the detector always processes fresh frames.
    """

    def __init__(
        self,
        config: CameraConfig,
        frame_queue: queue.Queue,
        stop_event: threading.Event,
    ) -> None:
        self.config = config
        self.frame_queue = frame_queue
        self.stop_event = stop_event

        self._thread: Optional[threading.Thread] = None
        self._online: bool = False
        self._frame_count: int = 0
        self._fps_actual: float = 0.0
        self._watchdog_ts: float = 0.0  # last successful frame time
        self._lock = threading.Lock()

        # Frame skip: sample every N frames to achieve target detection FPS
        # We assume RTSP provides ~25 FPS, we want DETECTION_FPS
        self._sample_every_n: int = max(1, round(25 / max(1, settings.DETECTION_FPS)))

    def start(self) -> None:
        """Launch the reader thread."""
        self._thread = threading.Thread(
            target=self._run,
            name=f"cam-worker-{self.config.id}",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "CameraWorker started: [%d] %s (sample every %d frames)",
            self.config.id,
            self.config.name,
            self._sample_every_n,
        )

    def _run(self) -> None:
        """Main loop: connect, read frames, reconnect on failure."""
        while not self.stop_event.is_set():
            cap = self._connect()
            if cap is None:
                self._set_online(False)
                time.sleep(settings.RTSP_RECONNECT_DELAY)
                continue

            self._set_online(True)
            self._read_loop(cap)
            cap.release()

            if not self.stop_event.is_set():
                logger.warning(
                    "Camera [%d] %s disconnected. Retrying in %ds...",
                    self.config.id,
                    self.config.name,
                    settings.RTSP_RECONNECT_DELAY,
                )
                self._set_online(False)
                time.sleep(settings.RTSP_RECONNECT_DELAY)

    def _connect(self) -> Optional[cv2.VideoCapture]:
        """Attempt to open the RTSP stream."""
        try:
            logger.info(
                "Connecting to camera [%d] %s: %s",
                self.config.id,
                self.config.name,
                self.config.rtsp,
            )
            cap = cv2.VideoCapture(self.config.rtsp, cv2.CAP_FFMPEG)
            # Set buffer size to 1 to always get latest frame
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            if not cap.isOpened():
                logger.warning(
                    "Camera [%d] %s: failed to open stream",
                    self.config.id,
                    self.config.name,
                )
                return None

            logger.info(
                "Camera [%d] %s: connected successfully",
                self.config.id,
                self.config.name,
            )
            return cap

        except Exception as exc:
            logger.error(
                "Camera [%d] %s: connection error: %s",
                self.config.id,
                self.config.name,
                exc,
            )
            return None

    def _read_loop(self, cap: cv2.VideoCapture) -> None:
        """Read frames continuously until failure or stop signal."""
        local_frame_count = 0
        fps_timer_start = time.monotonic()
        fps_frame_count = 0

        while not self.stop_event.is_set():
            ret, frame = cap.read()

            if not ret or frame is None:
                logger.warning(
                    "Camera [%d] %s: read failure",
                    self.config.id,
                    self.config.name,
                )
                break

            now = time.monotonic()
            self._watchdog_ts = now
            local_frame_count += 1
            fps_frame_count += 1

            # Calculate actual FPS every 5 seconds
            if now - fps_timer_start >= 5.0:
                self._fps_actual = fps_frame_count / (now - fps_timer_start)
                fps_frame_count = 0
                fps_timer_start = now
                # Recalculate sample_every_n based on actual FPS
                self._sample_every_n = max(
                    1, round(self._fps_actual / max(1, settings.DETECTION_FPS))
                )

            # Frame skip: only process every Nth frame
            if local_frame_count % self._sample_every_n != 0:
                continue

            packet = FramePacket(
                camera_id=self.config.id,
                camera_name=self.config.name,
                frame=frame.copy(),  # copy to avoid buffer reuse issues
                timestamp=now,
                frame_number=self._frame_count,
            )
            self._frame_count += 1

            # Bounded queue: drop oldest if full (never block)
            try:
                self.frame_queue.put_nowait(packet)
            except queue.Full:
                # Drop oldest to make room for newest
                try:
                    self.frame_queue.get_nowait()
                    self.frame_queue.put_nowait(packet)
                except (queue.Empty, queue.Full):
                    pass  # Race condition: just skip this frame

    def _set_online(self, online: bool) -> None:
        with self._lock:
            self._online = online

    # ── Public accessors ──────────────────────────────────────────────────────

    @property
    def is_online(self) -> bool:
        with self._lock:
            return self._online

    @property
    def fps(self) -> float:
        return round(self._fps_actual, 2)

    @property
    def watchdog_timestamp(self) -> float:
        return self._watchdog_ts

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
