import { apiFetch } from "@/lib/api";
import type { LoginPayload, RegisterPayload, TokenResponse, User } from "@/types/auth";

export function login(payload: LoginPayload): Promise<TokenResponse> {
  return apiFetch<TokenResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
    skipAuth: true,
  });
}

export function register(payload: RegisterPayload): Promise<User> {
  return apiFetch<User>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
    skipAuth: true,
  });
}

export function getCurrentUser(): Promise<User> {
  return apiFetch<User>("/api/auth/me");
}
