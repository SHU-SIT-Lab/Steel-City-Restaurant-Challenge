import { useMemo, useState } from "react";
import type { MenuItem, NormalizedOrderItem } from "../types/firestore";

/**
 * Shared order-draft state for building an order from the menu. Used by both the
 * manager OrdersBoard create-order modal and the CustomerScreen ordering flow.
 * Table selection is intentionally left to the caller (the two screens seed it
 * differently).
 */
export function useOrderDraft(menu: MenuItem[]) {
  const [selectedItems, setSelectedItems] = useState<Record<string, number>>({});
  const [notes, setNotes] = useState("");

  function toggleItem(item: MenuItem) {
    setSelectedItems((current) => {
      if ((current[item.id] ?? 0) > 0) {
        const next = { ...current };
        delete next[item.id];
        return next;
      }

      return { ...current, [item.id]: 1 };
    });
  }

  function changeQuantity(itemId: string, delta: number) {
    setSelectedItems((current) => {
      const nextQuantity = Math.max(0, Math.min(9, (current[itemId] ?? 0) + delta));
      const next = { ...current };

      if (nextQuantity === 0) {
        delete next[itemId];
      } else {
        next[itemId] = nextQuantity;
      }

      return next;
    });
  }

  const items = useMemo<NormalizedOrderItem[]>(
    () =>
      Object.entries(selectedItems).reduce<NormalizedOrderItem[]>((acc, [itemId, quantity]) => {
        const menuItem = menu.find((candidate) => candidate.id === itemId);

        if (!menuItem) {
          return acc;
        }

        acc.push({
          item_id: menuItem.id,
          name: menuItem.name,
          quantity,
          graspable: menuItem.graspable,
        });

        return acc;
      }, []),
    [selectedItems, menu],
  );

  const itemCount = useMemo(
    () => Object.values(selectedItems).reduce((total, quantity) => total + quantity, 0),
    [selectedItems],
  );

  function reset() {
    setSelectedItems({});
    setNotes("");
  }

  return {
    selectedItems,
    setSelectedItems,
    notes,
    setNotes,
    toggleItem,
    changeQuantity,
    items,
    itemCount,
    reset,
  };
}
