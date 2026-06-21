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

// Resolve an order's table_id to a table doc. Webapp orders use the table doc id
// (e.g. "0"); robot orders use "t_01"-style ids. Match by id, then by numeric
// table_id / the embedded number, so robot orders still link to a table.
export function findOrderTable(tableId: string, tables: Table[]): Table | undefined {
  const direct = tables.find((table) => table.id === tableId);
  if (direct) {
    return direct;
  }
  const match = /(\d+)/.exec(tableId);
  if (match) {
    const n = String(Number(match[1]));
    return tables.find((table) => table.id === n || String(table.table_id ?? "") === n);
  }
  return undefined;
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

    if (menuItem?.components?.length) {
      return {
        item_id: item,
        name: menuItem.name,
        quantity: 1,
        notes: menuItem.components.map((component) => component.name).join(", "),
        graspable: menuItem.graspable,
      };
    }

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

  const date = new Date(seconds * 1000);
  const now = new Date();
  const sameDay =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate();
  const options: Intl.DateTimeFormatOptions = { hour: "2-digit", minute: "2-digit" };
  if (!sameDay) {
    options.month = "short";
    options.day = "numeric";
  }
  return new Intl.DateTimeFormat("en-GB", options).format(date);
}
