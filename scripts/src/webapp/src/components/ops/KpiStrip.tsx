import type { OpsSnapshot } from "../../types/firestore";

interface KpiStripProps {
  snapshot: OpsSnapshot;
}

export function KpiStrip({ snapshot }: KpiStripProps) {
  const waitingParties = snapshot.entrance.filter((party) => party.status === "waiting").length;
  const freeTables = snapshot.tables.filter((table) => table.status === "empty").length;
  const activeOrders = snapshot.orders.filter(
    (order) => !["delivered", "cancelled", "failed"].includes(order.status),
  ).length;
  const runningTasks = snapshot.tasks.filter((task) => task.status === "running" || task.status === "queued").length;
  const alerts = snapshot.events.filter((event) => event.severity !== "info").length;

  return (
    <section className="kpi-strip" aria-label="Key metrics">
      <KpiCard label="Waiting parties" value={waitingParties} tone={waitingParties > 0 ? "amber" : "green"} />
      <KpiCard label="Free tables" value={freeTables} tone={freeTables > 0 ? "green" : "amber"} />
      <KpiCard label="Active orders" value={activeOrders} tone="steel" />
      <KpiCard label="Running tasks" value={runningTasks} tone="steel" />
      <KpiCard label="Alerts" value={alerts} tone={alerts > 0 ? "red" : "green"} />
    </section>
  );
}

function KpiCard({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <article className={`kpi-card kpi-card--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}
