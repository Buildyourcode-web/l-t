"""
FastAPI Application Entry Point — Construction Site AI Monitor.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
THREAD vs ASYNCIO BOUNDARY — READ THIS FIRST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  THREADS (one per camera — mandatory for OpenCV):
  ┌───────────────────────────────────────────────┐
  │  CameraManager spawns ONE dedicated OS thread │
  │  per camera.  Never uses ThreadPoolExecutor.  │
  │                                               │
  │  Why threads?  cv2.VideoCapture.read() is a  │
  │  BLOCKING C CALL.  It cannot be awaited.     │
  │  asyncio would deadlock the event loop.       │
  │                                               │
  │  Thread1 → Camera 1 (RTSP, runs forever)     │
  │  Thread2 → Camera 2 (RTSP, runs forever)     │
  │  ...                                          │
  │  Thread25 → Camera 25 (RTSP, runs forever)   │
  │                                               │
  │  Each thread pushes frames to a shared        │
  │  thread-safe queue.Queue(maxsize=10).         │
  └───────────────────────────────────────────────┘

  ASYNCIO (for all non-blocking services):
  ┌───────────────────────────────────────────────┐
  │  asyncio event loop runs:                     │
  │  - Detection pipeline (reads queue, offloads  │
  │    CPU inference to a small thread pool via   │
  │    run_in_executor — keeps event loop free)   │
  │  - Async DB writes (asyncpg / SQLAlchemy)     │
  │  - WebSocket broadcasting                     │
  │  - APScheduler (daily reports, cleanup)       │
  │  - Health monitoring                          │
  └───────────────────────────────────────────────┘

FULL PIPELINE (bottom-up):

    Camera Manager
          │
  ┌───────┼───────────────────────────────┐
  │       │                               │
  ▼       ▼                 ▼
Thread1  Thread2   ...  Thread25
Camera1  Camera2        Camera25
  │       │                 │
  └───────┴────────┬────────┘
                   │  (thread-safe queue.Queue)
                   ▼
          Detection Pipeline (asyncio task)
                   │
         ┌─────────┘ run_in_executor (CPU)
         ▼
    DetectionEngine (YOLO — loaded ONCE, GPU warm-up done)
         │
         ▼
    CameraTracker (ByteTrack via supervision — per camera)
         │
         ▼
    ViolationService (track lifecycle + cooldown dedup)
         │
    ┌────┴──────────────┐────────────────┐
    ▼                   ▼                ▼
Async DB Save   Async Screenshot   Async WebSocket
(asyncpg)       (file I/O)         (broadcast alert)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from __future__ import annotations

import asyncio
import concurrent.futures
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.logging_config import get_logger, setup_root_logging

# Set up logging before anything else
setup_root_logging()
logger = get_logger(__name__, "api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.

    Startup order:
    1. Create runtime directories + DB tables
    2. Load AI models (singleton, GPU warm-up)
    3. Start CameraManager → spawns 1 dedicated thread per camera
    4. Start HealthService (daemon thread for metrics)
    5. Start APScheduler (async: daily reports + retention cleanup)
    6. Start Detection Pipeline (asyncio task: reads queue, runs YOLO, tracks, alerts)

    Shutdown order:
    1. Cancel detection pipeline task
    2. Signal all camera threads to stop
    3. Shutdown scheduler
    4. Stop health service
    5. Close async DB engine
    """
    logger.info("=" * 60)
    logger.info("Starting %s v%s", settings.APP_TITLE, settings.APP_VERSION)
    logger.info("=" * 60)

    # ── 1. Ensure runtime directories exist ──────────────────────────────────
    for d in [settings.SCREENSHOT_DIR, settings.REPORTS_DIR, settings.LOG_DIR]:
        Path(d).mkdir(parents=True, exist_ok=True)
    Path("models").mkdir(exist_ok=True)

    # ── 2. Initialize database tables ────────────────────────────────────────
    from app.database.session import get_engine
    from app.database.models import Base

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ready")

    # ── 3. Load AI models ONCE — both PPE and fire (singleton + GPU warm-up) ─
    from app.detector.engine import DetectionEngine

    detection_engine = DetectionEngine.get_instance()
    try:
        detection_engine.initialize()
    except Exception as e:
        logger.error("Model loading failed: %s", e)
        logger.warning("Running without AI detection — place ppe.pt and fire.pt in models/")

    # ── 4. Start CameraManager ────────────────────────────────────────────────
    #       This spawns ONE dedicated threading.Thread per camera.
    #       NOT ThreadPoolExecutor — each RTSP stream is a long-lived blocking task.
    from app.camera.manager import camera_manager
    from app.websocket.manager import ws_manager
    from app.database.session import get_session_factory
    from app.database.crud import upsert_camera_status

    # Bridge: camera watchdog (thread) → async event loop for DB + WebSocket
    # call_soon_threadsafe safely schedules an async coroutine from a thread
    async def _on_camera_status_change(cam_id: int, cam_name: str, online: bool) -> None:
        """
        Async handler for camera online/offline events.
        Called from the watchdog thread via call_soon_threadsafe.
        Updates PostgreSQL and broadcasts to WebSocket clients.
        """
        try:
            factory = get_session_factory()
            async with factory() as db:
                await upsert_camera_status(
                    db,
                    camera_id=cam_id,
                    name=cam_name,
                    online=online,
                )
                await db.commit()
        except Exception as exc:
            logger.error("DB status update error for camera %d: %s", cam_id, exc)

        try:
            await ws_manager.broadcast_camera_status(
                camera_id=cam_id,
                camera_name=cam_name,
                online=online,
            )
        except Exception as exc:
            logger.error("WS broadcast error for camera %d: %s", cam_id, exc)

    # Register the thread→asyncio bridge callback on camera manager
    loop = asyncio.get_event_loop()

    def _thread_safe_status_callback(cam_id: int, cam_name: str, online: bool) -> None:
        """
        Called from the watchdog thread.
        Schedules the async handler on the event loop without blocking the thread.
        """
        asyncio.run_coroutine_threadsafe(
            _on_camera_status_change(cam_id, cam_name, online),
            loop,
        )

    camera_manager.set_status_callback(_thread_safe_status_callback)

    try:
        camera_manager.start()
        # At this point, 25 dedicated threads are running — one per camera.
        # Each thread owns its own cv2.VideoCapture and loops forever.
        logger.info(
            "CameraManager started — %d dedicated threads spawned (one per camera)",
            camera_manager.total_cameras,
        )
    except Exception as e:
        logger.error("CameraManager start failed: %s", e)

    # ── 5. Start HealthService (daemon thread — collects CPU/GPU/RAM metrics) ─
    from app.services.health_service import health_service

    health_service.set_camera_manager(camera_manager)
    health_service.start()
    logger.info("HealthService started (daemon thread)")

    # ── 6. Start APScheduler (async — daily reports + retention cleanup) ──────
    from app.services.scheduler import create_scheduler

    scheduler = create_scheduler()
    scheduler.start()
    logger.info("APScheduler started")

    # ── 7. Start Detection Pipeline (asyncio task) ────────────────────────────
    #       Reads from the shared frame queue, runs YOLO (in executor),
    #       tracks persons (ByteTrack), evaluates violations, saves alerts.
    pipeline_task = asyncio.create_task(
        _detection_pipeline(detection_engine, camera_manager),
        name="detection-pipeline",
    )
    logger.info("Detection pipeline started (asyncio task)")

    logger.info("=" * 60)
    logger.info(
        "System READY | Cameras: %d | API: http://%s:%d",
        camera_manager.total_cameras,
        settings.API_HOST,
        settings.API_PORT,
    )
    logger.info("=" * 60)

    yield  # ← Application serves requests here

    # ── SHUTDOWN ──────────────────────────────────────────────────────────────
    logger.info("Shutting down...")

    # Cancel async pipeline first
    pipeline_task.cancel()
    try:
        await pipeline_task
    except asyncio.CancelledError:
        pass

    # Signal all 25 camera threads to stop
    camera_manager.stop()
    logger.info("Camera threads signalled to stop")

    # Stop background services
    scheduler.shutdown(wait=False)
    health_service.stop()

    # Close async DB connection pool
    from app.database.session import close_engine
    await close_engine()

    logger.info("Shutdown complete")


