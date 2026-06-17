import { useCallback, useEffect, useMemo, useState } from "react";
import {
  advanceOrder,
  assignParty,
  createOrder,
  createParty,
  envRole,
  fetchSnapshot,
  queueCommand,
  seatParty,
  updateTableStatus,
  type AdvanceOrderInput,
  type AssignPartyInput,
  type CreateOrderInput,
  type CreatePartyInput,
  type QueueCommandInput,
  type SnapshotResponse,
  type UpdateTableInput,
} from "../lib/api/client";
import { mockSnapshot } from "../data/mockFirestore";
import type { OpsSnapshot } from "../types/firestore";

export interface OpsActions {
  refresh: () => Promise<void>;
  createParty: (input: CreatePartyInput) => Promise<void>;
  assignParty: (input: AssignPartyInput) => Promise<void>;
  seatParty: (input: AssignPartyInput) => Promise<void>;
  updateTableStatus: (input: UpdateTableInput) => Promise<void>;
  createOrder: (input: CreateOrderInput) => Promise<void>;
  advanceOrder: (input: AdvanceOrderInput) => Promise<void>;
  queueCommand: (input: QueueCommandInput) => Promise<void>;
}

export interface OpsDataState {
  snapshot: OpsSnapshot;
  mode: "live" | "mock";
  loading: boolean;
  saving: boolean;
  error: string | null;
  actions: OpsActions;
}

function withDefaults(snapshot: SnapshotResponse): OpsSnapshot {
  return {
    role: snapshot.role ?? envRole(),
    entrance: snapshot.entrance ?? [],
    tables: snapshot.tables ?? [],
    menu: snapshot.menu ?? [],
    orders: snapshot.orders ?? [],
    robots: snapshot.robots ?? [],
    tasks: snapshot.tasks ?? [],
    events: snapshot.events ?? [],
  };
}

export function useOpsData(): OpsDataState {
  const [snapshot, setSnapshot] = useState<OpsSnapshot>({ ...mockSnapshot, role: envRole() });
  const [mode, setMode] = useState<"live" | "mock">("mock");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const response = await fetchSnapshot();
      setSnapshot(withDefaults(response));
      setMode(response.mode);
      setError(null);
    } catch (requestError) {
      setMode("mock");
      setError(requestError instanceof Error ? requestError.message : "Unable to load Firestore snapshot");
    } finally {
      setLoading(false);
    }
  }, []);

  const mutate = useCallback(
    async (operation: () => Promise<unknown>) => {
      setSaving(true);
      setError(null);

      try {
        await operation();
        await refresh();
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "Firestore mutation failed");
      } finally {
        setSaving(false);
      }
    },
    [refresh],
  );

  useEffect(() => {
    refresh();
    const interval = window.setInterval(refresh, 3000);

    return () => window.clearInterval(interval);
  }, [refresh]);

  const actions = useMemo<OpsActions>(
    () => ({
      refresh,
      createParty: (input) => mutate(() => createParty(input)),
      assignParty: (input) => mutate(() => assignParty(input)),
      seatParty: (input) => mutate(() => seatParty(input)),
      updateTableStatus: (input) => mutate(() => updateTableStatus(input)),
      createOrder: (input) => mutate(() => createOrder(input)),
      advanceOrder: (input) => mutate(() => advanceOrder(input)),
      queueCommand: (input) => mutate(() => queueCommand(input)),
    }),
    [mutate, refresh],
  );

  return {
    snapshot,
    mode,
    loading,
    saving,
    error,
    actions,
  };
}
