export interface WorkflowRule {
  id: string;
  name: string;
  description: string | null;
  category: string | null;
  condition: string;
  action: string;
  enabled: boolean;
  created_at: string;
}

export interface RuleCreatePayload {
  name: string;
  description?: string | null;
  category?: string | null;
  condition: string;
  action: string;
  enabled: boolean;
}

export interface RuleUpdatePayload {
  name?: string;
  description?: string | null;
  category?: string | null;
  condition?: string;
  action?: string;
  enabled?: boolean;
}
