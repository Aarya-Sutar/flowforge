import { getToken } from "@/lib/auth-storage";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * status 0 means the request never reached the server at all (network
 * failure / backend unreachable) — distinct from any real HTTP status.
 */
export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
    public fieldErrors?: Record<string, string>,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

async function parseErrorBody(response: Response): Promise<{ detail: string; fieldErrors?: Record<string, string> }> {
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    return { detail: `Request failed with status ${response.status}` };
  }

  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;

    if (typeof detail === "string") {
      return { detail };
    }

    // FastAPI's 422 shape: detail is a list of {loc, msg, type}.
    if (Array.isArray(detail)) {
      const fieldErrors: Record<string, string> = {};
      for (const entry of detail) {
        if (entry && typeof entry === "object" && "loc" in entry && "msg" in entry) {
          const loc = (entry as { loc: unknown[] }).loc;
          const field = String(loc[loc.length - 1] ?? "field");
          fieldErrors[field] = String((entry as { msg: unknown }).msg);
        }
      }
      const summary = Object.values(fieldErrors)[0] ?? "Validation failed";
      return { detail: summary, fieldErrors };
    }
  }

  return { detail: `Request failed with status ${response.status}` };
}

interface ApiFetchOptions extends RequestInit {
  /** Skip attaching the Authorization header — only login/register need this. */
  skipAuth?: boolean;
}

/**
 * The single place every backend call goes through: base URL, auth header,
 * and error normalization all live here exactly once.
 */
export async function apiFetch<T>(path: string, init?: ApiFetchOptions): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };

  if (!init?.skipAuth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "Could not reach the server. Check your connection and try again.");
  }

  if (!response.ok) {
    const { detail, fieldErrors } = await parseErrorBody(response);
    throw new ApiError(response.status, detail, fieldErrors);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}
