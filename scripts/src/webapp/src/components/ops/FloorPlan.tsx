import { useState } from "react";
import type { UpdateTableInput } from "../../lib/api/client";
import type { OpsSnapshot, Table, TableStatus } from "../../types/firestore";
import { Modal, OptionCard } from "../ui/Modal";

interface FloorPlanProps {
  snapshot: OpsSnapshot;
  saving: boolean;
  onUpdateTableStatus: (input: UpdateTableInput) => Promise<void>;
}

const tableStatuses: TableStatus[] = ["empty", "occupied", "needs_cleaning", "unavailable"];

export function FloorPlan({ snapshot, saving, onUpdateTableStatus }: FloorPlanProps) {
  const robot = snapshot.robots[0];
  const [selectedTable, setSelectedTable] = useState<Table | null>(null);

  return (
    <section className="floor-plan" aria-label="Restaurant floor plan">
      <div className="panel__header">
        <div>
          <p className="eyebrow">Pose map</p>
          <h2>Restaurant Floor</h2>
        </div>
        <span className="tag tag--live">Live pose map</span>
      </div>

      <div className="floor-plan__canvas">
        <div className="zone zone--entrance">Entrance</div>
        <div className="zone zone--kitchen">Kitchen bar</div>
        {snapshot.tables.map((table) => (
          <TableCard
            key={table.id}
            onSelect={() => setSelectedTable(table)}
            table={table}
            saving={saving}
          />
        ))}
        {robot ? (
          <div className="robot-marker" style={{ left: "70%", top: "23%" }} aria-label={`${robot.name} robot marker`}>
            <span />
            {robot.name}
          </div>
        ) : null}
      </div>
      <Modal
        eyebrow="Table detail"
        onClose={() => setSelectedTable(null)}
        open={Boolean(selectedTable)}
        title={selectedTable ? `Table ${selectedTable.table_number}` : "Table"}
      >
        {selectedTable ? (
          <TableActionSheet
            onClose={() => setSelectedTable(null)}
            onUpdateTableStatus={onUpdateTableStatus}
            saving={saving}
            snapshot={snapshot}
            table={selectedTable}
          />
        ) : null}
      </Modal>
    </section>
  );
}

function TableCard({
  table,
  onSelect,
}: {
  table: Table;
  saving: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      className={`table-card table-card--${table.status}`}
      onClick={onSelect}
      style={{
        left: `${Math.min(table.pose_x * 12, 78)}%`,
        top: `${Math.min(table.pose_y * 18, 78)}%`,
      }}
      type="button"
    >
      <strong>Table {table.table_number}</strong>
      <span>{table.status.replace("_", " ")}</span>
      <small>
        x {table.pose_x} / y {table.pose_y}
      </small>
    </button>
  );
}

function TableActionSheet({
  snapshot,
  table,
  saving,
  onUpdateTableStatus,
  onClose,
}: {
  snapshot: OpsSnapshot;
  table: Table;
  saving: boolean;
  onUpdateTableStatus: (input: UpdateTableInput) => Promise<void>;
  onClose: () => void;
}) {
  const party = snapshot.entrance.find((candidate) => candidate.id === table.current_party);
  const order = snapshot.orders.find((candidate) => candidate.id === table.current_order);

  async function setStatus(status: TableStatus) {
    await onUpdateTableStatus({ table_id: table.id, status });
    onClose();
  }

  return (
    <div className="form-stack">
      <dl className="detail-list">
        <div>
          <dt>Status</dt>
          <dd>{table.status.replace("_", " ")}</dd>
        </div>
        <div>
          <dt>Pose</dt>
          <dd>
            {table.pose_x}, {table.pose_y}, {table.pose_theta}
          </dd>
        </div>
        <div>
          <dt>Party</dt>
          <dd>{party ? `Party of ${party.party_size}` : "None"}</dd>
        </div>
        <div>
          <dt>Order</dt>
          <dd>{order ? order.status : "None"}</dd>
        </div>
      </dl>
      <div className="selection-grid">
        {tableStatuses.map((status) => (
          <OptionCard
            key={status}
            disabled={saving}
            meta={status === "empty" ? "Clears party/order links" : "Writes table status"}
            onClick={() => setStatus(status)}
            selected={table.status === status}
            title={status.replace("_", " ")}
          />
        ))}
      </div>
    </div>
  );
}
