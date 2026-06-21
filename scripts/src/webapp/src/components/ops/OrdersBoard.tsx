import { useMemo, useState, type FormEvent } from "react";
import { findOrderTable, normalizeOrderItems, tableLabel } from "../../lib/firestore/converters";
import { canUpdateOrders, hasMinimumRole } from "../../lib/rbac";
import type { MenuItem, Order, OrderStatus, Role, Table } from "../../types/firestore";
import type { AdvanceOrderInput, CreateOrderInput } from "../../lib/api/client";
import { useOrderDraft } from "../../hooks/useOrderDraft";
import { Modal, OptionCard } from "../ui/Modal";

const columns: OrderStatus[] = [
  "detected",
  "draft",
  "confirmed",
  "preparing",
  "ready",
  "collecting",
  "delivering",
  "delivered",
];

// Cap cards per column so the board fits its window without scrolling; the rest
// open on demand in a per-column modal via the "+N more" control.
const MAX_VISIBLE_ORDERS = 2;
const MINIMIZED_STORAGE_KEY = "steelCity.ordersBoard.min";

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

interface OrdersBoardProps {
  role: Role;
  orders: Order[];
  tables: Table[];
  menu: MenuItem[];
  saving: boolean;
  onCreateOrder: (input: CreateOrderInput) => Promise<void>;
  onAdvanceOrder: (input: AdvanceOrderInput) => Promise<void>;
}

