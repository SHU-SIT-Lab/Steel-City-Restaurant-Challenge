"""Restaurant vision: YOLO-World detection with CLIP few-shot refinement.

Trained reference images live under:
  data/restaurant_few_shot-20260621T091110Z-3-001/restaurant_few_shot
"""

from __future__ import annotations

import os
from collections import Counter
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

from order_verification import DISPLAY_NAMES, normalize_item_name

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FEW_SHOT_DIR = (
    REPO_ROOT
    / "data"
    / "restaurant_few_shot-20260621T091110Z-3-001"
    / "restaurant_few_shot"
)

FEW_SHOT_LABELS = {
    "sandwich": "sandwich",
    "slice_of_pie": "slice of pie",
    "hot_dog": "hot dog",
    "crisps": "crisps",
    "chocolate_chip_cookie": "chocolate chip cookie",
    "waffle": "waffle",
    "bacon": "bacon",
    "crab": "crab",
    "lemon": "lemon",
    "slice_of_pizza": "slice of pizza",
    "prawn": "prawn",
    "tomato_ketchup_bottle": "tomato ketchup bottle",
    "yellow_mustard_bottle": "yellow mustard bottle",
}

SPECIAL_CLASSES = list(FEW_SHOT_LABELS.keys())

YOLO_WORLD_CLASSES = [
    "sandwich",
    "slice of pie",
    "pie",
    "hot dog",
    "toy hot dog",
    "plastic hot dog",
    "crisps",
    "potato chips",
    "chocolate chip cookie",
    "cookie",
    "waffle",
    "bacon",
    "crab",
    "lemon",
    "slice of pizza",
    "pizza",
    "prawn",
    "shrimp",
    "tomato ketchup bottle",
    "ketchup bottle",
    "yellow mustard bottle",
    "mustard bottle",
    "bottle",
]

FEWSHOT_THRESHOLD = 0.78
FEWSHOT_MARGIN = 0.05
DETECTION_FRAME_SIZE = (640, 480)


def display_label_name(label: str) -> str:
    normalized = normalize_item_name(label)
    return DISPLAY_NAMES.get(normalized, normalized.replace("_", " "))


def box_area(box: list[int] | tuple[int, ...]) -> float:
    x1, y1, x2, y2 = box
    return max(0, x2 - x1) * max(0, y2 - y1)


def box_area_ratio(box: list[int] | tuple[int, ...], frame: np.ndarray) -> float:
    return box_area(box) / (frame.shape[0] * frame.shape[1])


def compute_iou(box1: list[int], box2: list[int]) -> float:
    x1a, y1a, x2a, y2a = box1
    x1b, y1b, x2b, y2b = box2

    inter_x1 = max(x1a, x1b)
    inter_y1 = max(y1a, y1b)
    inter_x2 = min(x2a, x2b)
    inter_y2 = min(y2a, y2b)

    inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
    union = max(1, box_area(box1)) + max(1, box_area(box2)) - inter_area
    return inter_area / union


def inside_ratio(inner_box: list[int], outer_box: list[int]) -> float:
    x1a, y1a, x2a, y2a = inner_box
    x1b, y1b, x2b, y2b = outer_box

    inter_x1 = max(x1a, x1b)
    inter_y1 = max(y1a, y1b)
    inter_x2 = min(x2a, x2b)
    inter_y2 = min(y2a, y2b)

    inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
    return inter_area / max(1, box_area(inner_box))


