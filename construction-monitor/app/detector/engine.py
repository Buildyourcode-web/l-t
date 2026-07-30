"""
Detection Engine — Singleton that loads YOLO models ONCE at startup.

Design:
- PPE model: detects person, helmet, vest (and other PPE classes)
- Fire model: detects fire
- Both models loaded once, never reloaded per frame
- GPU warm-up runs one dummy inference at startup
- Person-centric PPE association:
    For each detected person, check if a helmet and vest are nearby.
    Uses bounding box overlap (IoU) AND center-point proximity.
    Violation = person detected WITHOUT associated helmet or vest.
- Thread-safe: models accessed from multiple camera threads via a lock
- Target: <300ms per processed frame
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__, "detection")


@dataclass
class BoundingBox:
    """Normalized or pixel bounding box [x1, y1, x2, y2]."""
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def center(self) -> Tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def area(self) -> float:
        return max(0, self.width) * max(0, self.height)

    def iou(self, other: "BoundingBox") -> float:
        """Intersection over Union."""
        ix1 = max(self.x1, other.x1)
        iy1 = max(self.y1, other.y1)
        ix2 = min(self.x2, other.x2)
        iy2 = min(self.y2, other.y2)
        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        union = self.area + other.area - inter
        return inter / union if union > 0 else 0.0

    def center_distance(self, other: "BoundingBox") -> float:
        """Euclidean distance between centers."""
        cx1, cy1 = self.center
        cx2, cy2 = other.center
        return ((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2) ** 0.5


@dataclass
class Detection:
    """A single detected object."""
    class_name: str
    confidence: float
    bbox: BoundingBox
    track_id: Optional[int] = None


@dataclass
class ViolationResult:
    """Result of violation analysis for one person."""
    track_id: Optional[int]
    person_bbox: BoundingBox
    violations: List[str]          # e.g. ["no_helmet", "no_vest"]
    confidence: float              # person detection confidence
    ppe_found: Dict[str, bool] = field(default_factory=dict)  # helmet->True/False


@dataclass
class FireResult:
    """A detected fire region."""
    bbox: BoundingBox
    confidence: float


@dataclass
class FrameDetectionResult:
    """Combined result from processing one frame."""
    ppe_violations: List[ViolationResult]
    fire_detections: List[FireResult]
    raw_persons: List[Detection]
    raw_ppe: List[Detection]
    inference_ms: float


class DetectionEngine:
    """
    Singleton detection engine.

    Usage:
        engine = DetectionEngine.get_instance()
        result = engine.process_frame(frame)
    """

    _instance: Optional["DetectionEngine"] = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._ppe_model = None
        self._fire_model = None
        self._model_lock = threading.Lock()
        self._initialized = False

        # Cache class indices for fast lookup
        self._ppe_class_names: List[str] = settings.ppe_class_name_list
        self._violation_classes: List[str] = settings.violation_class_list
        self._person_class: str = settings.PERSON_CLASS_NAME

    @classmethod
    def get_instance(cls) -> "DetectionEngine":
        """Thread-safe singleton accessor."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def initialize(self) -> None:
        """
        Load both models and run GPU warm-up.
        Call this ONCE at application startup.
        """
        if self._initialized:
            return

        try:
            from ultralytics import YOLO
            import torch
        except ImportError as e:
            raise RuntimeError(f"ultralytics / torch not installed: {e}") from e

        logger.info("Loading PPE model from: %s", settings.MODEL_PPE_PATH)
        self._ppe_model = YOLO(settings.MODEL_PPE_PATH)

        logger.info("Loading Fire model from: %s", settings.MODEL_FIRE_PATH)
        self._fire_model = YOLO(settings.MODEL_FIRE_PATH)

        # GPU warm-up — run one dummy inference to avoid first-frame latency
        logger.info("Running GPU warm-up inference...")
        dummy_frame = np.zeros((640, 640, 3), dtype=np.uint8)
        device = settings.MODEL_DEVICE
        try:
            self._ppe_model(
                dummy_frame,
                device=device,
                verbose=False,
                conf=settings.MODEL_CONF_THRESHOLD,
            )
            self._fire_model(
                dummy_frame,
                device=device,
                verbose=False,
                conf=settings.MODEL_CONF_THRESHOLD,
            )
            logger.info("GPU warm-up complete.")
        except Exception as e:
            logger.warning("GPU warm-up failed (may be CPU mode): %s", e)

        self._initialized = True
        logger.info(
            "DetectionEngine initialized. PPE classes: %s | Violation classes: %s",
            self._ppe_class_names,
            self._violation_classes,
        )

    def process_frame(self, frame: np.ndarray) -> FrameDetectionResult:
        """
        Run full detection pipeline on one frame.

        Pipeline:
            1. Run PPE model → get persons + PPE items
            2. Associate PPE with each person (IoU + proximity)
            3. Generate violations for persons missing required PPE
            4. Run fire model → get fire regions

        Args:
            frame: BGR numpy array from OpenCV

        Returns:
            FrameDetectionResult with violations and fire detections
        """
        if not self._initialized:
            raise RuntimeError("DetectionEngine not initialized. Call initialize() first.")

        t_start = time.perf_counter()

        with self._model_lock:
            ppe_results = self._ppe_model(
                frame,
                device=settings.MODEL_DEVICE,
                conf=settings.MODEL_CONF_THRESHOLD,
                iou=settings.MODEL_IOU_THRESHOLD,
                verbose=False,
            )
            fire_results = self._fire_model(
                frame,
                device=settings.MODEL_DEVICE,
                conf=settings.MODEL_CONF_THRESHOLD,
                iou=settings.MODEL_IOU_THRESHOLD,
                verbose=False,
            )

        # Parse PPE detections
        persons: List[Detection] = []
        ppe_items: List[Detection] = []
        self._parse_ppe_results(ppe_results, persons, ppe_items)

        # Person-centric PPE association
        violations = self._associate_ppe_with_persons(persons, ppe_items)

        # Parse fire detections
        fires = self._parse_fire_results(fire_results)

        inference_ms = (time.perf_counter() - t_start) * 1000
        if inference_ms > settings.TARGET_LATENCY_MS:
            logger.warning("Frame inference %.1fms exceeded target %dms", inference_ms, settings.TARGET_LATENCY_MS)

        return FrameDetectionResult(
            ppe_violations=violations,
            fire_detections=fires,
            raw_persons=persons,
            raw_ppe=ppe_items,
            inference_ms=inference_ms,
        )

    def _parse_ppe_results(
        self,
        results,
        persons: List[Detection],
        ppe_items: List[Detection],
    ) -> None:
        """Extract persons and PPE items from YOLO results."""
        for result in results:
            if result.boxes is None:
                continue
            boxes = result.boxes
            for i in range(len(boxes)):
                cls_id = int(boxes.cls[i].item())
                conf = float(boxes.conf[i].item())
                xyxy = boxes.xyxy[i].cpu().numpy()

                if cls_id >= len(self._ppe_class_names):
                    continue

                class_name = self._ppe_class_names[cls_id]
                bbox = BoundingBox(
                    x1=float(xyxy[0]),
                    y1=float(xyxy[1]),
                    x2=float(xyxy[2]),
                    y2=float(xyxy[3]),
                )
                det = Detection(
                    class_name=class_name,
                    confidence=conf,
                    bbox=bbox,
                )
                if class_name == self._person_class:
                    persons.append(det)
                else:
                    # Only add PPE classes we care about (extensible list)
                    ppe_items.append(det)

    def _associate_ppe_with_persons(
        self,
        persons: List[Detection],
        ppe_items: List[Detection],
    ) -> List[ViolationResult]:
        """
        Person-centric PPE association.

        Algorithm:
            For each person:
              For each required violation class (e.g., helmet, vest):
                Find all detected PPE items of that class.
                Check if any overlaps (IoU) OR is close enough (center proximity).
                If none found → violation.

        Returns list of ViolationResult only for persons WITH violations.
        """
        violations: List[ViolationResult] = []

        for person in persons:
            p_bbox = person.bbox
            person_height = p_bbox.height
            proximity_threshold = person_height * settings.PPE_ASSOCIATION_PROXIMITY_RATIO

            ppe_found: Dict[str, bool] = {}
            violation_types: List[str] = []

            for ppe_class in self._violation_classes:
                # Find all detections of this PPE class
                candidates = [d for d in ppe_items if d.class_name == ppe_class]

                found = False
                for ppe_det in candidates:
                    # Check IoU overlap
                    iou = p_bbox.iou(ppe_det.bbox)
                    if iou >= settings.PPE_ASSOCIATION_IOU_THRESHOLD:
                        found = True
                        break

                    # Check center proximity as fallback
                    dist = p_bbox.center_distance(ppe_det.bbox)
                    if dist <= proximity_threshold:
                        found = True
                        break

                ppe_found[ppe_class] = found
                if not found:
                    violation_types.append(f"no_{ppe_class}")

            if violation_types:
                violations.append(
                    ViolationResult(
                        track_id=person.track_id,
                        person_bbox=p_bbox,
                        violations=violation_types,
                        confidence=person.confidence,
                        ppe_found=ppe_found,
                    )
                )

        return violations

    def _parse_fire_results(self, results) -> List[FireResult]:
        """Extract fire detections from YOLO results."""
        fires: List[FireResult] = []
        for result in results:
            if result.boxes is None:
                continue
            boxes = result.boxes
            for i in range(len(boxes)):
                conf = float(boxes.conf[i].item())
                xyxy = boxes.xyxy[i].cpu().numpy()
                fires.append(
                    FireResult(
                        bbox=BoundingBox(
                            x1=float(xyxy[0]),
                            y1=float(xyxy[1]),
                            x2=float(xyxy[2]),
                            y2=float(xyxy[3]),
                        ),
                        confidence=conf,
                    )
                )
        return fires

    @property
    def is_initialized(self) -> bool:
        return self._initialized
