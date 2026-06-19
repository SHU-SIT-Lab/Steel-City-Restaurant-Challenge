import type { LegacyOrderItem, MenuItem, NormalizedOrderItem } from "../../types/firestore";

export function normalizeOrderItems(
  items: LegacyOrderItem[],
  menu: MenuItem[],
): NormalizedOrderItem[] {
  return items.map((item) => {
    if (typeof item !== "string") {
      return {
        ...item,
        quantity: item.quantity ?? 1,
      };
    }

    const menuItem = menu.find((candidate) => candidate.id === item);

    return {
      item_id: item,
      name: menuItem?.name ?? item,
      quantity: 1,
      graspable: menuItem?.graspable,
    };
  });
}

export function formatFirestoreTime(seconds?: number) {
  if (!seconds) {
    return "unknown";
  }

  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(seconds * 1000));
}