def clean_person_boxes(
    raw_people: list[dict[str, Any]],
    frame_shape: tuple[int, ...],
    iou_threshold: float = 0.25,
    inside_threshold: float = 0.50,
) -> list[dict[str, Any]]:
    h, w = frame_shape[:2]
    frame_area = h * w
    candidates: list[dict[str, Any]] = []

    for det in raw_people:
        box = det["box"]
        conf = det["confidence"]
        area_ratio = box_area(box) / frame_area
        _x1, y1, _x2, y2 = box
        height = y2 - y1

        if conf < 0.25:
            continue
        if area_ratio < 0.01:
            continue
        if height < h * 0.12:
            continue
        candidates.append(det)

    candidates.sort(key=lambda item: item["confidence"], reverse=True)
    kept: list[dict[str, Any]] = []

    for det in candidates:
        duplicate = False
        for kept_det in kept:
            iou = compute_iou(det["box"], kept_det["box"])
            inside_1 = inside_ratio(det["box"], kept_det["box"])
            inside_2 = inside_ratio(kept_det["box"], det["box"])
            if (
                iou >= iou_threshold
                or inside_1 >= inside_threshold
                or inside_2 >= inside_threshold
            ):
                duplicate = True
                break
        if not duplicate:
            kept.append(det)

    return kept


def clean_duplicate_object_boxes(
    object_detections: list[dict[str, Any]],
    iou_threshold: float = 0.35,
) -> list[dict[str, Any]]:
    if not object_detections:
        return []

    def detection_score(det: dict[str, Any]) -> float:
        fewshot_score = det.get("fewshot_score")
        if fewshot_score is not None:
            return float(fewshot_score)
        return float(det["yolo_confidence"])

    detections = sorted(object_detections, key=detection_score, reverse=True)
    kept: list[dict[str, Any]] = []

    for det in detections:
        duplicate = False
        for kept_det in kept:
            same_label = det["final_label"] == kept_det["final_label"]
            iou = compute_iou(det["box"], kept_det["box"])
            inside_1 = inside_ratio(det["box"], kept_det["box"])
            inside_2 = inside_ratio(kept_det["box"], det["box"])
            if same_label and (
                iou > iou_threshold or inside_1 > 0.65 or inside_2 > 0.65
            ):
                duplicate = True
                break
        if not duplicate:
            kept.append(det)

    return kept


def crop_box_from_frame(
    frame: np.ndarray,
    box: list[int],
    padding: int = 8,
) -> Image.Image | None:
    x1, y1, x2, y2 = box
    h, w = frame.shape[:2]

    x1 = max(0, int(x1) - padding)
    y1 = max(0, int(y1) - padding)
    x2 = min(w, int(x2) + padding)
    y2 = min(h, int(y2) + padding)

    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return None

    crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    return Image.fromarray(crop_rgb)


def horizontal_overlap_ratio(box1: list[int], box2: list[int]) -> float:
    x1a, _y1a, x2a, _y2a = box1
    x1b, _y1b, x2b, _y2b = box2

    overlap = max(0, min(x2a, x2b) - max(x1a, x1b))
    smaller_width = min(x2a - x1a, x2b - x1b)
    if smaller_width <= 0:
        return 0.0
    return overlap / smaller_width


def vertical_gap_between_boxes(box1: list[int], box2: list[int]) -> float:
    _x1a, y1a, _x2a, y2a = box1
    _x1b, y1b, _x2b, y2b = box2

    if y2a < y1b:
        return y1b - y2a
    if y2b < y1a:
        return y1a - y2b
    return 0.0


def is_person_near_table(
    table_box: list[int],
    people_detections: list[dict[str, Any]],
) -> bool:
    for person in people_detections:
        person_box = person["box"]
        h_overlap = horizontal_overlap_ratio(person_box, table_box)
        v_gap = vertical_gap_between_boxes(person_box, table_box)
        _px1, _py1, _px2, py2 = person_box
        tx1, _ty1, _tx2, _ty2 = table_box

        if (
            h_overlap > 0.20
            and v_gap < 150
            and py2 > ty1 - 120
        ):
            return True
    return False


def object_center_inside_or_near_table(
    object_box: list[int],
    table_box: list[int],
    margin: int = 70,
) -> bool:
    ox1, oy1, ox2, oy2 = object_box
    tx1, ty1, tx2, ty2 = table_box
    cx = (ox1 + ox2) / 2
    cy = (oy1 + oy2) / 2
    return (
        tx1 - margin <= cx <= tx2 + margin
        and ty1 - margin <= cy <= ty2 + margin
    )


