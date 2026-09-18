export default function ConfidenceNote({ confidence }: { confidence: number | null }) {
  if (confidence === null) return <span className="text-sm text-gray-400">—</span>;
  return (
    <div>
      <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{(confidence * 100).toFixed(0)}%</span>
      <p className="mt-0.5 text-xs text-gray-400 dark:text-gray-600">
        A heuristic score, not a calibrated probability — see the AI Pipeline docs.
      </p>
    </div>
  );
}
