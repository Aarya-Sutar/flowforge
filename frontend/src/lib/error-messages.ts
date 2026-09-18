import { ApiError } from "@/lib/api";

/**
 * Turns any error into a message safe to show a user — never leaks a raw
 * stack trace or backend internals, but is specific enough to be useful.
 * Covers every status FLOWFORGE_SPEC.md's frontend error-handling section
 * lists explicitly.
 */
export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    switch (error.status) {
      case 0:
        return "Could not reach the server. Check your connection and try again.";
      case 400:
        return error.detail || "The server could not process that request.";
      case 401:
        return "Your session has expired. Please log in again.";
      case 403:
        return "You don't have permission to do that.";
      case 404:
        return "That item could not be found.";
      case 409:
        return error.detail || "That action conflicts with the item's current state.";
      case 422:
        return error.detail || "Please check the highlighted fields.";
      case 429:
        return "Too many requests — please wait a moment and try again.";
      default:
        return error.status >= 500
          ? "Something went wrong on our end. Please try again shortly."
          : error.detail || "Something went wrong.";
    }
  }

  return "Something unexpected went wrong.";
}
