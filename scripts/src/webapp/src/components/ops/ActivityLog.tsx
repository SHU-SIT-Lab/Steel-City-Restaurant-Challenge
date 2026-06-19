import { formatFirestoreTime } from "../../lib/firestore/converters";
import type { Event } from "../../types/firestore";

interface ActivityLogProps {
  events: Event[];
}

export function ActivityLog({ events }: ActivityLogProps) {
  return (
    <section className="panel">
      <div className="panel__header">
        <h2>Activity Log</h2>
        <span>{events.length} events</span>
      </div>
      <div className="activity-list">
        {events.map((event) => (
          <article className={`activity-item activity-item--${event.severity}`} key={event.id}>
            <span>{formatFirestoreTime(event.created_at._seconds)}</span>
            <strong>{event.message}</strong>
            <small>
              {event.entity_type}
              {event.entity_id ? `:${event.entity_id}` : ""}
            </small>
          </article>
        ))}
      </div>
    </section>
  );
}
