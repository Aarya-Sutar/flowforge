"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import RequireAuth from "@/components/auth/RequireAuth";
import Card from "@/components/ui/Card";
import ErrorBanner from "@/components/ui/ErrorBanner";
import { SelectField, InputField } from "@/components/ui/Field";
import Pagination from "@/components/ui/Pagination";
import Spinner from "@/components/ui/Spinner";
import StatusBadge from "@/components/ui/StatusBadge";
import { describeError } from "@/lib/error-messages";
import * as taskService from "@/lib/services/tasks";
import type { Page } from "@/types/pagination";
import type { TaskStatus, WorkflowTaskWithRequest } from "@/types/request";

const STATUS_OPTIONS: TaskStatus[] = ["OPEN", "IN_PROGRESS", "DONE"];

function TasksPageContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const status = (searchParams.get("status") as TaskStatus | null) ?? "";
  const team = searchParams.get("assigned_team") ?? "";
  const page = Number(searchParams.get("page") ?? "1");

  const [data, setData] = useState<Page<WorkflowTaskWithRequest> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  function updateParams(updates: Record<string, string | number>, resetPage = false) {
    const next = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(updates)) {
      if (value === "" || value === undefined) next.delete(key);
      else next.set(key, String(value));
    }
    if (resetPage) next.delete("page");
    router.replace(`${pathname}?${next.toString()}`);
  }

  async function reload() {
    setError(null);
    try {
      const result = await taskService.listTasks({
        status: status || undefined,
        assigned_team: team || undefined,
        page,
        page_size: 15,
      });
      setData(result);
    } catch (err) {
      setError(describeError(err));
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- see dashboard/page.tsx
    setLoading(true);
    reload().finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, team, page]);

  async function handleStatusChange(taskId: string, newStatus: TaskStatus) {
    setUpdatingId(taskId);
    try {
      await taskService.updateTaskStatus(taskId, newStatus);
      await reload();
    } catch (err) {
      setError(describeError(err));
    } finally {
      setUpdatingId(null);
    }
  }

  return (
    <div>
      <h1 className="mb-6 text-xl font-semibold text-gray-900 dark:text-gray-100">Tasks</h1>

      <Card className="mb-6">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <SelectField
            label="Status"
            value={status}
            onChange={(e) => updateParams({ status: e.target.value }, true)}
          >
            <option value="">All</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s.replace(/_/g, " ")}
              </option>
            ))}
          </SelectField>
          <InputField
            label="Team"
            placeholder="Search..."
            value={team}
            onChange={(e) => updateParams({ assigned_team: e.target.value }, true)}
          />
        </div>
      </Card>

      {error && <ErrorBanner message={error} />}

      {loading ? (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      ) : data && data.items.length === 0 ? (
        <Card>
          <p className="text-sm text-gray-500 dark:text-gray-400">No tasks match these filters.</p>
        </Card>
      ) : (
        data && (
          <Card>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-xs uppercase tracking-wide text-gray-500 dark:border-gray-800 dark:text-gray-400">
                    <th className="py-2 pr-4">Request</th>
                    <th className="py-2 pr-4">Type</th>
                    <th className="py-2 pr-4">Team</th>
                    <th className="py-2 pr-4">Priority</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2 pr-4">Update</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((task) => (
                    <tr key={task.id} className="border-b border-gray-100 last:border-0 dark:border-gray-900">
                      <td className="py-2.5 pr-4">
                        <Link href={`/requests/${task.request_id}`} className="font-medium text-gray-900 hover:underline dark:text-gray-100">
                          {task.request_title}
                        </Link>
                      </td>
                      <td className="py-2.5 pr-4 text-gray-600 dark:text-gray-400">{task.task_type.replace(/_/g, " ")}</td>
                      <td className="py-2.5 pr-4 text-gray-600 dark:text-gray-400">{task.assigned_team}</td>
                      <td className="py-2.5 pr-4">
                        <StatusBadge value={task.priority} />
                      </td>
                      <td className="py-2.5 pr-4">
                        <StatusBadge value={task.status} />
                      </td>
                      <td className="py-2.5 pr-4">
                        <select
                          className="rounded-md border border-gray-300 bg-white px-2 py-1 text-xs dark:border-gray-700 dark:bg-gray-900"
                          value={task.status}
                          disabled={updatingId === task.id}
                          onChange={(e) => handleStatusChange(task.id, e.target.value as TaskStatus)}
                        >
                          {STATUS_OPTIONS.map((s) => (
                            <option key={s} value={s}>
                              {s.replace(/_/g, " ")}
                            </option>
                          ))}
                        </select>
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
    </div>
  );
}

export default function TasksPage() {
  return (
    <RequireAuth roles={["OPERATOR", "ADMIN"]}>
      <Suspense fallback={<Spinner />}>
        <TasksPageContent />
      </Suspense>
    </RequireAuth>
  );
}
