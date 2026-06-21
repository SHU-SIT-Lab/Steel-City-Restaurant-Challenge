"""Order verification helpers for the restaurant vision pipeline.

Resolves Firestore menu ids (menu_one, Menu Two, etc.) to vision labels and
compares them against camera detections.
"""

from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
DATABASE_DIR = REPO_ROOT / "scripts" / "database"
if str(DATABASE_DIR) not in sys.path:
    sys.path.insert(0, str(DATABASE_DIR))

from menu_catalog import (  # noqa: E402
    MENU_BY_ID,
    MenuDocument,
    resolve_order_items_to_vision_counts,
)

# Single-item aliases for raw vision labels.
ITEM_ALIASES: dict[str, str] = {
    "sandwich": "sandwich",
    "slice of pie": "slice_of_pie",
    "slice_of_pie": "slice_of_pie",
    "pie": "slice_of_pie",
    "hot dog": "hot_dog",
    "hot_dog": "hot_dog",
    "crisps": "crisps",
    "potato chips": "crisps",
    "chips": "crisps",
    "chocolate chip cookie": "chocolate_chip_cookie",
    "chocolate_chip_cookie": "chocolate_chip_cookie",
    "cookie": "chocolate_chip_cookie",
    "waffle": "waffle",
    "bacon": "bacon",
    "crab": "crab",
    "lemon": "lemon",
    "slice of pizza": "slice_of_pizza",
    "slice_of_pizza": "slice_of_pizza",
    "pizza": "slice_of_pizza",
    "prawn": "prawn",
    "shrimp": "prawn",
    "tomato ketchup bottle": "tomato_ketchup_bottle",
    "tomato_ketchup_bottle": "tomato_ketchup_bottle",
    "ketchup": "tomato_ketchup_bottle",
    "yellow mustard bottle": "yellow_mustard_bottle",
    "yellow_mustard_bottle": "yellow_mustard_bottle",
    "mustard": "yellow_mustard_bottle",
}

DISPLAY_NAMES: dict[str, str] = {
    "slice_of_pizza": "slice of pizza",
    "slice_of_pie": "slice of pie",
    "chocolate_chip_cookie": "chocolate chip cookie",
    "tomato_ketchup_bottle": "tomato ketchup bottle",
    "yellow_mustard_bottle": "yellow mustard bottle",
    "hot_dog": "hot dog",
}


def display_label_name(label: str) -> str:
    normalized = normalize_item_name(label)
    return DISPLAY_NAMES.get(normalized, normalized.replace("_", " "))


def normalize_item_name(name: str) -> str:
    """Map free-text or YOLO labels to canonical detector item ids."""
    key = str(name).strip().lower()
    if key in ITEM_ALIASES:
        return ITEM_ALIASES[key]
    return key.replace(" ", "_")


def normalize_detected_counts(
    detected: Mapping[str, int] | Counter[str],
) -> Counter[str]:
    """Normalize keys from vision output into canonical item ids."""
    normalized: Counter[str] = Counter()
    for label, count in detected.items():
        if count <= 0:
            continue
        normalized[normalize_item_name(label)] += int(count)
    return normalized


def order_items_to_required_counts(
    order_items: list[str],
    menus: dict[str, MenuDocument] | None = None,
) -> Counter[str]:
    """Expand stored menu ids into required vision item counts."""
    return resolve_order_items_to_vision_counts(
        order_items,
        menus=menus or MENU_BY_ID,
    )


@dataclass
class OrderVerificationResult:
    is_correct: bool
    required: Counter[str] = field(default_factory=Counter)
    detected: Counter[str] = field(default_factory=Counter)
    missing: Counter[str] = field(default_factory=Counter)
    extra: Counter[str] = field(default_factory=Counter)
    order_menus: list[str] = field(default_factory=list)


def verify_order(
    order_items: list[str],
    detected_counts: Mapping[str, int] | Counter[str],
    menus: dict[str, MenuDocument] | None = None,
) -> OrderVerificationResult:
    """Compare expected menu order with vision detections."""
    required = order_items_to_required_counts(order_items, menus=menus)
    detected = normalize_detected_counts(detected_counts)

    missing: Counter[str] = Counter()
    extra: Counter[str] = Counter()

    all_labels = set(required.keys()) | set(detected.keys())
    for label in all_labels:
        need = required.get(label, 0)
        have = detected.get(label, 0)
        if have < need:
            missing[label] = need - have
        elif have > need:
            extra[label] = have - need

    return OrderVerificationResult(
        is_correct=not missing and not extra,
        required=required,
        detected=detected,
        missing=missing,
        extra=extra,
        order_menus=list(order_items),
    )


def format_verification_speech(result: OrderVerificationResult) -> str:
    """Build a short spoken message for the robot."""
    if result.is_correct:
        if result.order_menus:
            menu_names = ", ".join(
                MENU_BY_ID[menu_id].name
                for menu_id in result.order_menus
                if menu_id in MENU_BY_ID
            )
            if menu_names:
                return (
                    f"{menu_names} looks correct. "
                    "I will deliver it to the table now."
                )
        return "The order looks correct. I will deliver it to the table now."

    parts: list[str] = []
    if result.missing:
        missing_text = ", ".join(
            f"{display_label_name(label)} times {count}"
            for label, count in sorted(result.missing.items())
        )
        parts.append(f"This order is missing {missing_text}")

    if result.extra:
        extra_text = ", ".join(
            f"{display_label_name(label)} times {count}"
            for label, count in sorted(result.extra.items())
        )
        parts.append(f"There are extra items: {extra_text}")

    parts.append("Please fix the order before I deliver it.")
    return ". ".join(parts)
