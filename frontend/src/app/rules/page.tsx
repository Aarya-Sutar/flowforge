"use client";

import { useEffect, useState } from "react";
import RequireAuth from "@/components/auth/RequireAuth";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import ErrorBanner from "@/components/ui/ErrorBanner";
import { InputField, SelectField, TextareaField } from "@/components/ui/Field";
import Spinner from "@/components/ui/Spinner";
import { describeError } from "@/lib/error-messages";
import * as rulesService from "@/lib/services/rules";
import type { RuleCreatePayload, WorkflowRule } from "@/types/rule";

const CATEGORY_OPTIONS = ["IT_SUPPORT", "HR", "FINANCE", "PROCUREMENT", "CUSTOMER_SERVICE", "ACCESS_REQUEST", "GENERAL"];

const EMPTY_FORM: RuleCreatePayload = {
  name: "",
  description: "",
  category: "",
  condition: "",
  action: "",
  enabled: true,
};

function RulesPageContent() {
  const [rules, setRules] = useState<WorkflowRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [form, setForm] = useState<RuleCreatePayload>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  async function reload() {
    try {
      setRules(await rulesService.listRules());
    } catch (err) {
      setError(describeError(err));
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- see dashboard/page.tsx
    setLoading(true);
    reload().finally(() => setLoading(false));
  }, []);

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    setFormError(null);
    setSubmitting(true);
    try {
      await rulesService.createRule({ ...form, category: form.category || null });
      setForm(EMPTY_FORM);
      await reload();
    } catch (err) {
      setFormError(describeError(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggle(rule: WorkflowRule) {
    setTogglingId(rule.id);
    try {
      await rulesService.updateRule(rule.id, { enabled: !rule.enabled });
      await reload();
    } catch (err) {
      setError(describeError(err));
    } finally {
      setTogglingId(null);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Workflow rules</h1>

      <Card title="Create a rule">
        <form onSubmit={handleCreate} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {formError && (
            <div className="sm:col-span-2">
              <ErrorBanner message={formError} />
            </div>
          )}
          <InputField label="Name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <SelectField
            label="Category (optional — applies to all if unset)"
            value={form.category ?? ""}
            onChange={(e) => setForm({ ...form, category: e.target.value })}
          >
            <option value="">All categories</option>
            {CATEGORY_OPTIONS.map((c) => (
              <option key={c} value={c}>
                {c.replace(/_/g, " ")}
              </option>
            ))}
          </SelectField>
          <div className="sm:col-span-2">
            <TextareaField
              label="Description"
              rows={2}
              value={form.description ?? ""}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </div>
          <InputField
            label="Condition"
            required
            placeholder="priority == HIGH"
            hint='Comparisons joined by " AND " — e.g. category == FINANCE AND amount &gt; 100000'
            value={form.condition}
            onChange={(e) => setForm({ ...form, condition: e.target.value })}
          />
          <InputField
            label="Action"
            required
            placeholder="assign_team = IT Security Team"
            hint="assign_team = ... | status = ... | require_approval = true | mark_urgent = true"
            value={form.action}
            onChange={(e) => setForm({ ...form, action: e.target.value })}
          />
          <div className="sm:col-span-2">
            <Button type="submit" loading={submitting}>
              Create rule
            </Button>
          </div>
        </form>
      </Card>

      {error && <ErrorBanner message={error} />}

      {loading ? (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-xs uppercase tracking-wide text-gray-500 dark:border-gray-800 dark:text-gray-400">
                  <th className="py-2 pr-4">Name</th>
                  <th className="py-2 pr-4">Category</th>
                  <th className="py-2 pr-4">Condition</th>
                  <th className="py-2 pr-4">Action</th>
                  <th className="py-2 pr-4">Enabled</th>
                </tr>
              </thead>
              <tbody>
                {rules.map((rule) => (
                  <tr key={rule.id} className="border-b border-gray-100 last:border-0 dark:border-gray-900">
                    <td className="py-2.5 pr-4 font-medium text-gray-900 dark:text-gray-100">{rule.name}</td>
                    <td className="py-2.5 pr-4 text-gray-600 dark:text-gray-400">{rule.category ?? "All"}</td>
                    <td className="py-2.5 pr-4 font-mono text-xs text-gray-600 dark:text-gray-400">{rule.condition}</td>
                    <td className="py-2.5 pr-4 font-mono text-xs text-gray-600 dark:text-gray-400">{rule.action}</td>
                    <td className="py-2.5 pr-4">
                      <button
                        onClick={() => handleToggle(rule)}
                        disabled={togglingId === rule.id}
                        className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                          rule.enabled
                            ? "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300"
                            : "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400"
                        }`}
                      >
                        {rule.enabled ? "Enabled" : "Disabled"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}

export default function RulesPage() {
  return (
    <RequireAuth roles={["ADMIN"]}>
      <RulesPageContent />
    </RequireAuth>
  );
}
