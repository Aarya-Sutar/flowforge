"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import type { UserRole } from "@/types/auth";
import Spinner from "@/components/ui/Spinner";

interface RequireAuthProps {
  children: React.ReactNode;
  /** If set, only these roles may view the page — everyone else is bounced
   * to /dashboard. This is a UX convenience, not the real security boundary:
   * the backend enforces authorization for real (see Phase 6 docs). */
  roles?: UserRole[];
}

export default function RequireAuth({ children, roles }: RequireAuthProps) {
  const { user, isInitializing } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isInitializing) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    if (roles && !roles.includes(user.role)) {
      router.replace("/dashboard");
    }
  }, [isInitializing, user, roles, router]);

  if (isInitializing || !user || (roles && !roles.includes(user.role))) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Spinner />
      </div>
    );
  }

  return <>{children}</>;
}