# ─────────────────────────────────────────────────────────────────────────────
# DETECTION PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

async def _detection_pipeline(
    detection_engine,
    camera_manager,
) -> None:
    """
    The heart of the system — runs as a single asyncio background task.

    ┌─────────────────────────────────────────────────────────────────┐
    │  BOUNDARY: Thread land → Async land                             │
    │                                                                 │
    │  Camera threads write to: queue.Queue (thread-safe)            │
    │  This coroutine reads from queue via get_nowait() (non-blocking)│
    │  Inference runs in a small ThreadPoolExecutor via               │
    │  run_in_executor — this offloads CPU/GPU work WITHOUT blocking  │
    │  the asyncio event loop.                                        │
    │                                                                 │
    │  After inference returns, all downstream operations are async:  │
    │    - ByteTrack update (pure Python, fast, stays async)         │
    │    - ViolationService cooldown check (in-memory, fast)         │
    │    - DB write (await asyncpg)                                   │
    │    - Screenshot save (via executor — file I/O)                 │
    │    - WebSocket broadcast (await)                                │
    └─────────────────────────────────────────────────────────────────┘
    """
    from app.camera.worker import FramePacket
    from app.tracker.tracker import CameraTracker
    from app.services.violation_service import violation_service
    from app.services.screenshot_service import save_screenshot
    from app.database.session import get_session_factory
    from app.database.crud import save_violation
    from app.websocket.manager import ws_manager

    # One ByteTracker instance per camera (maintained across frames)
    trackers: Dict[int, CameraTracker] = {}

    # Small thread pool for CPU/GPU-bound YOLO inference.
    # NOTE: This is NOT for camera reading (those have dedicated threads).
    #       This is solely to offload blocking model inference from the event loop.
    inference_executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=2,
        thread_name_prefix="yolo-inference",
    )

    # File I/O executor for screenshot saves (avoid blocking event loop on disk write)
    io_executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=4,
        thread_name_prefix="screenshot-io",
    )

    loop = asyncio.get_event_loop()
    factory = get_session_factory()

    async def _handle_alert(
        *,
        camera_id: int,
        camera_name: str,
        track_id: str,
        violation_type: str,
        confidence: float,
        frame,
    ) -> None:
        """
        Async alert handler — runs entirely in the asyncio event loop.

        Steps:
        1. Save screenshot (file I/O via io_executor — non-blocking)
        2. Save to PostgreSQL (await asyncpg — non-blocking)
        3. Broadcast via WebSocket (await — non-blocking)
        """
        # 1. Save screenshot (offload file I/O to avoid blocking event loop)
        image_path = None
        if frame is not None:
            try:
                image_path = await loop.run_in_executor(
                    io_executor,
                    _save_screenshot_sync,
                    frame, camera_name, violation_type,
                )
            except Exception as e:
                logger.warning("Screenshot save failed: %s", e)

        # 2. Async DB insert
        try:
            async with factory() as db:
                await save_violation(
                    db,
                    camera_id=camera_id,
                    camera_name=camera_name,
                    track_id=track_id,
                    violation_type=violation_type,
                    confidence=confidence,
                    image_path=image_path,
                )
                await db.commit()
        except Exception as e:
            logger.error("DB save failed for violation: %s", e)

        # 3. WebSocket broadcast (instant, non-blocking)
        await ws_manager.broadcast_violation(
            camera_id=camera_id,
            camera_name=camera_name,
            track_id=track_id,
            violation_type=violation_type,
            confidence=confidence,
            image_path=image_path,
            detected_at=datetime.now(timezone.utc).isoformat(),
        )

        severity = "🔥 FIRE" if violation_type == "fire" else "⚠️ VIOLATION"
        logger.info(
            "%s | cam=%d | track=%s | type=%s | conf=%.2f",
            severity, camera_id, track_id, violation_type, confidence,
        )

    logger.info("Detection pipeline running. Waiting for frames...")

    while True:
        try:
            # ── Read one frame packet from the shared queue ───────────────────
            # Non-blocking: if queue is empty, yield back to event loop briefly
            try:
                packet: FramePacket = camera_manager.frame_queue.get_nowait()
            except Exception:
                await asyncio.sleep(0.005)  # 5ms yield — tight enough for 2 FPS target
                continue

            if not detection_engine.is_initialized:
                continue

            cam_id = packet.camera_id

            # ── Run YOLO inference (offloaded to inference_executor) ──────────
            # This is CPU/GPU-bound. run_in_executor prevents blocking the event
            # loop, allowing WebSocket and API requests to continue serving.
            result = await loop.run_in_executor(
                inference_executor,
                detection_engine.process_frame,
                packet.frame,
            )

            # ── Update ByteTracker for this camera ───────────────────────────
            # CameraTracker is per-camera — maintains track state across frames.
            if cam_id not in trackers:
                trackers[cam_id] = CameraTracker(camera_id=cam_id)
            tracker = trackers[cam_id]

            tracked_persons = tracker.update(
                result.raw_persons,
                frame_shape=(packet.frame.shape[0], packet.frame.shape[1]),
            )

            # Build track_id lookup by bbox proximity
            # Match each ViolationResult (person) to the closest tracked person
            for viol in result.ppe_violations:
                # Find the tracked person whose bbox best matches this violation's person
                best_track_id = _match_violation_to_track(viol, tracked_persons)
                viol.track_id = best_track_id

                if viol.track_id is None:
                    continue  # No track ID → cannot deduplicate → skip

                # Capture frame reference for closure
                frame_ref = packet.frame

                await violation_service.evaluate_ppe_violation(
                    camera_id=cam_id,
                    camera_name=packet.camera_name,
                    violation=viol,
                    alert_handler=lambda **kw, _frame=frame_ref: _handle_alert(
                        **kw, frame=_frame
                    ),
                )

            # ── Fire detection — no tracking, immediate alert ─────────────────
            for fire in result.fire_detections:
                frame_ref = packet.frame
                await violation_service.evaluate_fire(
                    camera_id=cam_id,
                    camera_name=packet.camera_name,
                    fire=fire,
                    alert_handler=lambda **kw, _frame=frame_ref: _handle_alert(
                        **kw, frame=_frame
                    ),
                )

        except asyncio.CancelledError:
            logger.info("Detection pipeline cancelled — shutting down")
            inference_executor.shutdown(wait=False)
            io_executor.shutdown(wait=False)
            break
        except Exception as exc:
            logger.error("Detection pipeline error: %s", exc, exc_info=settings.DEBUG)
            await asyncio.sleep(0.1)


