import type { OpsSnapshot } from "../types/firestore";

// Cache the last live snapshot in localStorage so a page refresh can show real
// data immediately instead of the mock seed / a "Connecting" flash.
const STORAGE_KEY = "steelCity.snapshot";
// Ignore cache older than a day so the UI never seeds from very stale data.
const MAX_AGE_MS = 24 * 60 * 60 * 1000;

interface CachedSnapshot {
  snapshot: OpsSnapshot;
  cachedAt: number;
}

export function loadCachedSnapshot(): OpsSnapshot | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<CachedSnapshot>;
    if (!parsed || !parsed.snapshot || typeof parsed.cachedAt !== "number") {
      return null;
    }
    if (Date.now() - parsed.cachedAt > MAX_AGE_MS) {
      return null;
    }
    return parsed.snapshot;
  } catch {
    return null;
  }
}

export function saveCachedSnapshot(snapshot: OpsSnapshot): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    const payload: CachedSnapshot = { snapshot, cachedAt: Date.now() };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch {
    /* ignore quota / serialization failures */
  }
}
