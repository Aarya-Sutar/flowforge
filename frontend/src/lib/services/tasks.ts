import { apiFetch } from "@/lib/api";
import type { Page } from "@/types/pagination";
import type { TaskStatus, WorkflowTaskWithRequest } from "@/types/request";

export interface TaskListParams {
  status?: TaskStatus;
  assigned_team?: string;
  page?: number;
  page_size?: number;
}

function buildQuery(params: object): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

export function listTasks(params: TaskListParams = {}): Promise<Page<WorkflowTaskWithRequest>> {
  return apiFetch<Page<WorkflowTaskWithRequest>>(`/api/tasks${buildQuery(params)}`);
}

export function updateTaskStatus(id: string, status: TaskStatus): Promise<WorkflowTaskWithRequest> {
  return apiFetch<WorkflowTaskWithRequest>(`/api/tasks/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}
