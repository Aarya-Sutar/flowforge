export interface DashboardSummary {
  total: number;
  pending: number;
  processing: number;
  needs_information: number;
  manual_review: number;
  completed: number;
  failed: number;
  average_processing_time_seconds: number | null;
}

export interface CategoryCount {
  category: string | null;
  count: number;
}

export interface StatusCount {
  status: string;
  count: number;
}

export interface PriorityCount {
  priority: string | null;
  count: number;
}

export interface DailyCount {
  date: string;
  count: number;
}

export interface DashboardMetrics {
  requests_by_category: CategoryCount[];
  requests_by_status: StatusCount[];
  priority_distribution: PriorityCount[];
  processing_succeeded: number;
  processing_failed: number;
  requests_over_time: DailyCount[];
}
