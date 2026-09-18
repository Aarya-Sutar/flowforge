"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";

const NAV_LINKS = [
  { href: "/dashboard", label: "Dashboard", roles: ["USER", "OPERATOR", "ADMIN"] },
  { href: "/requests", label: "Requests", roles: ["USER", "OPERATOR", "ADMIN"] },
  { href: "/tasks", label: "Tasks", roles: ["OPERATOR", "ADMIN"] },
  { href: "/rules", label: "Rules", roles: ["ADMIN"] },
  { href: "/settings", label: "Settings", roles: ["USER", "OPERATOR", "ADMIN"] },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  if (!user) return <>{children}</>;

  const visibleLinks = NAV_LINKS.filter((link) => link.roles.includes(user.role));

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-gray-200 dark:border-gray-800">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-8">
            <span className="text-lg font-bold text-gray-900 dark:text-gray-100">FlowForge</span>
            <nav className="flex gap-1">
              {visibleLinks.map((link) => {
                const active = pathname === link.href || pathname.startsWith(`${link.href}/`);
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                      active
                        ? "bg-gray-900 text-white dark:bg-gray-100 dark:text-gray-900"
                        : "text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
                    }`}
                  >
                    {link.label}
                  </Link>
                );
              })}
            </nav>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="text-gray-600 dark:text-gray-400">
              {user.name} <span className="text-gray-400 dark:text-gray-600">({user.role})</span>
            </span>
            <button
              onClick={() => {
                logout();
                router.replace("/login");
              }}
              className="rounded-md border border-gray-300 px-3 py-1.5 font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
            >
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">{children}</main>
    </div>
  );
}
