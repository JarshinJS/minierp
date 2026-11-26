import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "./schema";

/**
 * Typed client for the Django REST API (types generated from /api/schema/ with
 * `npm run api`). Requests go to the same origin; Next.js rewrites /api/* to
 * Django, so the session cookie is first-party.
 */
export const api = createClient<paths>({ baseUrl: "", credentials: "same-origin" });

const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1] ?? "") : null;
}

let csrfPromise: Promise<void> | null = null;
async function ensureCsrfCookie() {
  if (readCookie("csrftoken")) return;
  csrfPromise ??= fetch("/api/auth/csrf/", { credentials: "same-origin" }).then(() => undefined);
  await csrfPromise;
  csrfPromise = null;
}

/** Django expects the csrftoken cookie echoed back as X-CSRFToken on writes. */
const csrfMiddleware: Middleware = {
  async onRequest({ request }) {
    if (!UNSAFE.has(request.method)) return request;
    await ensureCsrfCookie();
    const token = readCookie("csrftoken");
    if (token) request.headers.set("X-CSRFToken", token);
    return request;
  },
};
api.use(csrfMiddleware);

/** Error thrown by `unwrap` for any non-2xx response. */
export class ApiError extends Error {
  constructor(
    public status: number,
    public body: unknown,
  ) {
    super(ApiError.messageFrom(status, body));
  }

  /** Field-level validation errors, e.g. { email: ["Enter a valid email."] }. */
  get fieldErrors(): Record<string, string[]> {
    if (!this.body || typeof this.body !== "object") return {};
    const out: Record<string, string[]> = {};
    for (const [key, value] of Object.entries(this.body as Record<string, unknown>)) {
      if (key === "detail" || key === "restart") continue;
      if (Array.isArray(value)) out[key] = value.map(String);
      else if (typeof value === "string") out[key] = [value];
    }
    return out;
  }

  static messageFrom(status: number, body: unknown): string {
    if (body && typeof body === "object") {
      const b = body as Record<string, unknown>;
      if (typeof b.detail === "string") return b.detail;
      const nonField = b.non_field_errors;
      if (Array.isArray(nonField) && nonField.length) return String(nonField[0]);
      const first = Object.values(b).find((v) => Array.isArray(v) && v.length) as unknown[] | undefined;
      if (first) return String(first[0]);
    }
    if (status === 403) return "You don't have permission to do that.";
    if (status === 429) return "Too many attempts. Please wait a minute and try again.";
    if (status >= 500) return "The server had a problem. Please try again.";
    return `Request failed (${status}).`;
  }
}

/** Return `data` from an openapi-fetch result, or throw ApiError. */
export async function unwrap<T>(
  promise: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await promise;
  if (!response.ok) throw new ApiError(response.status, error);
  return data as T;
}

/** Paginated list envelope returned by DRF's LimitOffsetPagination. */
export type Page<T> = { count: number; next?: string | null; previous?: string | null; results: T[] };
