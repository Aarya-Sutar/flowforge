"use client";

import RequireAuth from "@/components/auth/RequireAuth";
import { useAuth } from "@/contexts/AuthContext";
import Card from "@/components/ui/Card";
import BackendStatus from "@/components/BackendStatus";

function SettingsContent() {
  const { user } = useAuth();
  if (!user) return null;

  return (
    <div className="max-w-xl space-y-6">
      <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Settings</h1>

      <Card title="Account">
        <dl className="space-y-3 text-sm">
          <div>
            <dt className="text-xs font-medium uppercase text-gray-400">Name</dt>
            <dd className="mt-0.5 text-gray-800 dark:text-gray-200">{user.name}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase text-gray-400">Email</dt>
            <dd className="mt-0.5 text-gray-800 dark:text-gray-200">{user.email}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase text-gray-400">Role</dt>
            <dd className="mt-0.5 text-gray-800 dark:text-gray-200">{user.role}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase text-gray-400">Member since</dt>
            <dd className="mt-0.5 text-gray-800 dark:text-gray-200">{new Date(user.created_at).toLocaleDateString()}</dd>
          </div>
        </dl>
      </Card>

      <Card title="Connection">
        <BackendStatus />
      </Card>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <RequireAuth>
      <SettingsContent />
    </RequireAuth>
  );
}