export function OrdersBoard({
  role,
  orders,
  tables,
  menu,
  saving,
  onCreateOrder,
  onAdvanceOrder,
}: OrdersBoardProps) {
  const [createOpen, setCreateOpen] = useState(false);
  const [selectedTableId, setSelectedTableId] = useState(tables[0]?.id ?? "");
  const [activeOrder, setActiveOrder] = useState<Order | null>(null);
  const [columnDetail, setColumnDetail] = useState<OrderStatus | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [minimized, setMinimized] = useState<boolean>(() => {
    if (typeof window === "undefined") {
      return false;
    }
    return window.localStorage.getItem(MINIMIZED_STORAGE_KEY) === "1";
  });
  const {
    setMenus,
    condimentItems,
    selectedMenuId,
    setSelectedMenuId,
    selectMenu,
    condiments,
    toggleCondiment,
    notes,
    setNotes,
    items,
    composedNotes,
    hasSelection,
    reset,
  } = useOrderDraft(menu);
  const availableTables = useMemo(
    () => tables.filter((table) => table.status !== "unavailable"),
    [tables],
  );
  const activeOrderCount = orders.filter(
    (order) => !["delivered", "cancelled", "failed"].includes(order.status),
  ).length;
  const detailOrders = columnDetail ? orders.filter((order) => order.status === columnDetail) : [];

  function toggleMinimized() {
    setMinimized((previous) => {
      const next = !previous;
      try {
        window.localStorage.setItem(MINIMIZED_STORAGE_KEY, next ? "1" : "0");
      } catch {
        /* ignore storage failures (private mode, etc.) */
      }
      return next;
    });
  }

  function openCreateOrder() {
    setSelectedTableId(availableTables[0]?.id ?? tables[0]?.id ?? "");
    reset();
    setSelectedMenuId(setMenus[0]?.id ?? null);
    setActionError(null);
    setCreateOpen(true);
  }

  async function handleCreateOrder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await onCreateOrder({ table_id: selectedTableId, notes: composedNotes, items });
      reset();
      setCreateOpen(false);
      setActionError(null);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not create the order.");
    }
  }

  async function handleOrderStatus(status?: OrderStatus) {
    if (!activeOrder) {
      return;
    }

    try {
      await onAdvanceOrder({ order_id: activeOrder.id, status });
      setActiveOrder(null);
      setActionError(null);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not update the order.");
    }
  }

  // Shared card used both inline (capped) and inside the per-column "see all" modal.
  function renderOrderCard(order: Order, status: OrderStatus) {
    const table = findOrderTable(order.table_id, tables);
    const orderItems = normalizeOrderItems(order.items, menu);
    const canAdvance = status === "ready" ? hasMinimumRole(role, "manager") : canUpdateOrders(role);

    return (
      <div className="order-card" key={order.id}>
        <strong>{table ? tableLabel(table) : order.table_id}</strong>
        <span>{orderItems.map((item) => `${item.quantity}x ${item.name}`).join(", ")}</span>
        {status !== "delivered" ? (
          <button
            disabled={!canAdvance || saving}
            onClick={() => {
              setColumnDetail(null);
              setActionError(null);
              setActiveOrder(order);
            }}
          >
            {status === "ready" ? "Request delivery" : "Advance"}
          </button>
        ) : null}
      </div>
    );
  }

  return (
    <section className={`orders-board${minimized ? " orders-board--min" : ""}`} aria-label="Orders board">
      <div className="panel__header">
        <div>
          <p className="eyebrow">Kitchen and delivery state</p>
          <h2>Orders Board</h2>
        </div>
        <div className="orders-board__actions">
          {minimized ? <span className="tag tag--live">{activeOrderCount} active</span> : null}
          <button
            className="button--ghost"
            type="button"
            aria-expanded={!minimized}
            onClick={toggleMinimized}
          >
            {minimized ? "Expand" : "Minimise"}
          </button>
          <button disabled={!canUpdateOrders(role) || saving} onClick={openCreateOrder}>Create order</button>
        </div>
      </div>

      {minimized ? null : (
        <div className="orders-columns">
          {columns.map((status) => {
            const columnOrders = orders.filter((order) => order.status === status);
            const visible = columnOrders.slice(0, MAX_VISIBLE_ORDERS);
            const hiddenCount = columnOrders.length - visible.length;

            return (
              <article className="order-column" key={status}>
                <h3>{status.replace("_", " ")}</h3>
                {visible.map((order) => renderOrderCard(order, status))}
                {hiddenCount > 0 ? (
                  <button
                    type="button"
                    className="order-column__more"
                    onClick={() => setColumnDetail(status)}
                  >
                    +{hiddenCount} more
                  </button>
                ) : null}
              </article>
            );
          })}
        </div>
      )}

      <Modal eyebrow="Order builder" onClose={() => setCreateOpen(false)} open={createOpen} title="Create Order">
        <form className="form-stack" onSubmit={handleCreateOrder}>
          <div>
            <span className="field-label">Table</span>
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
          </div>
          <div>
            <span className="field-label">Set menu</span>
            <div className="menu-grid menu-grid--set">
              {setMenus.map((item) => {
                const selected = selectedMenuId === item.id;
                const components = (item.components ?? []).map((component) => component.name);

                return (
                  <article className={`menu-choice ${selected ? "menu-choice--selected" : ""}`} key={item.id}>
                    <button aria-pressed={selected} onClick={() => selectMenu(item)} type="button">
                      <strong>{item.name}</strong>
                      {components.length ? (
                        <span className="menu-choice__components">{components.join(" · ")}</span>
                      ) : null}
                      <span className="menu-choice__add">{selected ? "✓ Selected" : "Choose"}</span>
                    </button>
                  </article>
                );
              })}
            </div>
            {condimentItems.length > 0 ? (
              <div className="customer-condiments">
                <span className="field-label">Condiments (optional)</span>
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
          <label>
            Order notes
            <textarea onChange={(event) => setNotes(event.target.value)} value={notes} />
          </label>
          {actionError ? <p className="form-error">{actionError}</p> : null}
          <div className="modal-actions">
            <button className="button button--ghost" onClick={() => setCreateOpen(false)} type="button">
              Cancel
            </button>
            <button disabled={saving || !selectedTableId || !hasSelection} type="submit">
              {saving ? "Creating…" : "Create order"}
            </button>
          </div>
        </form>
      </Modal>

      <Modal
        eyebrow="Column detail"
        onClose={() => setColumnDetail(null)}
        open={columnDetail !== null}
        title={
          columnDetail
            ? `${capitalize(columnDetail.replace("_", " "))} orders (${detailOrders.length})`
            : "Orders"
        }
      >
        {columnDetail ? (
          detailOrders.length > 0 ? (
            <div className="orders-detail-list">
              {detailOrders.map((order) => renderOrderCard(order, columnDetail))}
            </div>
          ) : (
            <p className="empty-state">No orders in this column.</p>
          )
        ) : null}
      </Modal>

      <Modal
        eyebrow="Order lifecycle"
        onClose={() => setActiveOrder(null)}
        open={Boolean(activeOrder)}
        title={activeOrder ? `Order ${activeOrder.id.slice(0, 8)}` : "Order"}
      >
        {activeOrder ? (
          <div className="form-stack">
            <p className="empty-state">
              Current status: <strong>{activeOrder.status}</strong>
            </p>
            {actionError ? <p className="form-error">{actionError}</p> : null}
            <div className="selection-grid">
              <OptionCard
                disabled={saving}
                meta="Use standard next transition"
                onClick={() => handleOrderStatus()}
                title="Advance"
              />
              <OptionCard
                disabled={saving || !hasMinimumRole(role, "manager")}
                meta="Queue delivery collection state"
                onClick={() => handleOrderStatus("collecting")}
                title="Request delivery"
              />
              <OptionCard
                disabled={saving}
                meta="Stop active order"
                onClick={() => handleOrderStatus("cancelled")}
                title="Cancel order"
              />
              <OptionCard
                disabled={saving}
                meta="Mark operational issue"
                onClick={() => handleOrderStatus("failed")}
                title="Mark failed"
              />
            </div>
          </div>
        ) : null}
      </Modal>
    </section>
  );
}
