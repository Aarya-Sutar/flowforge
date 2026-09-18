export default function Card({
  title,
  children,
  className = "",
}: {
  title?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`rounded-lg border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900 ${className}`}>
      {title && <h2 className="mb-3 text-sm font-semibold text-gray-900 dark:text-gray-100">{title}</h2>}
      {children}
    </div>
  );
}
