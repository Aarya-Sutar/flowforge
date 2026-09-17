"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import type { HealthStatus } from "@/types/health";

type LoadState =
  | { kind: "loading" }
  | { kind: "success"; data: HealthStatus }
  | { kind: "error"; message: string };

export default function BackendStatus() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;

    apiFetch<HealthStatus>("/api/health")
      .then((data) => {
        if (!cancelled) setState({ kind: "success", data });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        const message = error instanceof ApiError ? error.message : "Could not reach the backend API";
        setState({ kind: "error", message });
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (state.kind === "loading") {
    return <StatusCard color="bg-gray-400" title="Checking backend..." detail="Contacting FastAPI" />;
  }

  if (state.kind === "error") {
    return <StatusCard color="bg-red-500" title="Backend unreachable" detail={state.message} />;
  }

  const isHealthy = state.data.status === "ok";

  return (
    <StatusCard
      color={isHealthy ? "bg-green-500" : "bg-yellow-500"}
      title={isHealthy ? "Backend healthy" : "Backend degraded"}
      detail={`FastAPI reports database: ${state.data.database}`}
    />
  );
}

function StatusCard({ color, title, detail }: { color: string; title: string; detail: string }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
      <span className={`h-3 w-3 flex-shrink-0 rounded-full ${color}`} />
      <div>
        <p className="font-medium text-gray-900 dark:text-gray-100">{title}</p>
        <p className="text-sm text-gray-500 dark:text-gray-400">{detail}</p>
      </div>
    </div>
  );
}
