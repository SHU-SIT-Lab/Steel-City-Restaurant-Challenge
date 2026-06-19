"""Process camera frames for object detection in TurtleBot4."""

from typing import Dict, List, Tuple
import cv2
from ultralytics import YOLO
from helpers.retrieve_camera import CAMERA_CONFIG

# Initialize YOLO model once at module level
model = YOLO("yolov8m.pt")

# Keep detection resolution aligned with camera helper defaults.
DETECTION_TARGET_SIZE = CAMERA_CONFIG["target_size"]
DETECTION_IMGSZ = max(DETECTION_TARGET_SIZE)

# Objects to detect
OBJECTS_TO_DETECT = [
    # People
    "person",

    # Restaurant table objects
    "cup",
    "wine glass",
    "bottle",
    "fork",
    "knife",
    "spoon",
    "bowl",

    # Food items
    "banana",
    "apple",
    "sandwich",
    "orange",
    "broccoli",
    "carrot",
    "hot dog",
    "pizza",
    "donut",
    "cake",

    # Restaurant furniture/environment
    "chair",
    "dining table",
    "couch",
    "potted plant",

    # Kitchen/restaurant equipment
    "microwave",
    "oven",
    "toaster",
    "sink",
    "refrigerator",

    # Useful extra objects
    "cell phone",
    "laptop",
    "book",
    "clock",
    "vase"
]


def horizontal_overlap_ratio(box1: Tuple, box2: Tuple) -> float:
    """Calculate horizontal overlap ratio between two boxes."""
    x1a, y1a, x2a, y2a = box1
    x1b, y1b, x2b, y2b = box2

    overlap = max(0, min(x2a, x2b) - max(x1a, x1b))
    smaller_width = min(x2a - x1a, x2b - x1b)

    if smaller_width <= 0:
        return 0

    return overlap / smaller_width


def vertical_gap_between_person_and_table(person_box: Tuple, table_box: Tuple) -> float:
    """Calculate vertical gap between person and table."""
    px1, py1, px2, py2 = person_box
    tx1, ty1, tx2, ty2 = table_box

    if py2 < ty1:
        return ty1 - py2
    elif ty2 < py1:
        return py1 - ty2
    else:
        return 0


def is_table_occupied(table_box: Tuple, people_boxes: List[Tuple]) -> bool:
    """Check if a table is occupied by a person."""
    for person_box in people_boxes:
        h_overlap = horizontal_overlap_ratio(person_box, table_box)
        v_gap = vertical_gap_between_person_and_table(person_box, table_box)

        px1, py1, px2, py2 = person_box
        tx1, ty1, tx2, ty2 = table_box

        person_bottom = py2

        horizontal_condition = h_overlap > 0.20
        vertical_condition = v_gap < 120
        seated_condition = person_bottom > ty1 - 80

        if horizontal_condition and vertical_condition and seated_condition:
            return True

    return False


def box_area(box: Tuple) -> float:
    """Calculate area of bounding box."""
    x1, y1, x2, y2 = box
    return max(0, x2 - x1) * max(0, y2 - y1)


def iou(box1: Tuple, box2: Tuple) -> float:
    """
    Calculate Intersection over Union between two boxes.
    Used to remove duplicate/split person boxes.
    """
    x1a, y1a, x2a, y2a = box1
    x1b, y1b, x2b, y2b = box2

    inter_x1 = max(x1a, x1b)
    inter_y1 = max(y1a, y1b)
    inter_x2 = min(x2a, x2b)
    inter_y2 = min(y2a, y2b)

    inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)

    area1 = max(1, box_area(box1))
    area2 = max(1, box_area(box2))

    union = area1 + area2 - inter_area

    return inter_area / union


def center_distance(box1: Tuple, box2: Tuple) -> float:
    """Calculate distance between centres of two boxes."""
    x1a, y1a, x2a, y2a = box1
    x1b, y1b, x2b, y2b = box2

    c1x = (x1a + x2a) / 2
    c1y = (y1a + y2a) / 2

    c2x = (x1b + x2b) / 2
    c2y = (y1b + y2b) / 2

    return ((c1x - c2x) ** 2 + (c1y - c2y) ** 2) ** 0.5


