import { useMemo, useState, type FormEvent } from "react";
import { hasMinimumRole } from "../../lib/rbac";
import type { EntranceParty, Role, Table } from "../../types/firestore";
import type { AssignPartyInput, CreatePartyInput } from "../../lib/api/client";
import { tableLabel } from "../../lib/firestore/converters";
import { Modal, OptionCard } from "../ui/Modal";

interface CustomerQueueProps {
  role: Role;
  parties: EntranceParty[];
  tables: Table[];
  saving: boolean;
  onCreateParty: (input: CreatePartyInput) => Promise<void>;
  onAssignParty: (input: AssignPartyInput) => Promise<void>;
  onSeatParty: (input: AssignPartyInput) => Promise<void>;
}

export function CustomerQueue({
  role,
  parties,
  tables,
  saving,
  onCreateParty,
  onAssignParty,
  onSeatParty,
}: CustomerQueueProps) {
  const canSeat = hasMinimumRole(role, "operator");
  const queue = parties.filter((party) => party.status !== "cancelled" && party.status !== "no_show");
  const availableTables = tables.filter((table) => table.status === "empty");
  const [partyDialogOpen, setPartyDialogOpen] = useState(false);
  const [partySize, setPartySize] = useState(2);
  const [notes, setNotes] = useState("");
  const [assigningParty, setAssigningParty] = useState<EntranceParty | null>(null);
  const [selectedTableId, setSelectedTableId] = useState<string>("");
  const [actionError, setActionError] = useState<string | null>(null);

  const recommendedTable = useMemo(
    () => availableTables.find((table) => (table.table_number ?? 0) >= partySize) ?? availableTables[0],
    [availableTables, partySize],
  );

  async function handleCreateParty(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await onCreateParty({ party_size: partySize, notes });
      setPartyDialogOpen(false);
      setPartySize(2);
      setNotes("");
      setActionError(null);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not add the party.");
    }
  }

  async function handlePartyAction(party: EntranceParty) {
    if (party.assigned_table) {
      try {
        await onSeatParty({ party_id: party.id, table_id: party.assigned_table });
      } catch {
        // Seat failures surface in the top-bar status banner.
      }
      return;
    }

    setActionError(null);
    setAssigningParty(party);
    setSelectedTableId(recommendedTable?.id ?? availableTables[0]?.id ?? "");
  }

  async function handleAssignParty(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!assigningParty || !selectedTableId) {
      return;
    }

    try {
      await onAssignParty({ party_id: assigningParty.id, table_id: selectedTableId });
      setAssigningParty(null);
      setSelectedTableId("");
      setActionError(null);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not assign the table.");
    }
  }

  return (
    <section className="panel">
      <div className="panel__header">
        <h2>Customer Queue</h2>
        <button disabled={!canSeat || saving} onClick={() => { setActionError(null); setPartyDialogOpen(true); }}>Add party</button>
      </div>
      <div className="stack-list">
        {queue.length === 0 ? <p className="empty-state">No active parties in the entrance queue.</p> : null}
        {queue.map((party) => {
          const assignedTable = tables.find((table) => table.id === party.assigned_table);

          return (
            <article className="queue-item" key={party.id}>
              <div>
                <strong>Party of {party.party_size}</strong>
                <span>{party.detected_by} detection</span>
              </div>
              <div className="queue-item__meta">
                <span className={`tag tag--${party.status}`}>{party.status}</span>
                <span>{assignedTable ? tableLabel(assignedTable) : "Unassigned"}</span>
              </div>
              <p>{party.notes || "No staff notes"}</p>
              <button
                disabled={!canSeat || saving || party.status === "seated"}
                onClick={() => handlePartyAction(party)}
              >
                {assignedTable ? "Mark seated" : "Assign table"}
              </button>
            </article>
          );
        })}
      </div>
      <Modal
        eyebrow="Entrance workflow"
        onClose={() => setPartyDialogOpen(false)}
        open={partyDialogOpen}
        title="Add Waiting Party"
      >
        <form className="form-stack" onSubmit={handleCreateParty}>
          <label>
            Party size
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
          <label>
            Staff notes
            <textarea
              onChange={(event) => setNotes(event.target.value)}
              placeholder="Accessibility needs, wait notes, source..."
              value={notes}
            />
          </label>
          {actionError ? <p className="form-error">{actionError}</p> : null}
          <div className="modal-actions">
            <button className="button button--ghost" onClick={() => setPartyDialogOpen(false)} type="button">
              Cancel
            </button>
            <button disabled={saving} type="submit">{saving ? "Adding…" : "Create party"}</button>
          </div>
        </form>
      </Modal>
      <Modal
        eyebrow="Table assignment"
        onClose={() => setAssigningParty(null)}
        open={Boolean(assigningParty)}
        title={assigningParty ? `Assign Party of ${assigningParty.party_size}` : "Assign Party"}
      >
        <form className="form-stack" onSubmit={handleAssignParty}>
          {availableTables.length === 0 ? (
            <p className="empty-state">No empty tables are currently available.</p>
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
          {actionError ? <p className="form-error">{actionError}</p> : null}
          <div className="modal-actions">
            <button className="button button--ghost" onClick={() => setAssigningParty(null)} type="button">
              Cancel
            </button>
            <button disabled={saving || !selectedTableId} type="submit">{saving ? "Assigning…" : "Assign table"}</button>
          </div>
        </form>
      </Modal>
    </section>
  );
}
