"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import RequireAuth from "@/components/auth/RequireAuth";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import ErrorBanner from "@/components/ui/ErrorBanner";
import { SelectField, InputField } from "@/components/ui/Field";
import Pagination from "@/components/ui/Pagination";
import Spinner from "@/components/ui/Spinner";
import StatusBadge from "@/components/ui/StatusBadge";
import { describeError } from "@/lib/error-messages";
import * as requestsService from "@/lib/services/requests";
import type { BusinessRequest } from "@/types/request";
import type { Page } from "@/types/pagination";

const STATUS_OPTIONS = ["PENDING", "PROCESSING", "NEEDS_INFORMATION", "MANUAL_REVIEW", "COMPLETED", "FAILED"];
const CATEGORY_OPTIONS = ["IT_SUPPORT", "HR", "FINANCE", "PROCUREMENT", "CUSTOMER_SERVICE", "ACCESS_REQUEST", "GENERAL"];
const PRIORITY_OPTIONS = ["LOW", "MEDIUM", "HIGH", "URGENT"];

function RequestsPageContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // Filters live in the URL, not component state — this is what makes
  // /requests?status=MANUAL_REVIEW a real, shareable/bookmarkable link
  // rather than something only reachable by clicking through the UI.
  const status = searchParams.get("status") ?? "";
  const category = searchParams.get("category") ?? "";
  const priority = searchParams.get("priority") ?? "";
  const department = searchParams.get("department") ?? "";
  const sortBy = searchParams.get("sort_by") ?? "created_at";
  const sortOrder = (searchParams.get("sort_order") as "asc" | "desc") ?? "desc";
  const page = Number(searchParams.get("page") ?? "1");

  const [data, setData] = useState<Page<BusinessRequest> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  function updateParams(updates: Record<string, string | number>, resetPage = false) {
    const next = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(updates)) {
      if (value === "" || value === undefined) next.delete(key);
      else next.set(key, String(value));
    }
    if (resetPage) next.delete("page");
    router.replace(`${pathname}?${next.toString()}`);
  }

  useEffect(() => {
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- see dashboard/page.tsx
    setLoading(true);
    setError(null);

    requestsService
      .listRequests({ status, category, priority, department, sort_by: sortBy, sort_order: sortOrder, page, page_size: 15 })
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(describeError(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [status, category, priority, department, sortBy, sortOrder, page]);

  return (
    <>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Requests</h1>
        <Link href="/requests/new">
          <Button>New request</Button>
        </Link>
      </div>

      <Card className="mb-6">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          <SelectField label="Status" value={status} onChange={(e) => updateParams({ status: e.target.value }, true)}>
            <option value="">All</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s.replace(/_/g, " ")}
              </option>
            ))}
          </SelectField>
          <SelectField label="Category" value={category} onChange={(e) => updateParams({ category: e.target.value }, true)}>
            <option value="">All</option>
            {CATEGORY_OPTIONS.map((c) => (
              <option key={c} value={c}>
                {c.replace(/_/g, " ")}
              </option>
            ))}
          </SelectField>
          <SelectField label="Priority" value={priority} onChange={(e) => updateParams({ priority: e.target.value }, true)}>
            <option value="">All</option>
            {PRIORITY_OPTIONS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </SelectField>
          <InputField
            label="Department"
            placeholder="Search..."
            value={department}
            onChange={(e) => updateParams({ department: e.target.value }, true)}
          />
          <SelectField
            label="Sort by"
            value={`${sortBy}:${sortOrder}`}
            onChange={(e) => {
              const [field, order] = e.target.value.split(":");
              updateParams({ sort_by: field, sort_order: order });
            }}
          >
            <option value="created_at:desc">Newest first</option>
            <option value="created_at:asc">Oldest first</option>
            <option value="priority:desc">Priority (high-low)</option>
            <option value="status:asc">Status</option>
          </SelectField>
        </div>
      </Card>

      {error && <ErrorBanner message={error} />}

      {loading ? (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      ) : data && data.items.length === 0 ? (
        <Card>
          <p className="text-sm text-gray-500 dark:text-gray-400">No requests match these filters.</p>
        </Card>
      ) : (
        data && (
          <Card>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-xs uppercase tracking-wide text-gray-500 dark:border-gray-800 dark:text-gray-400">
                    <th className="py-2 pr-4">Title</th>
                    <th className="py-2 pr-4">Department</th>
                    <th className="py-2 pr-4">Category</th>
                    <th className="py-2 pr-4">Priority</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2 pr-4">Assigned team</th>
                    <th className="py-2 pr-4">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((request) => (
                    <tr
                      key={request.id}
                      className="border-b border-gray-100 last:border-0 hover:bg-gray-50 dark:border-gray-900 dark:hover:bg-gray-800/50"
                    >
                      <td className="py-2.5 pr-4">
                        <Link href={`/requests/${request.id}`} className="font-medium text-gray-900 hover:underline dark:text-gray-100">
                          {request.title}
                        </Link>
                      </td>
                      <td className="py-2.5 pr-4 text-gray-600 dark:text-gray-400">{request.department}</td>
                      <td className="py-2.5 pr-4">
                        <StatusBadge value={request.category} />
                      </td>
                      <td className="py-2.5 pr-4">
                        <StatusBadge value={request.priority} />
                      </td>
                      <td className="py-2.5 pr-4">
                        <StatusBadge value={request.status} />
                      </td>
                      <td className="py-2.5 pr-4 text-gray-600 dark:text-gray-400">{request.assigned_team ?? "—"}</td>
                      <td className="py-2.5 pr-4 text-gray-500 dark:text-gray-500">
                        {new Date(request.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-4">
              <Pagination page={data.page} pages={data.pages} total={data.total} onPageChange={(p) => updateParams({ page: p })} />
            </div>
          </Card>
        )
      )}
    </>
  );
}

export default function RequestsPage() {
  return (
    <RequireAuth>
      <Suspense fallback={<Spinner />}>
        <RequestsPageContent />
      </Suspense>
    </RequireAuth>
  );
}
