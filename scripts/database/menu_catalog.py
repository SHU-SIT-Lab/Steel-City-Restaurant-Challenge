"""Competition set-menu catalog (Menu One … Menu Five).

Source of truth for what each menu contains. Seeded into Firestore `menu`
collection and used by vision order verification.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any

WORD_NUMBERS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
}


@dataclass
class MenuComponent:
    item_id: str
    name: str
    quantity: int = 1
    vision_label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MenuComponent":
        return cls(
            item_id=str(data.get("item_id", "")),
            name=str(data.get("name", "")),
            quantity=int(data.get("quantity", 1)),
            vision_label=str(data.get("vision_label", data.get("item_id", ""))),
        )


@dataclass
class MenuDocument:
    id: str
    name: str
    menu_number: int
    category: str = "set_menu"
    available: bool = True
    display_order: int = 0
    description: str = ""
    components: list[MenuComponent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "menu_number": self.menu_number,
            "category": self.category,
            "available": self.available,
            "display_order": self.display_order,
            "description": self.description,
            "components": [component.to_dict() for component in self.components],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MenuDocument":
        components = [
            MenuComponent.from_dict(component)
            for component in data.get("components", [])
        ]
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            menu_number=int(data.get("menu_number", 0)),
            category=str(data.get("category", "set_menu")),
            available=bool(data.get("available", True)),
            display_order=int(data.get("display_order", 0)),
            description=str(data.get("description", "")),
            components=components,
        )

    def vision_counts(self) -> Counter[str]:
        counts: Counter[str] = Counter()
        for component in self.components:
            label = component.vision_label or component.item_id
            counts[label] += max(1, component.quantity)
        return counts


def menu_id_for_number(number: int) -> str:
    words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
    word = words.get(number)
    if word is None:
        raise ValueError(f"unsupported menu number: {number}")
    return f"menu_{word}"


def menu_display_name(number: int) -> str:
    words = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five"}
    return f"Menu {words[number]}"


COMPETITION_MENUS: list[MenuDocument] = [
    MenuDocument(
        id=menu_id_for_number(1),
        name=menu_display_name(1),
        menu_number=1,
        display_order=0,
        description="Sandwich with lettuce, served on plate; berry lattice slice of pie.",
        components=[
            MenuComponent("sandwich", "Sandwich", vision_label="sandwich"),
            MenuComponent("slice_of_pie", "Slice of Pie", vision_label="slice_of_pie"),
        ],
    ),
    MenuDocument(
        id=menu_id_for_number(2),
        name=menu_display_name(2),
        menu_number=2,
        display_order=1,
        description="Hot dog with lettuce; crisps on the side; chocolate chip cookie.",
        components=[
            MenuComponent("hot_dog", "Hot Dog", vision_label="hot_dog"),
            MenuComponent("crisps", "Crisps", vision_label="crisps"),
            MenuComponent(
                "chocolate_chip_cookie",
                "Chocolate Chip Cookie",
                vision_label="chocolate_chip_cookie",
            ),
        ],
    ),
    MenuDocument(
        id=menu_id_for_number(3),
        name=menu_display_name(3),
        menu_number=3,
        display_order=2,
        description="Waffle with bacon, served on plate.",
        components=[
            MenuComponent("waffle", "Waffle", vision_label="waffle"),
            MenuComponent("bacon", "Bacon", vision_label="bacon"),
        ],
    ),
    MenuDocument(
        id=menu_id_for_number(4),
        name=menu_display_name(4),
        menu_number=4,
        display_order=3,
        description="Crab with lemon; lattice slice of pie.",
        components=[
            MenuComponent("crab", "Crab", vision_label="crab"),
            MenuComponent("lemon", "Lemon", vision_label="lemon"),
            MenuComponent("slice_of_pie", "Slice of Pie", vision_label="slice_of_pie"),
        ],
    ),
    MenuDocument(
        id=menu_id_for_number(5),
        name=menu_display_name(5),
        menu_number=5,
        display_order=4,
        description="Slice of pizza with toppings; prawn on the side; cookie.",
        components=[
            MenuComponent("slice_of_pizza", "Slice of Pizza", vision_label="slice_of_pizza"),
            MenuComponent("prawn", "Prawn", vision_label="prawn"),
            MenuComponent(
                "chocolate_chip_cookie",
                "Cookie",
                vision_label="chocolate_chip_cookie",
            ),
        ],
    ),
]

CONDIMENT_ITEMS: list[MenuDocument] = [
    MenuDocument(
        id="tomato_ketchup",
        name="Tomato Ketchup",
        menu_number=0,
        category="condiment",
        display_order=10,
        components=[
            MenuComponent(
                "tomato_ketchup_bottle",
                "Tomato Ketchup",
                vision_label="tomato_ketchup_bottle",
            ),
        ],
    ),
    MenuDocument(
        id="yellow_mustard",
        name="Yellow Mustard",
        menu_number=0,
        category="condiment",
        display_order=11,
        components=[
            MenuComponent(
                "yellow_mustard_bottle",
                "Yellow Mustard",
                vision_label="yellow_mustard_bottle",
            ),
        ],
    ),
]

ALL_MENU_ITEMS = COMPETITION_MENUS + CONDIMENT_ITEMS
MENU_BY_ID = {menu.id: menu for menu in ALL_MENU_ITEMS}
MENU_BY_NUMBER = {menu.menu_number: menu for menu in COMPETITION_MENUS}


def normalize_menu_reference(value: str) -> str | None:
    """Map spoken or legacy menu strings to a canonical menu id."""
    raw = str(value).strip().lower()
    if not raw:
        return None

    if raw in MENU_BY_ID:
        return raw

    # menu_one, menu-one
    compact = raw.replace("-", "_").replace(" ", "_")
    if compact in MENU_BY_ID:
        return compact

    if compact.startswith("menu_"):
        suffix = compact.removeprefix("menu_")
        if suffix.isdigit():
            number = int(suffix)
            if number in MENU_BY_NUMBER:
                return menu_id_for_number(number)
        if suffix in WORD_NUMBERS:
            return menu_id_for_number(WORD_NUMBERS[suffix])

    if raw.startswith("menu"):
        remainder = raw.removeprefix("menu").strip(" _-")
        if remainder.isdigit():
            number = int(remainder)
            if number in MENU_BY_NUMBER:
                return menu_id_for_number(number)
        if remainder in WORD_NUMBERS:
            return menu_id_for_number(WORD_NUMBERS[remainder])

    return None


def resolve_order_items_to_vision_counts(
    order_items: list[str],
    menus: dict[str, MenuDocument] | None = None,
) -> Counter[str]:
    """Expand stored menu ids (e.g. menu_one) into required vision labels."""
    lookup = menus or MENU_BY_ID
    required: Counter[str] = Counter()

    for raw_item in order_items:
        item = str(raw_item).strip()
        if not item:
            continue

        menu_id = normalize_menu_reference(item)
        if menu_id and menu_id in lookup:
            required.update(lookup[menu_id].vision_counts())
            continue

        # Legacy fallback: treat as a single vision label.
        label = item.lower().replace(" ", "_")
        required[label] += 1

    return required


def list_set_menus() -> list[MenuDocument]:
    return list(COMPETITION_MENUS)


def menu_prompt_text() -> str:
    """Text for the order-taking LLM describing available menus."""
    lines = [
        "Customers must choose one set menu. Available menus:",
    ]
    for menu in COMPETITION_MENUS:
        parts = [f"{component.name}" for component in menu.components]
        lines.append(f"- {menu.name}: {', '.join(parts)}")
    lines.append(
        "Optional condiments (not included unless requested): "
        "Tomato Ketchup, Yellow Mustard."
    )
    return "\n".join(lines)
