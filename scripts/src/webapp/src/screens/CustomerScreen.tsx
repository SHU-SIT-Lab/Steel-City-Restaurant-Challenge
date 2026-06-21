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
  const availableTables = snapshot.tables.filter((table) => table.status !== "unavailable");

  const {
    setMenus,
    condimentItems,
    selectedMenuId,
    selectMenu,
    selectedMenu,
    condiments,
    toggleCondiment,
    selectedCondiments,
    notes,
    setNotes,
    items,
    composedNotes,
    hasSelection,
    reset,
  } = useOrderDraft(snapshot.menu);
  const [selectedTableId, setSelectedTableId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [confirmedTable, setConfirmedTable] = useState<string | null>(null);

  const selectedTable = availableTables.find((table) => table.id === selectedTableId);

  async function handlePlaceOrder() {
    if (!selectedTableId || !hasSelection || submitting) {
      return;
    }

    setSubmitting(true);
    setSubmitError(null);

    try {
      await createOrder({ table_id: selectedTableId, notes: composedNotes, items });
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
            <span className="field-label">2. Choose one set menu</span>
            <div className="customer-menu">
              {setMenus.length === 0 ? (
                <p className="empty-state">The menu is unavailable right now.</p>
              ) : (
                <div className="menu-grid menu-grid--set">
                  {setMenus.map((item) => {
                    const selected = selectedMenuId === item.id;
                    const components = (item.components ?? []).map((component) => component.name);

                    return (
                      <article
                        className={`menu-choice ${selected ? "menu-choice--selected" : ""}`}
                        key={item.id}
                      >
                        <button aria-pressed={selected} onClick={() => selectMenu(item)} type="button">
                          <strong>{item.name}</strong>
                          {components.length ? (
                            <span className="menu-choice__components">{components.join(" · ")}</span>
                          ) : null}
                          {item.description ? (
                            <span className="menu-choice__desc">{item.description}</span>
                          ) : null}
                          <span className="menu-choice__add">{selected ? "✓ Selected" : "Choose"}</span>
                        </button>
                      </article>
                    );
                  })}
                </div>
              )}

              {condimentItems.length > 0 ? (
                <div className="customer-condiments">
                  <span className="field-label">Add condiments (optional)</span>
                  <div className="condiment-row">
                    {condimentItems.map((item) => {
                      const on = Boolean(condiments[item.id]);

                      return (
                        <button
                          aria-pressed={on}
                          className={`condiment-chip ${on ? "condiment-chip--on" : ""}`}
                          key={item.id}
                          onClick={() => toggleCondiment(item)}
                          type="button"
                        >
                          {on ? "✓ " : "+ "}
                          {item.name}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ) : null}
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
                <span className="tag">{hasSelection ? "1 set menu" : "No menu"}</span>
              </div>
              <div className="customer-cart__lines">
                {!selectedMenu ? (
                  <p className="empty-state">Choose a set menu to start your order.</p>
                ) : (
                  <>
                    <div className="cart-line">
                      <span>{selectedMenu.name}</span>
                      <strong>x1</strong>
                    </div>
                    {(selectedMenu.components ?? []).length > 0 ? (
                      <p className="cart-components">
                        Includes: {(selectedMenu.components ?? []).map((c) => c.name).join(", ")}
                      </p>
                    ) : null}
                    {selectedCondiments.length > 0 ? (
                      <p className="cart-components">
                        Condiments: {selectedCondiments.map((c) => c.name).join(", ")}
                      </p>
                    ) : null}
                  </>
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
                  disabled={!selectedTableId || !hasSelection || submitting}
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
