import Button from "@/components/ui/Button";

export default function Pagination({
  page,
  pages,
  total,
  onPageChange,
}: {
  page: number;
  pages: number;
  total: number;
  onPageChange: (page: number) => void;
}) {
  if (pages <= 1) return null;

  return (
    <div className="flex items-center justify-between border-t border-gray-200 pt-3 text-sm text-gray-600 dark:border-gray-800 dark:text-gray-400">
      <span>
        Page {page} of {pages} ({total} total)
      </span>
      <div className="flex gap-2">
        <Button variant="secondary" onClick={() => onPageChange(page - 1)} disabled={page <= 1}>
          Previous
        </Button>
        <Button variant="secondary" onClick={() => onPageChange(page + 1)} disabled={page >= pages}>
          Next
        </Button>
      </div>
    </div>
  );
}
