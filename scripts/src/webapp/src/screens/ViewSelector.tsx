interface ViewSelectorProps {
  onSelect: (view: "manager" | "customer") => void;
}

export function ViewSelector({ onSelect }: ViewSelectorProps) {
  return (
    <main className="view-selector">
      <div className="view-selector__brand">
        <p className="eyebrow">Steel City Restaurant Challenge</p>
        <h1>Steel City Ops</h1>
        <p className="view-selector__sub">Choose a screen for this device.</p>
      </div>
      <div className="view-selector__options">
        <button className="view-card" onClick={() => onSelect("manager")} type="button">
          <strong>Manager</strong>
          <span>Operations control — tables, orders, robots, and high-level commands.</span>
        </button>
        <button className="view-card" onClick={() => onSelect("customer")} type="button">
          <strong>Customer</strong>
          <span>Browse the menu and place an order from your table.</span>
        </button>
      </div>
    </main>
  );
}
