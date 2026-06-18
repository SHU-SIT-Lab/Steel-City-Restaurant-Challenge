import { useMemo, useState, type FormEvent } from "react";
import { hasRole } from "../../lib/rbac";
import type { CommandDefinition } from "../../types/commands";
import type { EntranceParty, Order, Robot, Role, Table } from "../../types/firestore";
import type { QueueCommandInput } from "../../lib/api/client";
import { Modal, OptionCard } from "../ui/Modal";

interface CommandDeckProps {
  role: Role;
  commands: CommandDefinition[];
  robots: Robot[];
  tables: Table[];
  orders: Order[];
  parties: EntranceParty[];
  saving: boolean;
  onQueueCommand: (input: QueueCommandInput) => Promise<void>;
}

export function CommandDeck({
  role,
  commands,
  robots,
  tables,
  orders,
  parties,
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
  const [selectedPartyId, setSelectedPartyId] = useState("");
  const [partySize, setPartySize] = useState(2);
  const [waypoint, setWaypoint] = useState("");
  const [reason, setReason] = useState("");

  const executableOrders = useMemo(
    () => orders.filter((order) => !["delivered", "cancelled", "failed"].includes(order.status)),
    [orders],
  );

  const partyQueue = useMemo(
    () => parties.filter((party) => party.status !== "cancelled" && party.status !== "no_show"),
    [parties],
  );

  const waypointSuggestions = useMemo(
    () =>
      Array.from(
        new Set(
          [...robots.map((candidate) => candidate.current_location), "kitchen_bar", "entrance", "charging_dock"].filter(
            Boolean,
          ),
        ),
      ),
    [robots],
  );

  function openCommand(command: CommandDefinition) {
    const firstParty = partyQueue[0];

    setActiveCommand(command);
    setSelectedRobotId(robot?.id ?? "");
    setSelectedTableId(targetTable?.id ?? "");
    setSelectedOrderId(targetOrder?.id ?? "");
    setSelectedPartyId(firstParty?.id ?? "");
    setPartySize(firstParty?.party_size ?? 2);
    setWaypoint("");
    setReason("");
  }

  function selectParty(party: EntranceParty) {
    setSelectedPartyId(party.id);
    setPartySize(party.party_size);
  }

  const missingRequirement = useMemo(() => {
    if (!activeCommand) {
      return true;
    }

    const required = activeCommand.requiredParams;

    if (required.includes("robot_id") && !selectedRobotId) return true;
    if (required.includes("table_id") && !selectedTableId) return true;
    if (required.includes("order_id") && !selectedOrderId) return true;
    if (required.includes("party_id") && !selectedPartyId) return true;
    if (required.includes("waypoint") && !waypoint.trim()) return true;
    if (required.includes("reason") && !reason.trim()) return true;

    return false;
  }, [activeCommand, selectedRobotId, selectedTableId, selectedOrderId, selectedPartyId, waypoint, reason]);

  async function handleQueueCommand(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!activeCommand || missingRequirement) {
      return;
    }

    const payload = buildCommandPayload(activeCommand, {
      robot: robots.find((candidate) => candidate.id === selectedRobotId),
      table: tables.find((candidate) => candidate.id === selectedTableId),
      order: orders.find((candidate) => candidate.id === selectedOrderId),
      party: parties.find((candidate) => candidate.id === selectedPartyId),
      waypoint,
      partySize,
      reason,
    });

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
          const needsRobot = command.requiredParams.includes("robot_id");

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
                disabled={!allowed || saving || (needsRobot && !robot)}
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
            {activeCommand.requiredParams.includes("party_id") ? (
              <div>
                <span className="field-label">Party</span>
                {partyQueue.length === 0 ? (
                  <p className="empty-state">No active parties in the entrance queue.</p>
                ) : (
                  <div className="selection-grid">
                    {partyQueue.map((party) => (
                      <OptionCard
                        key={party.id}
                        meta={`${party.status} / party of ${party.party_size}`}
                        onClick={() => selectParty(party)}
                        selected={selectedPartyId === party.id}
                        title={party.notes || `Party ${party.id.slice(0, 6)}`}
                      />
                    ))}
                  </div>
                )}
              </div>
            ) : null}
            {activeCommand.requiredParams.includes("party_size") ? (
              <label>
                New customer count
                <div className="stepper">
                  <button
                    disabled={partySize <= 1}
                    onClick={() => setPartySize((value) => Math.max(1, value - 1))}
                    type="button"
                  >
                    -
                  </button>
                  <strong>{partySize}</strong>
                  <button
                    disabled={partySize >= 12}
                    onClick={() => setPartySize((value) => Math.min(12, value + 1))}
                    type="button"
                  >
                    +
                  </button>
                </div>
              </label>
            ) : null}
            {activeCommand.requiredParams.includes("waypoint") ? (
              <label>
                Waypoint
                <input
                  list="command-waypoints"
                  onChange={(event) => setWaypoint(event.target.value)}
                  placeholder="e.g. kitchen_bar"
                  type="text"
                  value={waypoint}
                />
                <datalist id="command-waypoints">
                  {waypointSuggestions.map((suggestion) => (
                    <option key={suggestion} value={suggestion} />
                  ))}
                </datalist>
              </label>
            ) : null}
            {activeCommand.requiredParams.includes("reason") ? (
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
              <button disabled={saving || missingRequirement} type="submit">
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
  selections: {
    robot?: Robot;
    table?: Table;
    order?: Order;
    party?: EntranceParty;
    waypoint: string;
    partySize: number;
    reason: string;
  },
): QueueCommandInput {
  const { robot, table, order, party, waypoint, partySize, reason } = selections;
  const required = command.requiredParams;
  const target: QueueCommandInput["target"] = {};
  const params: Record<string, unknown> = {};

  if (required.includes("table_id") && table) {
    target.table_id = table.id;
  }

  if (required.includes("order_id") && order) {
    target.order_id = order.id;
    target.table_id = order.table_id;
  }

  if (required.includes("waypoint") && waypoint.trim()) {
    target.waypoint = waypoint.trim();
  }

  if (required.includes("party_id") && party) {
    target.party_id = party.id;
  }

  if (required.includes("party_size")) {
    params.party_size = partySize;
  }

  if (required.includes("reason") && reason.trim()) {
    params.reason = reason.trim();
  }

  return {
    command_type: command.type,
    robot_id: required.includes("robot_id") ? (robot?.id ?? null) : null,
    target,
    params,
    idempotency_key: `${command.type}-${Date.now()}`,
  };
}
