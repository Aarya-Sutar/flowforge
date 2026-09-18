import { apiFetch } from "@/lib/api";
import type { DashboardMetrics, DashboardSummary } from "@/types/dashboard";

export function getSummary(): Promise<DashboardSummary> {
  return apiFetch<DashboardSummary>("/api/dashboard/summary");
}

export function getMetrics(): Promise<DashboardMetrics> {
  return apiFetch<DashboardMetrics>("/api/dashboard/metrics");
}
