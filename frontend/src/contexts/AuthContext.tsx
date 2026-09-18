"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { ApiError } from "@/lib/api";
import { clearToken, getToken, setToken } from "@/lib/auth-storage";
import * as authService from "@/lib/services/auth";
import type { User } from "@/types/auth";

interface AuthContextValue {
  user: User | null;
  /** True only while the very first "do we have a valid session" check is
   * running (on page load). Distinct from any later loading state a page
   * might have of its own. */
  isInitializing: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      // No token means there's nothing to await; this synchronously ends
      // the one-time "check for an existing session" effect on mount.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setIsInitializing(false);
      return;
    }

    // A token in storage might be expired or invalid (e.g. the backend's
    // JWT_SECRET_KEY changed) — GET /api/auth/me is the actual proof it
    // still works, not just that something is present in localStorage.
    authService
      .getCurrentUser()
      .then(setUser)
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 401) {
          clearToken();
        }
      })
      .finally(() => setIsInitializing(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await authService.login({ email, password });
    setToken(access_token);
    const me = await authService.getCurrentUser();
    setUser(me);
  }, []);

  const register = useCallback(async (name: string, email: string, password: string) => {
    await authService.register({ name, email, password });
    await login(email, password);
  }, [login]);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, isInitializing, login, register, logout }),
    [user, isInitializing, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
