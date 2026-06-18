import { useCallback, useEffect, useState } from "react";

export type AppView = "select" | "manager" | "customer";

const STORAGE_KEY = "steelCity.view";
const ALLOWED: AppView[] = ["select", "manager", "customer"];

function readStoredView(): AppView {
  if (typeof window === "undefined") {
    return "select";
  }

  const stored = window.localStorage.getItem(STORAGE_KEY);

  return ALLOWED.includes(stored as AppView) ? (stored as AppView) : "select";
}

/**
 * Top-level screen selection (manager vs customer), persisted to localStorage so a
 * reload keeps the chosen view. There is no router; App switches on this value.
 */
export function useView(): { view: AppView; setView: (next: AppView) => void } {
  const [view, setViewState] = useState<AppView>(readStoredView);

  useEffect(() => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, view);
    }
  }, [view]);

  const setView = useCallback((next: AppView) => setViewState(next), []);

  return { view, setView };
}
