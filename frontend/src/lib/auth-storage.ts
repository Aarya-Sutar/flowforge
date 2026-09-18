// A single place that knows the JWT lives in localStorage under this key —
// see docs/learning/PHASE_6_FRONTEND_ENGINEERING.md for why localStorage
// (not a cookie) was chosen and what that trades away.
const TOKEN_KEY = "flowforge_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  try {
    window.localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // Private browsing / storage disabled — the session just won't persist
    // across reloads; nothing to recover from here.
  }
}

export function clearToken(): void {
  try {
    window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    // See setToken.
  }
}
