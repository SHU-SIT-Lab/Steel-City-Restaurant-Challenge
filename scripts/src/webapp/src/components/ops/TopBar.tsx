import type { Robot, Role } from "../../types/firestore";

interface TopBarProps {
  role: Role;
  robot: Robot;
  mode: "live" | "mock";
  loading: boolean;
  saving: boolean;
  error: string | null;
  onRefresh: () => void;
  onSwitchView?: () => void;
}

export function TopBar({ role, robot, mode, loading, saving, error, onRefresh, onSwitchView }: TopBarProps) {
  const healthLabel = error
    ? "Degraded"
    : robot.status === "offline" || robot.status === "error"
      ? "Degraded"
      : "System OK";
  const healthTone = healthLabel === "Degraded" ? "degraded" : "live";
  const dataLabel = loading ? "Connecting" : mode === "live" ? "Firestore connected" : "Mock data";

  return (
    <header className="top-bar">
      <div>
        <p className="eyebrow">Steel City Restaurant Challenge</p>
        <h1>Steel City Ops</h1>
      </div>
      <div className="top-bar__status">
        <span className={`status-pill status-pill--${healthTone}`}>{healthLabel}</span>
        <span className={`tag tag--${mode === "live" ? "live" : "waiting"}`}>
          {dataLabel}
        </span>
        {saving ? <span className="tag tag--waiting">Saving</span> : null}
        <span className="top-bar__meta">
          Robot <strong>{robot.name}</strong> / {robot.status} / {robot.battery_pct}%
        </span>
        <span className="role-pill">{role}</span>
        <button onClick={onRefresh}>Refresh</button>
        {onSwitchView ? (
          <button className="button--ghost" onClick={onSwitchView} type="button">
            Switch view
          </button>
        ) : null}
      </div>
      {error ? <p className="top-bar__error">{error}</p> : null}
    </header>
  );
}
