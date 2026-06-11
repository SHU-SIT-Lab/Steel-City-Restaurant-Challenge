import { useMemo, useState, type FormEvent } from "react";
import { normalizeOrderItems } from "../../lib/firestore/converters";
import { canUpdateOrders, hasMinimumRole } from "../../lib/rbac";
import type { MenuItem, NormalizedOrderItem, Order, OrderStatus, Role, Table } from "../../types/firestore";
import type { AdvanceOrderInput, CreateOrderInput } from "../../lib/api/client";
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
  const [selectedItems, setSelectedItems] = useState<Record<string, number>>({});
  const [notes, setNotes] = useState("");
  const [activeOrder, setActiveOrder] = useState<Order | null>(null);
  const availableTables = useMemo(
    () => tables.filter((table) => table.status !== "unavailable"),
    [tables],
  );

  function openCreateOrder() {
    setSelectedTableId(availableTables[0]?.id ?? tables[0]?.id ?? "");
    setSelectedItems(menu[0] ? { [menu[0].id]: 1 } : {});
    setNotes("");
    setCreateOpen(true);
  }

  function toggleItem(item: MenuItem) {
    setSelectedItems((current) => {
      const quantity = current[item.id] ?? 0;

      if (quantity > 0) {
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

  async function handleCreateOrder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const items = Object.entries(selectedItems).reduce<NormalizedOrderItem[]>((acc, [itemId, quantity]) => {
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
      }, []);

    await onCreateOrder({
      table_id: selectedTableId,
      notes,
      items,
    });
    setCreateOpen(false);
  }

  async function handleOrderStatus(status?: OrderStatus) {
    if (!activeOrder) {
      return;
    }

    await onAdvanceOrder({ order_id: activeOrder.id, status });
    setActiveOrder(null);
  }

  return (
    <section className="orders-board" aria-label="Orders board">
      <div className="panel__header">
        <div>
          <p className="eyebrow">Kitchen and delivery state</p>
          <h2>Orders Board</h2>
        </div>
        <button disabled={!canUpdateOrders(role) || saving} onClick={openCreateOrder}>Create order</button>
      </div>
      <div className="orders-columns">
        {columns.map((status) => (
          <article className="order-column" key={status}>
            <h3>{status.replace("_", " ")}</h3>
            {orders
              .filter((order) => order.status === status)
              .map((order) => {
                const table = tables.find((candidate) => candidate.id === order.table_id);
                const items = normalizeOrderItems(order.items, menu);
                const canAdvance = status === "ready" ? hasMinimumRole(role, "manager") : canUpdateOrders(role);

                return (
                  <div className="order-card" key={order.id}>
                    <strong>{table ? `Table ${table.table_number}` : order.table_id}</strong>
                    <span>{items.map((item) => `${item.quantity}x ${item.name}`).join(", ")}</span>
                    <small>{order.assigned_robot ? `Robot: ${order.assigned_robot}` : "No robot assigned"}</small>
                    <button
                      disabled={!canAdvance || saving || status === "delivered"}
                      onClick={() => setActiveOrder(order)}
                    >
                      {status === "ready" ? "Request delivery" : "Advance"}
                    </button>
                  </div>
                );
              })}
          </article>
        ))}
      </div>
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
                  title={`Table ${table.table_number}`}
                />
              ))}
            </div>
          </div>
          <div>
            <span className="field-label">Menu items</span>
            <div className="menu-grid">
              {menu.map((item) => {
                const quantity = selectedItems[item.id] ?? 0;

                return (
                  <article className={`menu-choice ${quantity ? "menu-choice--selected" : ""}`} key={item.id}>
                    <button onClick={() => toggleItem(item)} type="button">
                      <strong>{item.name}</strong>
                      <span>{item.category}</span>
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
          <label>
            Order notes
            <textarea onChange={(event) => setNotes(event.target.value)} value={notes} />
          </label>
          <div className="modal-actions">
            <button className="button button--ghost" onClick={() => setCreateOpen(false)} type="button">
              Cancel
            </button>
            <button disabled={saving || !selectedTableId || Object.keys(selectedItems).length === 0} type="submit">
              Create order
            </button>
          </div>
        </form>
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
