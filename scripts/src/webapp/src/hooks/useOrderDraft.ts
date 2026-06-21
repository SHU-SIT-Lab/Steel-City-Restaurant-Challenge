import { useMemo, useState } from "react";
import type { MenuItem, NormalizedOrderItem } from "../types/firestore";

/**
 * Shared order-draft state for the set-menu model. A customer/manager picks
 * exactly **one** set menu (`category === "set_menu"`); condiments
 * (`category === "condiment"`) are optional add-ons that go into the order
 * **notes**, never into `items` — matching the robot's `save_order` contract
 * (table `order_items` stores a single menu id like `menu_two`). Used by both
 * the manager OrdersBoard create-order modal and the CustomerScreen ordering
 * flow. Table selection is left to the caller (the two screens seed it
 * differently).
 *
 * Pass the full `snapshot.menu`; the hook splits it into orderable set menus and
 * condiments and drops anything `available === false`.
 */
export function useOrderDraft(menu: MenuItem[]) {
  const [selectedMenuId, setSelectedMenuId] = useState<string | null>(null);
  const [condiments, setCondiments] = useState<Record<string, boolean>>({});
  const [notes, setNotes] = useState("");

  const setMenus = useMemo(
    () =>
      menu
        .filter((item) => item.category === "set_menu" && item.available !== false)
        .sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0)),
    [menu],
  );

  const condimentItems = useMemo(
    () =>
      menu
        .filter((item) => item.category === "condiment" && item.available !== false)
        .sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0)),
    [menu],
  );

  const selectedMenu = useMemo(
    () => setMenus.find((item) => item.id === selectedMenuId) ?? null,
    [setMenus, selectedMenuId],
  );

  // Single-select: tapping the chosen menu again clears it.
  function selectMenu(item: MenuItem) {
    setSelectedMenuId((current) => (current === item.id ? null : item.id));
  }

  function toggleCondiment(item: MenuItem) {
    setCondiments((current) => {
      const next = { ...current };

      if (next[item.id]) {
        delete next[item.id];
      } else {
        next[item.id] = true;
      }

      return next;
    });
  }

  const selectedCondiments = useMemo(
    () => condimentItems.filter((item) => condiments[item.id]),
    [condimentItems, condiments],
  );

  // The order carries exactly the one chosen set menu, in object form.
  const items = useMemo<NormalizedOrderItem[]>(
    () => (selectedMenu ? [{ item_id: selectedMenu.id, name: selectedMenu.name, quantity: 1 }] : []),
    [selectedMenu],
  );

  // Condiments live in the notes, per the DB rule (order_notes, not order_items).
  const composedNotes = useMemo(() => {
    const trimmed = notes.trim();

    if (selectedCondiments.length === 0) {
      return trimmed;
    }

    const condimentLine = `Condiments: ${selectedCondiments.map((item) => item.name).join(", ")}`;
    return trimmed ? `${trimmed} — ${condimentLine}` : condimentLine;
  }, [notes, selectedCondiments]);

  const hasSelection = selectedMenu !== null;

  function reset() {
    setSelectedMenuId(null);
    setCondiments({});
    setNotes("");
  }

  return {
    setMenus,
    condimentItems,
    selectedMenuId,
    setSelectedMenuId,
    selectedMenu,
    selectMenu,
    condiments,
    toggleCondiment,
    selectedCondiments,
    notes,
    setNotes,
    items,
    composedNotes,
    hasSelection,
    reset,
  };
}