def _save_screenshot_sync(frame, camera_name: str, violation_type: str):
    """Synchronous screenshot save — called in io_executor to avoid blocking event loop."""
    from app.services.screenshot_service import save_screenshot
    return save_screenshot(frame, camera_name=camera_name, violation_type=violation_type)


def _match_violation_to_track(violation, tracked_persons) -> int | None:
    """
    Match a ViolationResult to the closest tracked person by bounding box center distance.

    Returns the track_id of the best-matching tracked person, or None if no match found.
    """
    if not tracked_persons:
        return None

    vp = violation.person_bbox
    best_dist = float("inf")
    best_id = None

    for tp in tracked_persons:
        tb = tp.bbox
        # Euclidean distance between bbox centers
        dist = ((vp.center[0] - tb.center[0]) ** 2 + (vp.center[1] - tb.center[1]) ** 2) ** 0.5
        if dist < best_dist:
            best_dist = dist
            best_id = tp.track_id

    return best_id


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI Application
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    description="AI-powered construction site safety monitoring — 25 cameras, real-time detection",
    lifespan=lifespan,
)

# CORS — allow React dev server and production frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve screenshots as static files (thumbnail access from browser)
screenshots_dir = Path(settings.SCREENSHOT_DIR)
screenshots_dir.mkdir(parents=True, exist_ok=True)
app.mount("/screenshots", StaticFiles(directory=str(screenshots_dir)), name="screenshots")

# ── API Routers ───────────────────────────────────────────────────────────────
from app.api.routes import dashboard, violations, cameras, images, health, reports  # noqa: E402

app.include_router(dashboard.router)
app.include_router(violations.router)
app.include_router(cameras.router)
app.include_router(images.router)
app.include_router(health.router)
app.include_router(reports.router)


# ── WebSocket Endpoint ────────────────────────────────────────────────────────
@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """
    Real-time alert stream.

    Clients connect here to receive instant violation notifications.
    No polling — alerts are pushed as soon as they are detected.
    Kept alive with a 30-second ping message.
    """
    from app.websocket.manager import ws_manager
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep-alive ping every 30 seconds
            await asyncio.sleep(30)
            await websocket.send_text('{"type":"ping"}')
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception:
        await ws_manager.disconnect(websocket)


# ── Health / Info ─────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "app": settings.APP_TITLE,
        "version": settings.APP_VERSION,
        "status": "running",
    }


@app.get("/api/ping")
async def ping():
    """Lightweight health check — used by Docker HEALTHCHECK."""
    return {"status": "ok"}
