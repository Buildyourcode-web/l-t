"""
CameraManager — orchestrates all camera workers.

Responsibilities:
- Reads config/cameras.json
- Spawns one CameraWorker thread per camera
- Provides a single shared detection queue for all cameras
- Health Watchdog: periodically checks each camera's last-frame timestamp.
  If no frame received in CAMERA_WATCHDOG_TIMEOUT seconds → mark offline → alert dashboard
- Restarts dead threads automatically
- Never requires code changes to add/remove cameras (config-driven)
"""
from __future__ import annotations

import asyncio
import json
import queue
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

from app.camera.worker import CameraConfig, CameraWorker, FramePacket
from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__, "camera")


class CameraManager:
    """
    Manages all camera workers and the shared frame queue.

    Usage:
        manager = CameraManager()
        manager.start()
        # detection loop reads from manager.frame_queue
        manager.stop()
    """

    def __init__(self) -> None:
        self._workers: Dict[int, CameraWorker] = {}
        self._configs: List[CameraConfig] = []
        self._stop_event = threading.Event()

        # Single shared queue for all cameras → detection pipeline
        self.frame_queue: queue.Queue[FramePacket] = queue.Queue(
            maxsize=settings.FRAME_QUEUE_SIZE
        )

        # Optional callback for status changes (wired to WebSocket broadcast)
        self._status_callback: Optional[Callable] = None
        self._watchdog_thread: Optional[threading.Thread] = None

    def load_config(self) -> None:
        """Read cameras.json and populate camera configurations."""
        config_path = Path(settings.CAMERAS_CONFIG_PATH)
        if not config_path.exists():
            raise FileNotFoundError(f"cameras.json not found at: {config_path}")

        with config_path.open("r", encoding="utf-8") as f:
            raw = json.load(f)

        self._configs = [
            CameraConfig(
                id=cam["id"],
                name=cam["name"],
                rtsp=cam["rtsp"],
            )
            for cam in raw
        ]
        logger.info("Loaded %d camera configurations from %s", len(self._configs), config_path)

    def start(self) -> None:
        """Start all camera workers and the health watchdog."""
        self.load_config()
        self._stop_event.clear()

        for config in self._configs:
            self._spawn_worker(config)

        # Start health watchdog thread
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            name="cam-watchdog",
            daemon=True,
        )
        self._watchdog_thread.start()
        logger.info("CameraManager started with %d cameras", len(self._workers))

    def _spawn_worker(self, config: CameraConfig) -> None:
        """Create and start a CameraWorker for the given config."""
        worker = CameraWorker(
            config=config,
            frame_queue=self.frame_queue,
            stop_event=self._stop_event,
        )
        self._workers[config.id] = worker
        worker.start()

    def stop(self) -> None:
        """Signal all workers to stop."""
        logger.info("CameraManager stopping...")
        self._stop_event.set()

    def set_status_callback(self, callback: Callable) -> None:
        """
        Register a callback called when camera status changes.
        Signature: callback(camera_id, camera_name, online: bool)
        """
        self._status_callback = callback

    def _watchdog_loop(self) -> None:
        """
        Health Watchdog — runs every 5 seconds.

        For each camera:
        1. Check if worker thread is alive; restart if dead
        2. Check time since last frame received
        3. If > CAMERA_WATCHDOG_TIMEOUT → mark offline, trigger callback
        4. If back online → trigger callback
        """
        prev_online: Dict[int, bool] = {cid: False for cid in self._workers}
        CHECK_INTERVAL = 5  # seconds

        while not self._stop_event.is_set():
            time.sleep(CHECK_INTERVAL)

            now = time.monotonic()
            for cam_id, worker in self._workers.items():
                # Restart dead threads
                if not worker.is_alive:
                    logger.warning(
                        "Camera [%d] %s worker thread died. Restarting...",
                        cam_id,
                        worker.config.name,
                    )
                    self._spawn_worker(worker.config)
                    continue

                # Watchdog: check last frame timestamp
                watchdog_ts = worker.watchdog_timestamp
                if watchdog_ts == 0:
                    # Camera never connected
                    is_online = False
                else:
                    elapsed = now - watchdog_ts
                    is_online = elapsed <= settings.CAMERA_WATCHDOG_TIMEOUT

                # Trigger callback on status change
                if is_online != prev_online.get(cam_id, None):
                    prev_online[cam_id] = is_online
                    status_str = "ONLINE" if is_online else "OFFLINE"
                    logger.info(
                        "Camera [%d] %s is now %s",
                        cam_id,
                        worker.config.name,
                        status_str,
                    )
                    if self._status_callback:
                        try:
                            self._status_callback(cam_id, worker.config.name, is_online)
                        except Exception as e:
                            logger.error("Status callback error: %s", e)

    def get_camera_statuses(self) -> List[Dict]:
        """Return current status of all cameras."""
        now = time.monotonic()
        statuses = []
        for cam_id, worker in self._workers.items():
            watchdog_ts = worker.watchdog_timestamp
            if watchdog_ts == 0:
                online = False
            else:
                online = (now - watchdog_ts) <= settings.CAMERA_WATCHDOG_TIMEOUT

            statuses.append({
                "camera_id": cam_id,
                "name": worker.config.name,
                "online": online,
                "fps": worker.fps,
                "rtsp_url": worker.config.rtsp,
            })
        return sorted(statuses, key=lambda x: x["camera_id"])

    def get_online_count(self) -> int:
        now = time.monotonic()
        count = 0
        for worker in self._workers.values():
            wt = worker.watchdog_timestamp
            if wt > 0 and (now - wt) <= settings.CAMERA_WATCHDOG_TIMEOUT:
                count += 1
        return count

    @property
    def total_cameras(self) -> int:
        return len(self._workers)


# Module-level singleton
camera_manager = CameraManager()
