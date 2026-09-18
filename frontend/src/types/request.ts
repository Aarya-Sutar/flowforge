export type RequestStatus =
  | "PENDING"
  | "PROCESSING"
  | "NEEDS_INFORMATION"
  | "MANUAL_REVIEW"
  | "COMPLETED"
  | "FAILED";

export type ProcessingStatus = "QUEUED" | "IN_PROGRESS" | "COMPLETED" | "FAILED";

export type RequestCategory =
  | "IT_SUPPORT"
  | "HR"
  | "FINANCE"
  | "PROCUREMENT"
  | "CUSTOMER_SERVICE"
  | "ACCESS_REQUEST"
  | "GENERAL";

export type RequestPriority = "LOW" | "MEDIUM" | "HIGH" | "URGENT";

export interface BusinessRequest {
  id: string;
  requester_id: string;
  title: string;
  description: string;
  normalized_description: string | null;
  department: string;
  status: RequestStatus;
  processing_status: ProcessingStatus;
  category: RequestCategory | null;
  subcategory: string | null;
  priority: RequestPriority | null;
  confidence: number | null;
  amount: number | null;
  assigned_team: string | null;
  summary: string | null;
  created_at: string;
  updated_at: string;
}

export interface RequestCreatePayload {
  title: string;
  description: string;
  department: string;
}

export interface ExtractedEntity {
  key: string;
  value: string;
}

export interface BusinessRequestDetail extends BusinessRequest {
  extracted_entities: ExtractedEntity[];
  requester_name: string;
  requester_email: string;
}

export interface RequestUpdatePayload {
  title?: string;
  description?: string;
  department?: string;
  status?: RequestStatus;
}

export interface AuditLogEntry {
  id: string;
  event_type: string;
  actor: string;
  description: string;
  event_metadata: Record<string, unknown> | null;
  created_at: string;
}

export type TaskStatus = "OPEN" | "IN_PROGRESS" | "DONE";

export interface WorkflowTask {
  id: string;
  request_id: string;
  task_type: string;
  assigned_team: string;
  status: TaskStatus;
  priority: RequestPriority | null;
  created_at: string;
  updated_at: string;
}

export interface WorkflowTaskWithRequest extends WorkflowTask {
  request_title: string;
}
