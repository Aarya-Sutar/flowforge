"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import RequireAuth from "@/components/auth/RequireAuth";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import ErrorBanner from "@/components/ui/ErrorBanner";
import { InputField, TextareaField } from "@/components/ui/Field";
import { ApiError } from "@/lib/api";
import { describeError } from "@/lib/error-messages";
import * as requestsService from "@/lib/services/requests";

interface FormState {
  title: string;
  description: string;
  department: string;
}

const EMPTY_FORM: FormState = { title: "", description: "", department: "" };

function validate(form: FormState): Record<string, string> {
  const errors: Record<string, string> = {};
  if (form.title.trim().length === 0) errors.title = "Title is required.";
  if (form.description.trim().length === 0) errors.description = "Description is required.";
  if (form.department.trim().length === 0) errors.department = "Department is required.";
  return errors;
}

export default function NewRequestPage() {
  const router = useRouter();
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    const errors = validate(form);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setSubmitting(true);
    try {
      const created = await requestsService.createRequest(form);
      setSuccess(true);
      // The API returns as soon as the request is queued — it does not wait
      // for the AI pipeline to run. We navigate to the detail page immediately;
      // that page polls for status updates as processing happens in the background.
      setTimeout(() => router.push(`/requests/${created.id}`), 600);
    } catch (err) {
      if (err instanceof ApiError && err.fieldErrors) {
        setFieldErrors(err.fieldErrors);
      } else {
        setError(describeError(err));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <RequireAuth>
      <h1 className="mb-6 text-xl font-semibold text-gray-900 dark:text-gray-100">New request</h1>

      <Card className="max-w-xl">
        {success ? (
          <div className="rounded-md border border-green-300 bg-green-50 px-4 py-3 text-sm text-green-800 dark:border-green-900 dark:bg-green-950 dark:text-green-200">
            Request submitted — it&apos;s now queued for processing. Redirecting...
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && <ErrorBanner message={error} />}
            <InputField
              label="Title"
              required
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              error={fieldErrors.title}
            />
            <TextareaField
              label="Description"
              required
              rows={5}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              error={fieldErrors.description}
              hint="Describe the issue or request in as much detail as possible — this is what gets classified."
            />
            <InputField
              label="Department"
              required
              value={form.department}
              onChange={(e) => setForm({ ...form, department: e.target.value })}
              error={fieldErrors.department}
            />
            <p className="text-xs text-gray-500 dark:text-gray-400">
              File attachments are not yet supported — see the project docs for why.
            </p>
            <Button type="submit" loading={submitting}>
              Submit request
            </Button>
          </form>
        )}
      </Card>
    </RequireAuth>
  );
}
