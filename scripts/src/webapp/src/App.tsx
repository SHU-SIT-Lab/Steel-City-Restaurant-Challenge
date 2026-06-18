import { useOpsData } from "./hooks/useOpsData";
import { useView } from "./hooks/useView";
import { CustomerScreen } from "./screens/CustomerScreen";
import { ManagerScreen } from "./screens/ManagerScreen";
import { ViewSelector } from "./screens/ViewSelector";

export default function App() {
  const ops = useOpsData();
  const { view, setView } = useView();

  if (view === "select") {
    return <ViewSelector onSelect={setView} />;
  }

  if (view === "customer") {
    return <CustomerScreen ops={ops} onSwitchView={() => setView("select")} />;
  }

  return <ManagerScreen ops={ops} onSwitchView={() => setView("select")} />;
}