def table_has_objects(
    table_box: list[int],
    object_detections: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    objects_on_table: list[str] = []
    for obj in object_detections:
        if object_center_inside_or_near_table(obj["box"], table_box):
            objects_on_table.append(obj["final_label"])
    return len(objects_on_table) > 0, objects_on_table


class RestaurantVision:
    """Lazy-loaded YOLO + CLIP few-shot detector for competition items."""

    def __init__(self, few_shot_dir: Path | None = None) -> None:
        self.few_shot_dir = Path(
            os.environ.get("RESTAURANT_FEW_SHOT_DIR", few_shot_dir or DEFAULT_FEW_SHOT_DIR)
        )
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._people_table_model = None
        self._object_model = None
        self._clip_model = None
        self._clip_processor = None
        self._reference_embeddings: dict[str, torch.Tensor] = {}
        self._initialized = False
        self._init_error: str | None = None

    def _ensure_loaded(self) -> bool:
        if self._initialized:
            return self._init_error is None
        self._initialized = True

        try:
            from transformers import CLIPModel, CLIPProcessor
            from ultralytics import YOLO
        except ImportError as exc:
            self._init_error = f"vision dependencies missing: {exc}"
            print(f"[RESTAURANT_VISION] {self._init_error}")
            return False

        try:
            self._people_table_model = YOLO("yolov8m.pt")
            self._object_model = YOLO("yolov8s-world.pt")
            self._object_model.set_classes(YOLO_WORLD_CLASSES)

            self._clip_model = CLIPModel.from_pretrained(
                "openai/clip-vit-base-patch32"
            ).to(self.device)
            self._clip_processor = CLIPProcessor.from_pretrained(
                "openai/clip-vit-base-patch32"
            )
            self._reference_embeddings = self._build_reference_embeddings()
            print(
                "[RESTAURANT_VISION] loaded models with "
                f"{len(self._reference_embeddings)} few-shot classes."
            )
            return True
        except Exception as exc:
            self._init_error = str(exc)
            print(f"[RESTAURANT_VISION] failed to load models: {exc}")
            return False

    def _build_reference_embeddings(self) -> dict[str, torch.Tensor]:
        embeddings: dict[str, torch.Tensor] = {}
        if not self.few_shot_dir.exists():
            print(f"[RESTAURANT_VISION] few-shot folder not found: {self.few_shot_dir}")
            return embeddings

        for folder_name in FEW_SHOT_LABELS:
            folder_path = self.few_shot_dir / folder_name
            if not folder_path.is_dir():
                continue

            image_files = [
                path
                for path in folder_path.iterdir()
                if path.suffix.lower() in {".jpg", ".jpeg", ".png"}
            ]
            if not image_files:
                continue

            class_embeddings: list[torch.Tensor] = []
            for image_path in image_files:
                try:
                    image = Image.open(image_path).convert("RGB")
                    class_embeddings.append(self._clip_image_embedding(image))
                except Exception as exc:
                    print(f"[RESTAURANT_VISION] could not read {image_path}: {exc}")

            if class_embeddings:
                stacked = torch.cat(class_embeddings, dim=0)
                mean_embedding = torch.mean(stacked, dim=0, keepdim=True)
                embeddings[folder_name] = F.normalize(mean_embedding, p=2, dim=-1)

        return embeddings

    def _clip_image_embedding(self, pil_image: Image.Image) -> torch.Tensor:
        assert self._clip_model is not None
        assert self._clip_processor is not None

        inputs = self._clip_processor(images=pil_image, return_tensors="pt").to(
            self.device
        )
        with torch.no_grad():
            outputs = self._clip_model.vision_model(
                pixel_values=inputs["pixel_values"]
            )
            image_features = outputs.pooler_output
            image_features = self._clip_model.visual_projection(image_features)
        return F.normalize(image_features, p=2, dim=-1)

    def classify_crop(
        self,
        pil_image: Image.Image,
        top_k: int = 10,
    ) -> tuple[tuple[str, float] | None, list[tuple[str, float]]]:
        if not self._reference_embeddings:
            return None, []

        image_emb = self._clip_image_embedding(pil_image)
        scores: list[tuple[str, float]] = []
        for label, ref_emb in self._reference_embeddings.items():
            score = torch.matmul(image_emb, ref_emb.T).item()
            scores.append((label, score))

        scores.sort(key=lambda item: item[1], reverse=True)
        best = scores[0] if scores else None
        return best, scores[:top_k]

    def detect_frame(self, frame: np.ndarray) -> dict[str, Any]:
        """Run full restaurant detection on a BGR camera frame."""
        if not self._ensure_loaded():
            return self._empty_result(frame, error=self._init_error)

        assert self._people_table_model is not None
        assert self._object_model is not None

        resized = cv2.resize(frame, DETECTION_FRAME_SIZE)
        h, w = resized.shape[:2]

        people_table_results = self._people_table_model.predict(
            resized,
            conf=0.20,
            iou=0.45,
            imgsz=1280,
            device=self.device,
            verbose=False,
        )

        raw_people: list[dict[str, Any]] = []
        raw_tables: list[dict[str, Any]] = []

        for result in people_table_results:
            for box in result.boxes:
                cls = int(box.cls[0])
                name = self._people_table_model.names[cls]
                conf = float(box.conf[0])
                xyxy = box.xyxy[0].cpu().numpy().astype(int).tolist()

                if name == "person":
                    raw_people.append(
                        {"class": "person", "confidence": conf, "box": xyxy}
                    )
                elif name == "dining table":
                    raw_tables.append(
                        {
                            "final_label": "table",
                            "final_label_display": "table",
                            "decision_source": "YOLOv8m",
                            "yolo_label": "dining table",
                            "yolo_confidence": conf,
                            "box": xyxy,
                        }
                    )

        people_detections = clean_person_boxes(raw_people, frame_shape=resized.shape)
        table_detections = clean_duplicate_object_boxes(raw_tables, iou_threshold=0.40)

        if not table_detections:
            table_detections.append(
                {
                    "final_label": "table",
                    "final_label_display": "table",
                    "decision_source": "fallback",
                    "yolo_label": "fallback table area",
                    "yolo_confidence": 1.0,
                    "box": [
                        int(w * 0.05),
                        int(h * 0.58),
                        int(w * 0.98),
                        int(h * 0.98),
                    ],
                }
            )

        object_results = self._object_model.predict(
            resized,
            conf=0.03,
            iou=0.45,
            imgsz=1280,
            device=self.device,
            verbose=False,
        )

        raw_object_detections: list[dict[str, Any]] = []
        for result in object_results:
            for box in result.boxes:
                cls_id = int(box.cls[0])
                yolo_conf = float(box.conf[0])
                xyxy = box.xyxy[0].cpu().numpy().astype(int).tolist()
                yolo_label_raw = result.names[cls_id]
                yolo_label_norm = normalize_item_name(yolo_label_raw)

                if box_area_ratio(xyxy, resized) > 0.35:
                    continue

                crop = crop_box_from_frame(resized, xyxy)
                final_label = yolo_label_norm
                decision_source = "YOLO-World"
                fewshot_label = None
                fewshot_score = None
                fewshot_margin = None

                if crop is not None and self._reference_embeddings:
                    _best, all_scores = self.classify_crop(crop, top_k=20)
                    filtered_scores = [
                        (label, score)
                        for label, score in all_scores
                        if label in SPECIAL_CLASSES
                    ]
                    filtered_scores.sort(key=lambda item: item[1], reverse=True)

                    if filtered_scores:
                        fewshot_label, fewshot_score = filtered_scores[0]
                        if len(filtered_scores) > 1:
                            fewshot_margin = fewshot_score - filtered_scores[1][1]
                        else:
                            fewshot_margin = fewshot_score

                        if (
                            fewshot_score >= FEWSHOT_THRESHOLD
                            and fewshot_margin >= FEWSHOT_MARGIN
                        ):
                            final_label = fewshot_label
                            decision_source = "Few-shot CLIP"

                if final_label in SPECIAL_CLASSES or final_label == "bottle":
                    raw_object_detections.append(
                        {
                            "final_label": final_label,
                            "final_label_display": display_label_name(final_label),
                            "decision_source": decision_source,
                            "yolo_label": yolo_label_raw,
                            "yolo_confidence": yolo_conf,
                            "fewshot_label": fewshot_label,
                            "fewshot_score": fewshot_score,
                            "fewshot_margin": fewshot_margin,
                            "box": xyxy,
                        }
                    )

        object_detections = clean_duplicate_object_boxes(raw_object_detections)
        object_counts = Counter(obj["final_label"] for obj in object_detections)

        table_statuses: list[dict[str, Any]] = []
        occupied_tables = 0
        free_tables = 0

        for idx, table in enumerate(table_detections):
            table_box = table["box"]
            occupied_by_person = is_person_near_table(table_box, people_detections)
            occupied_by_objects, objects_on_table = table_has_objects(
                table_box, object_detections
            )
            occupied = occupied_by_person or occupied_by_objects
            if occupied:
                occupied_tables += 1
                status = "occupied"
            else:
                free_tables += 1
                status = "free"

            table_statuses.append(
                {
                    "table_id": idx + 1,
                    "status": status,
                    "occupied_by_person": occupied_by_person,
                    "occupied_by_objects": occupied_by_objects,
                    "objects_on_table": objects_on_table,
                    "box": table_box,
                }
            )

        annotated = self._annotate_frame(
            resized,
            people_detections,
            object_detections,
            table_statuses,
        )

        return {
            "frame": annotated,
            "people_count": len(people_detections),
            "table_count": len(table_detections),
            "occupied_tables": occupied_tables,
            "free_tables": free_tables,
            "object_detections": object_detections,
            "object_counts": object_counts,
            "table_statuses": table_statuses,
            "error": None,
        }

    def _annotate_frame(
        self,
        frame: np.ndarray,
        people_detections: list[dict[str, Any]],
        object_detections: list[dict[str, Any]],
        table_statuses: list[dict[str, Any]],
    ) -> np.ndarray:
        annotated = frame.copy()

        for table in table_statuses:
            x1, y1, x2, y2 = table["box"]
            color = (0, 0, 255) if table["status"] == "occupied" else (0, 255, 255)
            label = f"Table {table['table_id']}: {table['status']}"
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                annotated,
                label,
                (x1, max(y1 - 8, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
            )

        for person in people_detections:
            x1, y1, x2, y2 = person["box"]
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                annotated,
                f"person {person['confidence']:.2f}",
                (x1, max(y1 - 8, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 255, 0),
                2,
            )

        for obj in object_detections:
            x1, y1, x2, y2 = obj["box"]
            score = obj.get("fewshot_score")
            if score is None:
                score = obj["yolo_confidence"]
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (255, 0, 255), 2)
            cv2.putText(
                annotated,
                f"{obj['final_label_display']} {score:.2f}",
                (x1, max(y1 - 8, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 0, 255),
                2,
            )

        return annotated

    def _empty_result(self, frame: np.ndarray, error: str | None) -> dict[str, Any]:
        resized = cv2.resize(frame, DETECTION_FRAME_SIZE)
        return {
            "frame": resized,
            "people_count": 0,
            "table_count": 0,
            "occupied_tables": 0,
            "free_tables": 0,
            "object_detections": [],
            "object_counts": Counter(),
            "table_statuses": [],
            "error": error,
        }


_VISION_SINGLETON: RestaurantVision | None = None


def get_restaurant_vision() -> RestaurantVision:
    global _VISION_SINGLETON
    if _VISION_SINGLETON is None:
        _VISION_SINGLETON = RestaurantVision()
    return _VISION_SINGLETON
