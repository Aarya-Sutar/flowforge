export interface HealthStatus {
  status: "ok" | "degraded";
  database: "up" | "down";
}
