import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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

// Poll the snapshot on an interval that backs off on errors and pauses when the tab
// is hidden, so idle tablets and failing backends stop hammering the API.
const BASE_POLL_MS = 8000;
const MAX_POLL_MS = 60000;

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
  const failuresRef = useRef(0);

  const refresh = useCallback(async () => {
    try {
      const response = await fetchSnapshot();
      setSnapshot(withDefaults(response));
      setMode(response.mode);
      setError(null);
      failuresRef.current = 0;
    } catch (requestError) {
      setMode("mock");
      setError(requestError instanceof Error ? requestError.message : "Unable to load Firestore snapshot");
      failuresRef.current += 1;
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
        const message = requestError instanceof Error ? requestError.message : "Firestore mutation failed";
        setError(message);
        // Re-throw so the calling component can keep its modal open and show the error inline.
        throw requestError instanceof Error ? requestError : new Error(message);
      } finally {
        setSaving(false);
      }
    },
    [refresh],
  );

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    const schedule = () => {
      window.clearTimeout(timer);
      // Don't poll while the tab is hidden (e.g. an idle customer tablet); resume on focus.
      if (cancelled || document.hidden) {
        return;
      }
      const delay = Math.min(MAX_POLL_MS, BASE_POLL_MS * 2 ** failuresRef.current);
      timer = window.setTimeout(run, delay);
    };

    const run = () => {
      window.clearTimeout(timer);
      void refresh().finally(() => {
        if (!cancelled) {
          schedule();
        }
      });
    };

    const onVisibilityChange = () => {
      if (document.hidden) {
        window.clearTimeout(timer);
      } else {
        run();
      }
    };

    run();
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
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
