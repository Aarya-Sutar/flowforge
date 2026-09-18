"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import RequireAuth from "@/components/auth/RequireAuth";
import { useAuth } from "@/contexts/AuthContext";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import ErrorBanner from "@/components/ui/ErrorBanner";
import { SelectField } from "@/components/ui/Field";
import Spinner from "@/components/ui/Spinner";
import StatusBadge from "@/components/ui/StatusBadge";
import ConfidenceNote from "@/components/requests/ConfidenceNote";
import Timeline from "@/components/requests/Timeline";
import { describeError } from "@/lib/error-messages";
import * as requestsService from "@/lib/services/requests";
import type { AuditLogEntry, BusinessRequestDetail, RequestStatus, WorkflowTask } from "@/types/request";

const IN_FLIGHT_PROCESSING_STATUSES = new Set(["QUEUED", "IN_PROGRESS"]);
const STAFF_STATUS_OPTIONS: RequestStatus[] = [
  "PENDING",
  "PROCESSING",
  "NEEDS_INFORMATION",
  "MANUAL_REVIEW",
  "COMPLETED",
  "FAILED",
];

function RequestDetailPage() {
  const params = useParams<{ id: string }>();
  const { user } = useAuth();
  const isStaff = user?.role === "OPERATOR" || user?.role === "ADMIN";

  const [request, setRequest] = useState<BusinessRequestDetail | null>(null);
  const [timeline, setTimeline] = useState<AuditLogEntry[]>([]);
  const [tasks, setTasks] = useState<WorkflowTask[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [statusDraft, setStatusDraft] = useState<RequestStatus | "">("");
  const [savingStatus, setSavingStatus] = useState(false);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    const [requestData, timelineData, tasksData] = await Promise.all([
      requestsService.getRequest(params.id),
      requestsService.getRequestTimeline(params.id),
      requestsService.getRequestTasks(params.id),
    ]);
    setRequest(requestData);
    setTimeline(timelineData);
    setTasks(tasksData);
    return requestData;
  }, [params.id]);

  useEffect(() => {
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- see dashboard/page.tsx
    setLoading(true);
    setError(null);

    load()
      .catch((err: unknown) => {
        if (!cancelled) setError(describeError(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [load]);

  // The request was just created and might still be QUEUED/IN_PROGRESS —
  // poll for updates rather than making the user manually refresh to see
  // the async pipeline's result land.
  useEffect(() => {
    if (!request) return;
    if (!IN_FLIGHT_PROCESSING_STATUSES.has(request.processing_status)) {
      if (pollRef.current) clearInterval(pollRef.current);
      return;
    }
    pollRef.current = setInterval(() => {
      load().catch(() => undefined);
    }, 3000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [request, load]);

  async function handleRetry() {
    setActionError(null);
    setActionMessage(null);
    setRetrying(true);
    try {
      await requestsService.retryRequest(params.id);
      setActionMessage("Reprocessing has been queued.");
      await load();
    } catch (err) {
      setActionError(describeError(err));
    } finally {
      setRetrying(false);
    }
  }

  async function handleStatusSave() {
    if (!statusDraft) return;
    setActionError(null);
    setActionMessage(null);
    setSavingStatus(true);
    try {
      await requestsService.updateRequest(params.id, { status: statusDraft });
      setActionMessage("Status updated.");
      await load();
    } catch (err) {
      setActionError(describeError(err));
    } finally {
      setSavingStatus(false);
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner />
      </div>
    );
  }

  if (error || !request) {
    return <ErrorBanner message={error ?? "Request not found."} />;
  }

  const retryEligible =
    request.processing_status === "FAILED" ||
    request.status === "MANUAL_REVIEW" ||
    request.status === "NEEDS_INFORMATION";

  const triggeredRules = timeline.filter((event) => event.event_type === "RULE_TRIGGERED");

  return (
    <div className="space-y-6">
      <div>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">{request.title}</h1>
          <StatusBadge value={request.status} />
          <StatusBadge value={request.processing_status} />
          {IN_FLIGHT_PROCESSING_STATUSES.has(request.processing_status) && (
            <span className="flex items-center gap-1.5 text-xs text-gray-400">
              <Spinner className="h-3 w-3" /> processing...
            </span>
          )}
        </div>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Submitted by {request.requester_name} ({request.requester_email}) &middot; {request.department} &middot;{" "}
          {new Date(request.created_at).toLocaleString()}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card title="Request information">
          <dl className="space-y-3 text-sm">
            <div>
              <dt className="text-xs font-medium uppercase text-gray-400">Description</dt>
              <dd className="mt-0.5 whitespace-pre-wrap text-gray-800 dark:text-gray-200">{request.description}</dd>
            </div>
            {request.normalized_description && request.normalized_description !== request.description && (
              <div>
                <dt className="text-xs font-medium uppercase text-gray-400">Normalized description</dt>
                <dd className="mt-0.5 whitespace-pre-wrap text-gray-600 dark:text-gray-400">
                  {request.normalized_description}
                </dd>
              </div>
            )}
          </dl>
        </Card>

        <Card title="AI analysis">
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-xs font-medium uppercase text-gray-400">Category</dt>
              <dd className="mt-1">
                <StatusBadge value={request.category} />
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase text-gray-400">Priority</dt>
              <dd className="mt-1">
                <StatusBadge value={request.priority} />
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase text-gray-400">Confidence</dt>
              <dd className="mt-1">
                <ConfidenceNote confidence={request.confidence} />
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase text-gray-400">Amount</dt>
              <dd className="mt-1 text-gray-800 dark:text-gray-200">
                {request.amount !== null ? `$${request.amount.toLocaleString()}` : "—"}
              </dd>
            </div>
            <div className="col-span-2">
              <dt className="text-xs font-medium uppercase text-gray-400">Summary</dt>
              <dd className="mt-1 text-gray-800 dark:text-gray-200">{request.summary ?? "—"}</dd>
            </div>
            <div className="col-span-2">
              <dt className="text-xs font-medium uppercase text-gray-400">Extracted entities</dt>
              <dd className="mt-1">
                {request.extracted_entities.length === 0 ? (
                  <span className="text-gray-400">None</span>
                ) : (
                  <ul className="space-y-1">
                    {request.extracted_entities.map((entity) => (
                      <li key={entity.key} className="text-gray-800 dark:text-gray-200">
                        <span className="font-medium">{entity.key}:</span> {entity.value}
                      </li>
                    ))}
                  </ul>
                )}
              </dd>
            </div>
          </dl>
          <p className="mt-4 border-t border-gray-100 pt-3 text-xs text-gray-400 dark:border-gray-800">
            This section shows what the AI produced — the workflow section below shows what the deterministic rule
            engine decided to do about it. They are not the same thing.
          </p>
        </Card>

        <Card title="Workflow">
          <dl className="space-y-3 text-sm">
            <div>
              <dt className="text-xs font-medium uppercase text-gray-400">Assigned team</dt>
              <dd className="mt-0.5 text-gray-800 dark:text-gray-200">{request.assigned_team ?? "Not yet assigned"}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase text-gray-400">Tasks</dt>
              <dd className="mt-1 space-y-2">
                {tasks.length === 0 ? (
                  <span className="text-gray-400">No tasks created</span>
                ) : (
                  tasks.map((task) => (
                    <div key={task.id} className="flex items-center gap-2 text-gray-800 dark:text-gray-200">
                      <StatusBadge value={task.status} />
                      <span>{task.task_type.replace(/_/g, " ")}</span>
                      <span className="text-gray-400">→ {task.assigned_team}</span>
                    </div>
                  ))
                )}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase text-gray-400">Triggered rules</dt>
              <dd className="mt-1 space-y-1">
                {triggeredRules.length === 0 ? (
                  <span className="text-gray-400">None yet</span>
                ) : (
                  triggeredRules.map((rule) => (
                    <p key={rule.id} className="text-gray-800 dark:text-gray-200">
                      {rule.description}
                    </p>
                  ))
                )}
              </dd>
            </div>
          </dl>
        </Card>

        <Card title="Audit timeline">
          <Timeline events={timeline} />
        </Card>
      </div>

      {isStaff && (
        <Card title="Staff actions">
          <p className="mb-4 text-xs text-gray-400 dark:text-gray-600">
            Actions here are human-confirmed decisions, distinct from the AI-generated analysis above.
          </p>
          {actionError && (
            <div className="mb-3">
              <ErrorBanner message={actionError} />
            </div>
          )}
          {actionMessage && <p className="mb-3 text-sm text-green-700 dark:text-green-400">{actionMessage}</p>}

          <div className="flex flex-wrap items-end gap-4">
            <div className="w-48">
              <SelectField
                label="Set status"
                value={statusDraft}
                onChange={(e) => setStatusDraft(e.target.value as RequestStatus)}
              >
                <option value="">Choose...</option>
                {STAFF_STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {s.replace(/_/g, " ")}
                  </option>
                ))}
              </SelectField>
            </div>
            <Button variant="secondary" onClick={handleStatusSave} loading={savingStatus} disabled={!statusDraft}>
              Save status
            </Button>
            <Button onClick={handleRetry} loading={retrying} disabled={!retryEligible} title={!retryEligible ? "Only FAILED, MANUAL_REVIEW, or NEEDS_INFORMATION requests can be retried" : undefined}>
              Retry processing
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <RequestDetailPage />
    </RequireAuth>
  );
}
