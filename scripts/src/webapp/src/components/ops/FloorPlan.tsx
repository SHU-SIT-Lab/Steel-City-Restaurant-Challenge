import { useState } from "react";
import type { UpdateTableInput } from "../../lib/api/client";
import { tableLabel } from "../../lib/firestore/converters";
import type { OpsSnapshot, Table, TableStatus } from "../../types/firestore";
import { Modal, OptionCard } from "../ui/Modal";

interface FloorPlanProps {
  snapshot: OpsSnapshot;
  saving: boolean;
  onUpdateTableStatus: (input: UpdateTableInput) => Promise<void>;
}

const tableStatuses: TableStatus[] = ["empty", "occupied", "needs_cleaning", "unavailable"];

function hasFinitePose(table: Table): boolean {
  return Number.isFinite(table.pose_x) && Number.isFinite(table.pose_y);
}

// Place tables by their real pose when present; otherwise lay them out in a tidy
// grid across the lower portion of the canvas (clear of the entrance/kitchen
// zones up top and the robot marker), so the map is readable without pose data.
function tablePosition(table: Table, index: number, total: number): { left: string; top: string } {
  if (hasFinitePose(table)) {
    return {
      left: `${Math.min(table.pose_x * 12, 78)}%`,
      top: `${Math.min(table.pose_y * 18, 78)}%`,
    };
  }
  const cols = Math.min(Math.max(total, 1), 3);
  const rows = Math.max(Math.ceil(total / cols), 1);
  const col = index % cols;
  const row = Math.floor(index / cols);
  const left = ((col + 0.5) / cols) * 100;
  const top = rows === 1 ? 60 : 38 + (row / (rows - 1)) * 40;
  return { left: `${left}%`, top: `${top}%` };
}

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
        {snapshot.tables.map((table, index) => (
          <TableCard
            key={table.id}
            index={index}
            total={snapshot.tables.length}
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
        title={selectedTable ? tableLabel(selectedTable) : "Table"}
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
  index,
  total,
  onSelect,
}: {
  table: Table;
  index: number;
  total: number;
  saving: boolean;
  onSelect: () => void;
}) {
  const { left, top } = tablePosition(table, index, total);

  return (
    <button
      className={`table-card table-card--${table.status}`}
      onClick={onSelect}
      style={{ left, top }}
      type="button"
    >
      <strong>{tableLabel(table)}</strong>
      <span>{table.status.replace("_", " ")}</span>
      {hasFinitePose(table) ? (
        <small>
          x {table.pose_x} / y {table.pose_y}
        </small>
      ) : null}
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
            {hasFinitePose(table)
              ? `${table.pose_x}, ${table.pose_y}, ${table.pose_theta}`
              : "Not set"}
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
