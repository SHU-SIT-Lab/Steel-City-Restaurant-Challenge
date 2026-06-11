import { ActivityLog } from "./components/ops/ActivityLog";
import { CommandDeck } from "./components/ops/CommandDeck";
import { CustomerQueue } from "./components/ops/CustomerQueue";
import { FloorPlan } from "./components/ops/FloorPlan";
import { KpiStrip } from "./components/ops/KpiStrip";
import { OrdersBoard } from "./components/ops/OrdersBoard";
import { RobotPanel } from "./components/ops/RobotPanel";
import { TopBar } from "./components/ops/TopBar";
import { commandCatalogue, mockSnapshot } from "./data/mockFirestore";
import { useOpsData } from "./hooks/useOpsData";

export default function App() {
  const { snapshot, mode, loading, saving, error, actions } = useOpsData();
  const primaryRobot = snapshot.robots[0] ?? mockSnapshot.robots[0];

  return (
    <main className="app-shell">
      <TopBar
        role={snapshot.role}
        robot={primaryRobot}
        mode={mode}
        loading={loading}
        saving={saving}
        error={error}
        onRefresh={actions.refresh}
      />
      <KpiStrip snapshot={snapshot} />

      <section className="ops-grid" aria-label="Operations dashboard">
        <aside className="left-rail">
          <CustomerQueue
            role={snapshot.role}
            parties={snapshot.entrance}
            tables={snapshot.tables}
            saving={saving}
            onCreateParty={actions.createParty}
            onAssignParty={actions.assignParty}
            onSeatParty={actions.seatParty}
          />
          <RobotPanel robot={primaryRobot} tasks={snapshot.tasks} />
        </aside>

        <FloorPlan
          snapshot={snapshot}
          saving={saving}
          onUpdateTableStatus={actions.updateTableStatus}
        />

        <aside className="right-rail">
          <CommandDeck
            role={snapshot.role}
            commands={commandCatalogue}
            robots={snapshot.robots}
            tables={snapshot.tables}
            orders={snapshot.orders}
            saving={saving}
            onQueueCommand={actions.queueCommand}
          />
          <ActivityLog events={snapshot.events} />
        </aside>
      </section>

      <OrdersBoard
        role={snapshot.role}
        orders={snapshot.orders}
        tables={snapshot.tables}
        menu={snapshot.menu}
        saving={saving}
        onCreateOrder={actions.createOrder}
        onAdvanceOrder={actions.advanceOrder}
      />
    </main>
  );
}
