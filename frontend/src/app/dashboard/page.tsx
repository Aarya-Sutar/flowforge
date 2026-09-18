"use client";

import { useEffect, useState } from "react";
import RequireAuth from "@/components/auth/RequireAuth";
import Card from "@/components/ui/Card";
import ErrorBanner from "@/components/ui/ErrorBanner";
import Spinner from "@/components/ui/Spinner";
import MetricCard from "@/components/dashboard/MetricCard";
import { BarCountChart, PieCountChart, TimeSeriesChart, toNamedCounts } from "@/components/dashboard/Charts";
import * as dashboardService from "@/lib/services/dashboard";
import { describeError } from "@/lib/error-messages";
import type { DashboardMetrics, DashboardSummary } from "@/types/dashboard";

function formatDuration(seconds: number | null): string {
  if (seconds === null) return "—";
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  return `${(seconds / 60).toFixed(1)}m`;
}

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    // Standard data-fetching pattern (react.dev uses this same shape): reset
    // loading/error synchronously before kicking off the fetch below.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(null);

    Promise.all([dashboardService.getSummary(), dashboardService.getMetrics()])
      .then(([summaryData, metricsData]) => {
        if (cancelled) return;
        setSummary(summaryData);
        setMetrics(metricsData);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(describeError(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <RequireAuth>
      <h1 className="mb-6 text-xl font-semibold text-gray-900 dark:text-gray-100">Dashboard</h1>

      {loading && (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      )}

      {error && <ErrorBanner message={error} />}

      {summary && !loading && (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-7">
            <MetricCard label="Total" value={summary.total} />
            <MetricCard label="Pending" value={summary.pending} />
            <MetricCard label="Processing" value={summary.processing} />
            <MetricCard label="Needs Info" value={summary.needs_information} />
            <MetricCard label="Manual Review" value={summary.manual_review} />
            <MetricCard label="Completed" value={summary.completed} />
            <MetricCard label="Failed" value={summary.failed} />
          </div>

          <div className="mt-4">
            <MetricCard label="Avg. processing time" value={formatDuration(summary.average_processing_time_seconds)} />
          </div>
        </>
      )}

      {metrics && !loading && (
        <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Card title="Requests by category">
            <BarCountChart data={toNamedCounts(metrics.requests_by_category, "category")} />
          </Card>
          <Card title="Requests by status">
            <BarCountChart data={toNamedCounts(metrics.requests_by_status, "status")} />
          </Card>
          <Card title="Priority distribution">
            <PieCountChart data={toNamedCounts(metrics.priority_distribution, "priority")} />
          </Card>
          <Card title="Processing success vs. failure">
            <PieCountChart
              data={[
                { name: "Succeeded", count: metrics.processing_succeeded },
                { name: "Failed", count: metrics.processing_failed },
              ]}
            />
          </Card>
          <Card title="Requests over time (last 14 days)" className="lg:col-span-2">
            <TimeSeriesChart data={metrics.requests_over_time} />
          </Card>
        </div>
      )}
    </RequireAuth>
  );
}
