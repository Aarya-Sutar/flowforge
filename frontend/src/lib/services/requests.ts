import { apiFetch } from "@/lib/api";
import type { Page } from "@/types/pagination";
import type {
  AuditLogEntry,
  BusinessRequest,
  BusinessRequestDetail,
  RequestCreatePayload,
  RequestUpdatePayload,
  WorkflowTask,
} from "@/types/request";

export interface RequestListParams {
  status?: string;
  category?: string;
  priority?: string;
  department?: string;
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_order?: "asc" | "desc";
}

function buildQuery(params: object): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

export function listRequests(params: RequestListParams = {}): Promise<Page<BusinessRequest>> {
  return apiFetch<Page<BusinessRequest>>(`/api/requests${buildQuery(params)}`);
}

export function getRequest(id: string): Promise<BusinessRequestDetail> {
  return apiFetch<BusinessRequestDetail>(`/api/requests/${id}`);
}

export function createRequest(payload: RequestCreatePayload): Promise<BusinessRequest> {
  return apiFetch<BusinessRequest>("/api/requests", { method: "POST", body: JSON.stringify(payload) });
}

export function updateRequest(id: string, payload: RequestUpdatePayload): Promise<BusinessRequest> {
  return apiFetch<BusinessRequest>(`/api/requests/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function retryRequest(id: string): Promise<BusinessRequest> {
  return apiFetch<BusinessRequest>(`/api/requests/${id}/retry`, { method: "POST" });
}

export function getRequestTimeline(id: string): Promise<AuditLogEntry[]> {
  return apiFetch<AuditLogEntry[]>(`/api/requests/${id}/timeline`);
}

export function getRequestTasks(id: string): Promise<WorkflowTask[]> {
  return apiFetch<WorkflowTask[]>(`/api/requests/${id}/tasks`);
}
