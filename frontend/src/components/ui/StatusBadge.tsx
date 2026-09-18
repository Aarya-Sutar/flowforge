const STATUS_COLORS: Record<string, string> = {
  PENDING: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  PROCESSING: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  QUEUED: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  IN_PROGRESS: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  NEEDS_INFORMATION: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  MANUAL_REVIEW: "bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-300",
  COMPLETED: "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300",
  DONE: "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300",
  FAILED: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
  OPEN: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  LOW: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
  MEDIUM: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  HIGH: "bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-300",
  URGENT: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
};

export default function StatusBadge({ value }: { value: string | null | undefined }) {
  if (!value) {
    return <span className="text-xs text-gray-400">—</span>;
  }
  const colorClasses = STATUS_COLORS[value] ?? "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300";
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${colorClasses}`}>
      {value.replace(/_/g, " ")}
    </span>
  );
}
