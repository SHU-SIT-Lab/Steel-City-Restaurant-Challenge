"""Process camera frames for object detection in TurtleBot4."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Tuple

import cv2

from helpers.retrieve_camera import CAMERA_CONFIG

REPO_ROOT = Path(__file__).resolve().parents[5]
VISION_DIR = REPO_ROOT / "scripts" / "vision"
if str(VISION_DIR) not in sys.path:
    sys.path.insert(0, str(VISION_DIR))

try:
    from restaurant_vision import get_restaurant_vision
except ImportError as exc:
    get_restaurant_vision = None  # type: ignore[assignment]
    _VISION_IMPORT_ERROR = str(exc)
else:
    _VISION_IMPORT_ERROR = None

DETECTION_TARGET_SIZE = CAMERA_CONFIG["target_size"]


def process_frame(frame) -> Tuple:
    """
    Process a camera frame for restaurant vision.

    Returns:
        Tuple of (processed_img, people_detected, table_detected,
        occupied_table, free_table, objects_detected)
    """
    if get_restaurant_vision is None:
        resized = cv2.resize(frame, DETECTION_TARGET_SIZE, interpolation=cv2.INTER_AREA)
        print(f"[VISION] restaurant vision unavailable: {_VISION_IMPORT_ERROR}")
        return resized, 0, 0, 0, 0, {}

    vision = get_restaurant_vision()
    result = vision.detect_frame(frame)

    if result.get("error"):
        print(f"[VISION] detection warning: {result['error']}")

    object_counts = result.get("object_counts", {})
    objects_detected: Dict[str, int] = dict(object_counts)

    return (
        result["frame"],
        int(result.get("people_count", 0)),
        int(result.get("table_count", 0)),
        int(result.get("occupied_tables", 0)),
        int(result.get("free_tables", 0)),
        objects_detected,
    )
