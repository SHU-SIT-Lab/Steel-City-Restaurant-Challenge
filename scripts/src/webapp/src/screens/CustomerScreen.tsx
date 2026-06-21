import { useState } from "react";
import { createOrder } from "../lib/api/client";
import { tableLabel } from "../lib/firestore/converters";
import { useOrderDraft } from "../hooks/useOrderDraft";
import type { OpsDataState } from "../hooks/useOpsData";
import { OptionCard } from "../components/ui/Modal";

interface CustomerScreenProps {
  ops: OpsDataState;
  onSwitchView: () => void;
}

export function CustomerScreen({ ops, onSwitchView }: CustomerScreenProps) {
  const { snapshot, loading, mode } = ops;
  const menu = snapshot.menu.filter((item) => item.available !== false);
  const availableTables = snapshot.tables.filter((table) => table.status !== "unavailable");

  const { selectedItems, notes, setNotes, toggleItem, changeQuantity, items, itemCount, reset } =
    useOrderDraft(menu);
  const [selectedTableId, setSelectedTableId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [confirmedTable, setConfirmedTable] = useState<string | null>(null);

  const selectedTable = availableTables.find((table) => table.id === selectedTableId);

  async function handlePlaceOrder() {
    if (!selectedTableId || itemCount === 0 || submitting) {
      return;
    }

    setSubmitting(true);
    setSubmitError(null);

    try {
      await createOrder({ table_id: selectedTableId, notes, items });
      setConfirmedTable(selectedTable ? tableLabel(selectedTable) : selectedTableId);
      reset();
      ops.actions.refresh();
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "Could not place order");
    } finally {
      setSubmitting(false);
    }
  }

  function startNewOrder() {
    setConfirmedTable(null);
    setSubmitError(null);
  }

  return (
    <main className="customer-shell">
      <header className="customer-header">
        <div>
          <p className="eyebrow">Steel City Restaurant</p>
          <h1>Place your order</h1>
        </div>
        <div className="customer-header__status">
          {loading ? (
            <span className="tag tag--waiting">Loading menu</span>
          ) : mode === "mock" ? (
            <span
              className="tag tag--demo"
              title="Couldn't reach Firestore — demo menu. Orders are not saved."
            >
              ⚠ DEMO — not saving
            </span>
          ) : mode === "cached" ? (
            <span
              className="tag tag--cached"
              title="Showing the last menu received from Firestore while it refreshes."
            >
              ↻ Cached menu
            </span>
          ) : (
            <span className="tag tag--live">Live menu</span>
          )}
          <span className="role-pill">
            {selectedTable ? tableLabel(selectedTable) : "No table"}
          </span>
          <button className="button--ghost" onClick={onSwitchView} type="button">
            Switch view
          </button>
        </div>
      </header>

      <div className="customer-body">
        <section className="customer-main">
          <div className="customer-tables">
            <span className="field-label">1. Choose your table</span>
            {availableTables.length === 0 ? (
              <p className="empty-state">No tables are available right now.</p>
            ) : (
              <div className="selection-grid">
                {availableTables.map((table) => (
                  <OptionCard
                    key={table.id}
                    meta={table.status.replace("_", " ")}
                    onClick={() => setSelectedTableId(table.id)}
                    selected={selectedTableId === table.id}
                    title={tableLabel(table)}
                  />
                ))}
              </div>
            )}
          </div>

          <div className="customer-menu-wrap">
            <span className="field-label">2. Add items</span>
            <div className="customer-menu">
              <div className="menu-grid">
                {menu.map((item) => {
                  const quantity = selectedItems[item.id] ?? 0;

                  return (
                    <article className={`menu-choice ${quantity ? "menu-choice--selected" : ""}`} key={item.id}>
                      <button onClick={() => toggleItem(item)} type="button">
                        <strong>{item.name}</strong>
                        <span className="menu-choice__cat">{item.category}</span>
                        <span className="menu-choice__add">{quantity ? `In order · ${quantity}` : "+ Add"}</span>
                      </button>
                      {quantity ? (
                        <div className="quantity-row">
                          <button onClick={() => changeQuantity(item.id, -1)} type="button">-</button>
                          <strong>{quantity}</strong>
                          <button onClick={() => changeQuantity(item.id, 1)} type="button">+</button>
                        </div>
                      ) : null}
                    </article>
                  );
                })}
              </div>
            </div>
          </div>
        </section>

        <aside className="customer-cart">
          {confirmedTable ? (
            <div className="customer-confirm">
              <p className="eyebrow">Order placed</p>
              <h2>Thank you!</h2>
              <p>Your order for {confirmedTable} is on its way to the kitchen.</p>
              <button onClick={startNewOrder} type="button">Start new order</button>
            </div>
          ) : (
            <>
              <div className="panel__header">
                <h2>Your order</h2>
                <span className="tag">
                  {itemCount} item{itemCount === 1 ? "" : "s"}
                </span>
              </div>
              <div className="customer-cart__lines">
                {items.length === 0 ? (
                  <p className="empty-state">Add items from the menu to start your order.</p>
                ) : (
                  items.map((item) => (
                    <div className="cart-line" key={item.item_id}>
                      <span>{item.name}</span>
                      <strong>x{item.quantity}</strong>
                    </div>
                  ))
                )}
              </div>
              <div className="customer-cart__footer">
                <label>
                  Notes
                  <textarea
                    onChange={(event) => setNotes(event.target.value)}
                    placeholder="Allergies, preferences..."
                    value={notes}
                  />
                </label>
                {submitError ? <p className="top-bar__error">{submitError}</p> : null}
                <button
                  className="customer-place"
                  disabled={!selectedTableId || itemCount === 0 || submitting}
                  onClick={handlePlaceOrder}
                  type="button"
                >
                  {submitting ? "Placing..." : "Place order"}
                </button>
              </div>
            </>
          )}
        </aside>
      </div>
    </main>
  );
}
