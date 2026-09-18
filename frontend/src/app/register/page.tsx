"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { ApiError } from "@/lib/api";
import { describeError } from "@/lib/error-messages";
import Button from "@/components/ui/Button";
import { InputField } from "@/components/ui/Field";
import ErrorBanner from "@/components/ui/ErrorBanner";

export default function RegisterPage() {
  const { user, register, isInitializing } = useAuth();
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!isInitializing && user) router.replace("/dashboard");
  }, [isInitializing, user, router]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setFieldErrors({});

    if (password.length < 8) {
      setFieldErrors({ password: "Password must be at least 8 characters." });
      return;
    }

    setSubmitting(true);
    try {
      await register(name, email, password);
      router.replace("/dashboard");
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setFieldErrors({ email: "An account with this email already exists." });
      } else if (err instanceof ApiError && err.fieldErrors) {
        setFieldErrors(err.fieldErrors);
      } else {
        setError(describeError(err));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <h1 className="mb-1 text-2xl font-bold text-gray-900 dark:text-gray-100">FlowForge</h1>
        <p className="mb-6 text-sm text-gray-500 dark:text-gray-400">Create an account</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && <ErrorBanner message={error} />}
          <InputField label="Name" required value={name} onChange={(e) => setName(e.target.value)} />
          <InputField
            label="Email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            error={fieldErrors.email}
          />
          <InputField
            label="Password"
            type="password"
            autoComplete="new-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            hint="At least 8 characters."
            error={fieldErrors.password}
          />
          <Button type="submit" loading={submitting} className="w-full">
            Create account
          </Button>
        </form>

        <p className="mt-4 text-center text-sm text-gray-500 dark:text-gray-400">
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-gray-900 hover:underline dark:text-gray-100">
            Log in
          </Link>
        </p>
      </div>
    </div>
  );
}
