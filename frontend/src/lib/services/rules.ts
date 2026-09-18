import { apiFetch } from "@/lib/api";
import type { RuleCreatePayload, RuleUpdatePayload, WorkflowRule } from "@/types/rule";

export function listRules(): Promise<WorkflowRule[]> {
  return apiFetch<WorkflowRule[]>("/api/rules");
}

export function createRule(payload: RuleCreatePayload): Promise<WorkflowRule> {
  return apiFetch<WorkflowRule>("/api/rules", { method: "POST", body: JSON.stringify(payload) });
}

export function updateRule(id: string, payload: RuleUpdatePayload): Promise<WorkflowRule> {
  return apiFetch<WorkflowRule>(`/api/rules/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}
