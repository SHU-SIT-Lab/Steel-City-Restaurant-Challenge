import { useMemo, useState, type FormEvent } from "react";
import { hasRole } from "../../lib/rbac";
import type { CommandDefinition } from "../../types/commands";
import type { Order, Robot, Role, Table } from "../../types/firestore";
import type { QueueCommandInput } from "../../lib/api/client";
import { Modal, OptionCard } from "../ui/Modal";

interface CommandDeckProps {
  role: Role;
  commands: CommandDefinition[];
  robots: Robot[];
  tables: Table[];
  orders: Order[];
  saving: boolean;
  onQueueCommand: (input: QueueCommandInput) => Promise<void>;
}

export function CommandDeck({
  role,
  commands,
  robots,
  tables,
  orders,
  saving,
  onQueueCommand,
}: CommandDeckProps) {
  const robot = robots[0];
  const targetTable = tables.find((table) => table.status !== "unavailable");
  const targetOrder = orders.find((order) => order.status === "ready") ?? orders[0];
  const [activeCommand, setActiveCommand] = useState<CommandDefinition | null>(null);
  const [selectedRobotId, setSelectedRobotId] = useState(robot?.id ?? "");
  const [selectedTableId, setSelectedTableId] = useState(targetTable?.id ?? "");
  const [selectedOrderId, setSelectedOrderId] = useState(targetOrder?.id ?? "");
  const [reason, setReason] = useState("Queued from web app");

  const executableOrders = useMemo(
    () => orders.filter((order) => !["delivered", "cancelled", "failed"].includes(order.status)),
    [orders],
  );

  function openCommand(command: CommandDefinition) {
    setActiveCommand(command);
    setSelectedRobotId(robot?.id ?? "");
    setSelectedTableId(targetTable?.id ?? "");
    setSelectedOrderId(targetOrder?.id ?? "");
    setReason(command.type === "EMERGENCY_STOP" ? "" : "Queued from web app");
  }

  async function handleQueueCommand(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!activeCommand) {
      return;
    }

    const payload = buildCommandPayload(
      activeCommand,
      robots.find((candidate) => candidate.id === selectedRobotId),
      tables.find((candidate) => candidate.id === selectedTableId),
      orders.find((candidate) => candidate.id === selectedOrderId),
      reason,
    );

    await onQueueCommand(payload);
    setActiveCommand(null);
  }

  return (
    <section className="panel command-deck">
      <div className="panel__header">
        <h2>Command Deck</h2>
        <span className="tag">Role: {role}</span>
      </div>
      <div className="command-list">
        {commands.map((command) => {
          const allowed = hasRole(role, command.roles);

          return (
            <article className={`command-row ${command.highRisk ? "command-row--risk" : ""}`} key={command.type}>
              <div>
                <strong>{command.label}</strong>
                <span>{command.description}</span>
                <small>
                  Params: {command.requiredParams.join(", ")}
                </small>
              </div>
              <button
                disabled={!allowed || saving || !robot}
                onClick={() => openCommand(command)}
              >
                {allowed ? "Configure" : "Locked"}
              </button>
            </article>
          );
        })}
      </div>
      <div className="command-preview">
        <span>Request preview</span>
        <code>
          {JSON.stringify(
            {
              robot_id: robot?.id,
              target: {
                table_id: targetTable?.id,
                order_id: targetOrder?.id,
              },
            },
            null,
            2,
          )}
        </code>
      </div>
      <Modal
        eyebrow="Command executor"
        onClose={() => setActiveCommand(null)}
        open={Boolean(activeCommand)}
        title={activeCommand?.label ?? "Command"}
      >
        {activeCommand ? (
          <form className="form-stack" onSubmit={handleQueueCommand}>
            {activeCommand.requiredParams.includes("robot_id") ? (
              <div>
                <span className="field-label">Robot</span>
                <div className="selection-grid">
                  {robots.map((candidate) => (
                    <OptionCard
                      key={candidate.id}
                      meta={`${candidate.status} at ${candidate.current_location}`}
                      onClick={() => setSelectedRobotId(candidate.id)}
                      selected={selectedRobotId === candidate.id}
                      title={candidate.name}
                    />
                  ))}
                </div>
              </div>
            ) : null}
            {activeCommand.requiredParams.includes("table_id") ? (
              <div>
                <span className="field-label">Table target</span>
                <div className="selection-grid">
                  {tables
                    .filter((table) => table.status !== "unavailable")
                    .map((table) => (
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
            ) : null}
            {activeCommand.requiredParams.includes("order_id") ? (
              <div>
                <span className="field-label">Order target</span>
                <div className="selection-grid">
                  {executableOrders.map((order) => (
                    <OptionCard
                      key={order.id}
                      meta={`${order.status} / ${order.table_id}`}
                      onClick={() => setSelectedOrderId(order.id)}
                      selected={selectedOrderId === order.id}
                      title={order.id.slice(0, 8)}
                    />
                  ))}
                </div>
              </div>
            ) : null}
            {activeCommand.type === "EMERGENCY_STOP" ? (
              <label>
                Safety reason
                <textarea
                  onChange={(event) => setReason(event.target.value)}
                  placeholder="Required for emergency stop"
                  value={reason}
                />
              </label>
            ) : null}
            <div className="command-preview">
              <span>Firestore command/task only; ROS bridge is not called yet.</span>
            </div>
            <div className="modal-actions">
              <button className="button button--ghost" onClick={() => setActiveCommand(null)} type="button">
                Cancel
              </button>
              <button
                disabled={saving || (activeCommand.type === "EMERGENCY_STOP" && !reason.trim())}
                type="submit"
              >
                Queue command
              </button>
            </div>
          </form>
        ) : null}
      </Modal>
    </section>
  );
}

function buildCommandPayload(
  command: CommandDefinition,
  robot: Robot | undefined,
  table: Table | undefined,
  order: Order | undefined,
  reason: string,
): QueueCommandInput {
  const target: QueueCommandInput["target"] = {};

  if (command.requiredParams.includes("table_id") && table) {
    target.table_id = table.id;
  }

  if (command.requiredParams.includes("order_id") && order) {
    target.order_id = order.id;
    target.table_id = order.table_id;
  }

  return {
    command_type: command.type,
    robot_id: robot?.id ?? null,
    target,
    params: command.type === "EMERGENCY_STOP" ? { reason } : {},
    idempotency_key: `${command.type}-${Date.now()}`,
  };
}
