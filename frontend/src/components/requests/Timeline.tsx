import type { AuditLogEntry } from "@/types/request";

export default function Timeline({ events }: { events: AuditLogEntry[] }) {
  if (events.length === 0) {
    return <p className="text-sm text-gray-400">No events yet.</p>;
  }

  return (
    <ol className="space-y-4">
      {events.map((event, index) => (
        <li key={event.id} className="relative pl-6">
          <span
            className={`absolute left-0 top-1 h-2.5 w-2.5 rounded-full ${
              event.event_type.includes("FAILED") ? "bg-red-500" : "bg-gray-400 dark:bg-gray-600"
            }`}
          />
          {index !== events.length - 1 && (
            <span className="absolute left-[4.5px] top-3.5 h-full w-px bg-gray-200 dark:bg-gray-800" />
          )}
          <p className="text-xs font-mono text-gray-400 dark:text-gray-600">
            {new Date(event.created_at).toLocaleString()}
          </p>
          <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{event.event_type.replace(/_/g, " ")}</p>
          <p className="text-sm text-gray-600 dark:text-gray-400">{event.description}</p>
        </li>
      ))}
    </ol>
  );
}