def clean_person_boxes(
    person_detections: List[Tuple],
    frame_width: int,
    frame_height: int
) -> List[Tuple]:
    """
    Remove weak, tiny, duplicate, and split person detections.
    This is useful when YOLO detects the same close-up person as two people.
    """
    frame_area = frame_width * frame_height
    candidates = []

    for box, conf in person_detections:
        x1, y1, x2, y2 = box

        width = x2 - x1
        height = y2 - y1
        area = width * height

        # Person should have stronger confidence than small objects
        if conf < 0.35:
            continue

        # Remove small false person detections
        if area < frame_area * 0.12:
            continue

        # Remove boxes that are too short
        if height < frame_height * 0.40:
            continue

        candidates.append((box, conf, area))

    # Sort by confidence first, then area
    candidates = sorted(
        candidates,
        key=lambda item: (item[1], item[2]),
        reverse=True
    )

    final_people = []

    for box, conf, area in candidates:
        duplicate = False

        for kept_box in final_people:
            overlap_iou = iou(box, kept_box)
            dist = center_distance(box, kept_box)

            # If two person boxes overlap or are very close,
            # treat them as the same person.
            if overlap_iou > 0.15 or dist < frame_width * 0.35:
                duplicate = True
                break

        if not duplicate:
            final_people.append(box)

    return final_people


def process_frame(
    frame
) -> Tuple:
    """
    Process a camera frame for object detection.

    Args:
        frame: OpenCV image array (BGR format)

    Returns:
        Tuple containing:
        - processed_img: Annotated frame with bounding boxes
        - people_detected: Count of people detected
        - table_detected: Count of tables detected
        - occupied_table: Count of occupied tables
        - free_table: Count of free tables
        - objects_detected: Dictionary of detected object counts
    """
    # Resize to the same target used by retrieve_camera to reduce inference cost.
    frame = cv2.resize(frame, DETECTION_TARGET_SIZE, interpolation=cv2.INTER_AREA)

    # Get frame dimensions
    h, w = frame.shape[:2]

    # Run YOLO detection
    # Slightly increased confidence to reduce false person detections,
    # but still low enough for objects like cup/table
    results = model(frame, conf=0.12, iou=0.50, imgsz=DETECTION_IMGSZ, verbose=False)

    # Initialize lists for detections
    people_boxes = []
    raw_person_detections = []
    table_boxes = []

    # Person and dining table are handled separately
    selected_objects = [
        obj for obj in OBJECTS_TO_DETECT
        if obj not in ["person", "dining table", "table"]
    ]

    object_boxes = {obj: [] for obj in selected_objects}

    # Process YOLO results
    for r in results:
        for box in r.boxes:
            cls = int(box.cls[0])
            name = model.names[cls]
            conf = float(box.conf[0])

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            detected_box = (x1, y1, x2, y2)

            if name == "person":
                raw_person_detections.append((detected_box, conf))

            elif name == "dining table":
                table_boxes.append(detected_box)

            elif name in selected_objects:
                object_boxes[name].append(detected_box)

    # Clean false/duplicate people detections
    people_boxes = clean_person_boxes(
        raw_person_detections,
        frame_width=w,
        frame_height=h
    )

    # Optional fallback if YOLO misses the table
    if len(table_boxes) == 0:
        fallback_table_box = (
            int(w * 0.05),   # x1
            int(h * 0.58),   # y1
            int(w * 0.98),   # x2
            int(h * 0.98)    # y2
        )
        table_boxes.append(fallback_table_box)

    # Check occupied/free tables
    occupied_tables = 0
    free_tables = 0

    for table_box in table_boxes:
        x1, y1, x2, y2 = table_box
        occupied = is_table_occupied(table_box, people_boxes)

        if occupied:
            occupied_tables += 1
            color = (0, 0, 255)      # red
            label = "occupied table"
        else:
            free_tables += 1
            color = (0, 255, 255)    # yellow
            label = "free table"

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            frame,
            label,
            (x1, max(y1 - 5, 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2
        )

    # Draw people
    for person_box in people_boxes:
        x1, y1, x2, y2 = person_box
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            frame,
            "person",
            (x1, max(y1 - 5, 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2
        )

    # Draw selected objects
    for object_name, boxes in object_boxes.items():
        for object_box in boxes:
            x1, y1, x2, y2 = object_box
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 255), 2)
            cv2.putText(
                frame,
                object_name,
                (x1, max(y1 - 5, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 0, 255),
                2
            )

    # Create objects_detected dictionary with counts
    objects_detected: Dict[str, int] = {}
    for object_name, boxes in object_boxes.items():
        count = len(boxes)
        if count > 0:
            objects_detected[object_name] = count

    # Return results as tuple
    return (
        frame,  # processed_img
        len(people_boxes),  # people_detected
        len(table_boxes),  # table_detected
        occupied_tables,  # occupied_table
        free_tables,  # free_table
        objects_detected  # objects_detected (dict)
    )