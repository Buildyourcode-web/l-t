"""
System Health Service — monitors CPU, RAM, GPU, and camera FPS.

Provides real-time metrics for the health dashboard page.
Refreshed every 5 seconds via background task.
"""
from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from app.core.logging_config import get_logger

logger = get_logger(__name__, "api")


@dataclass
class GPUInfo:
    available: bool = False
    name: str = "N/A"
    memory_used_mb: float = 0.0
    memory_total_mb: float = 0.0
    utilization_percent: float = 0.0
    temperature_c: float = 0.0


@dataclass
class SystemMetrics:
    cpu_percent: float = 0.0
    ram_used_mb: float = 0.0
    ram_total_mb: float = 0.0
    ram_percent: float = 0.0
    gpu: GPUInfo = field(default_factory=GPUInfo)
    cameras_online: int = 0
    cameras_total: int = 0
    avg_fps: float = 0.0
    updated_at: float = field(default_factory=time.monotonic)

    def to_dict(self) -> Dict:
        return {
            "cpu_percent": round(self.cpu_percent, 1),
            "ram_used_mb": round(self.ram_used_mb, 1),
            "ram_total_mb": round(self.ram_total_mb, 1),
            "ram_percent": round(self.ram_percent, 1),
            "gpu": {
                "available": self.gpu.available,
                "name": self.gpu.name,
                "memory_used_mb": round(self.gpu.memory_used_mb, 1),
                "memory_total_mb": round(self.gpu.memory_total_mb, 1),
                "utilization_percent": round(self.gpu.utilization_percent, 1),
                "temperature_c": round(self.gpu.temperature_c, 1),
            },
            "cameras_online": self.cameras_online,
            "cameras_total": self.cameras_total,
            "avg_fps": round(self.avg_fps, 2),
        }


class HealthService:
    """Collects and caches system metrics."""

    REFRESH_INTERVAL = 5  # seconds

    def __init__(self) -> None:
        self._metrics = SystemMetrics()
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._camera_manager_ref = None  # set by main.py after startup

    def set_camera_manager(self, manager) -> None:
        self._camera_manager_ref = manager

    def start(self) -> None:
        """Start background metrics collection thread."""
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._collect_loop,
            name="health-monitor",
            daemon=True,
        )
        self._thread.start()
        logger.info("HealthService started")

    def stop(self) -> None:
        self._stop.set()

    def get_metrics(self) -> Dict:
        with self._lock:
            return self._metrics.to_dict()

    def _collect_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._collect()
            except Exception as e:
                logger.warning("Health collection error: %s", e)
            time.sleep(self.REFRESH_INTERVAL)

    def _collect(self) -> None:
        metrics = SystemMetrics()

        # CPU & RAM
        try:
            import psutil
            metrics.cpu_percent = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory()
            metrics.ram_used_mb = ram.used / 1024 / 1024
            metrics.ram_total_mb = ram.total / 1024 / 1024
            metrics.ram_percent = ram.percent
        except ImportError:
            logger.warning("psutil not installed — CPU/RAM metrics unavailable")

        # GPU
        try:
            import torch
            if torch.cuda.is_available():
                gpu = GPUInfo(available=True)
                gpu.name = torch.cuda.get_device_name(0)
                mem = torch.cuda.mem_get_info(0)
                gpu.memory_total_mb = mem[1] / 1024 / 1024
                gpu.memory_used_mb = (mem[1] - mem[0]) / 1024 / 1024
                # Try pynvml for utilization
                try:
                    import pynvml
                    pynvml.nvmlInit()
                    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    gpu.utilization_percent = util.gpu
                    temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                    gpu.temperature_c = temp
                except Exception:
                    pass  # pynvml optional
                metrics.gpu = gpu
        except Exception:
            pass

        # Camera stats
        if self._camera_manager_ref is not None:
            try:
                statuses = self._camera_manager_ref.get_camera_statuses()
                metrics.cameras_total = len(statuses)
                metrics.cameras_online = sum(1 for s in statuses if s["online"])
                fps_list = [s["fps"] for s in statuses if s["online"] and s["fps"] > 0]
                metrics.avg_fps = sum(fps_list) / len(fps_list) if fps_list else 0.0
            except Exception:
                pass

        with self._lock:
            self._metrics = metrics


# Module-level singleton
health_service = HealthService()
