import type { LegacyOrderItem, MenuItem, NormalizedOrderItem, Table } from "../../types/firestore";

// Live Firestore table docs (robot schema) may not carry table_number, so derive
// a readable label from table_number, then table_id, then the doc id — instead of
// rendering "Table undefined". Shared by the floor plan, orders board, and
// customer ordering screen so every surface names a table the same way.
export function tableLabel(table: Table): string {
  const raw = table as { table_number?: number; table_id?: number | string };
  if (typeof raw.table_number === "number" && Number.isFinite(raw.table_number)) {
    return `Table ${raw.table_number}`;
  }
  if (raw.table_id !== undefined && raw.table_id !== null && raw.table_id !== "") {
    return `Table ${raw.table_id}`;
  }
  return `Table ${table.id}`;
}

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
