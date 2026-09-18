"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const AXIS_COLOR = "#6b7280";
const GRID_COLOR = "#e5e7eb";
const BAR_COLOR = "#4f46e5";
const PIE_COLORS = ["#4f46e5", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"];

interface NamedCount {
  name: string;
  count: number;
}

function formatLabel(value: string | null): string {
  return value ? value.replace(/_/g, " ") : "Unclassified";
}

export function BarCountChart({ data }: { data: NamedCount[] }) {
  if (data.length === 0) {
    return <EmptyState />;
  }
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} vertical={false} />
        <XAxis dataKey="name" tick={{ fontSize: 11, fill: AXIS_COLOR }} interval={0} angle={-20} textAnchor="end" height={50} />
        <YAxis tick={{ fontSize: 11, fill: AXIS_COLOR }} allowDecimals={false} />
        <Tooltip contentStyle={{ fontSize: 12, borderRadius: 6 }} />
        <Bar dataKey="count" fill={BAR_COLOR} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function PieCountChart({ data }: { data: NamedCount[] }) {
  if (data.length === 0) {
    return <EmptyState />;
  }
  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie
          data={data}
          dataKey="count"
          nameKey="name"
          outerRadius={80}
          label={(entry: { name?: string; value?: number }) => `${entry.name}: ${entry.value}`}
        >
          {data.map((entry, index) => (
            <Cell key={entry.name} fill={PIE_COLORS[index % PIE_COLORS.length]} />
          ))}
        </Pie>
        <Tooltip contentStyle={{ fontSize: 12, borderRadius: 6 }} />
      </PieChart>
    </ResponsiveContainer>
  );
}

export function TimeSeriesChart({ data }: { data: { date: string; count: number }[] }) {
  if (data.length === 0) {
    return <EmptyState />;
  }
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} vertical={false} />
        <XAxis dataKey="date" tick={{ fontSize: 11, fill: AXIS_COLOR }} />
        <YAxis tick={{ fontSize: 11, fill: AXIS_COLOR }} allowDecimals={false} />
        <Tooltip contentStyle={{ fontSize: 12, borderRadius: 6 }} />
        <Line type="monotone" dataKey="count" stroke={BAR_COLOR} strokeWidth={2} dot={{ r: 3 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function EmptyState() {
  return (
    <div className="flex h-[220px] items-center justify-center text-sm text-gray-400 dark:text-gray-600">
      No data yet
    </div>
  );
}

export function toNamedCounts<T extends { count: number }>(entries: T[], key: keyof T): NamedCount[] {
  return entries.map((entry) => ({
    name: formatLabel(entry[key] as string | null),
    count: entry.count,
  }));
}
