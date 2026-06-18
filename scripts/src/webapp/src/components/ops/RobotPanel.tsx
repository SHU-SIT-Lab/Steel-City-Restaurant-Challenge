import { formatFirestoreTime } from "../../lib/firestore/converters";
import type { Robot, Task } from "../../types/firestore";

interface RobotPanelProps {
  robot: Robot;
  tasks: Task[];
}

export function RobotPanel({ robot, tasks }: RobotPanelProps) {
  const currentTask = robot.current_task
    ? tasks.find((task) => task.id === robot.current_task)
    : tasks.find((task) => task.status === "queued" || task.status === "running");

  return (
    <section className="panel">
      <div className="panel__header">
        <h2>Robot</h2>
        <span className={`tag tag--${robot.status}`}>{robot.status}</span>
      </div>
      <div className="robot-card">
        <div>
          <strong>{robot.name}</strong>
          <span>{robot.model}</span>
        </div>
        <div className="battery">
          <span style={{ width: `${robot.battery_pct}%` }} />
        </div>
        <dl>
          <div>
            <dt>Battery</dt>
            <dd>{robot.battery_pct}%</dd>
          </div>
          <div>
            <dt>Location</dt>
            <dd>{robot.current_location}</dd>
          </div>
          <div>
            <dt>Task</dt>
            <dd>{currentTask?.current_step ?? "No active task"}</dd>
          </div>
          <div>
            <dt>Last seen</dt>
            <dd>{formatFirestoreTime(robot.last_seen._seconds)}</dd>
          </div>
        </dl>
      </div>
    </section>
  );
}
