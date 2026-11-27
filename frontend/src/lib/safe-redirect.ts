/**
 * Open-redirect protection for post-login destinations (`?next=`).
 *
 * Only same-site, relative paths are allowed. Everything else falls back to a safe
 * default. Browsers are lenient when parsing URLs, so a plain
 * `startsWith("/") && !startsWith("//")` check is not enough:
 *   "/\evil.com"   -> backslash becomes "/" -> "//evil.com"
 *   "/\t/evil.com" -> tabs/newlines are stripped -> "//evil.com"
 * Hence: reject whitespace, control characters, backslashes and encoded
 * slashes/backslashes/percent signs in the path, then resolve the URL against a
 * fixed origin and require that the origin did not change.
 *
 * Dependency-free on purpose (no React/Next imports) so it runs under `node --test`.
 */

export const DEFAULT_REDIRECT = "/dashboard/";

// Placeholder origin used only to resolve relative paths; never navigated to.
const BASE = "https://minierp.invalid";
const MAX_LENGTH = 2048;
// Pages that must not be a post-login destination (they would loop or re-authenticate).
const AUTH_PATHS = ["/login", "/signup"];

export function safeNext(next: string | null | undefined, fallback: string = DEFAULT_REDIRECT): string {
  if (typeof next !== "string" || next.length === 0 || next.length > MAX_LENGTH) return fallback;
  // Control characters and any whitespace (incl. Unicode spaces and line separators).
  if (/[\u0000-\u001F\u007F-\u009F\s\u200B-\u200F\u2028\u2029\uFEFF]/u.test(next)) return fallback;
  if (next.includes("\\")) return fallback;
  if (!next.startsWith("/") || next.startsWith("//")) return fallback;

  // Encoded "/", "\" or "%" in the path may be decoded later (by a proxy or a
  // second decode) into "//host" or "\host". Query strings may contain them.
  const path = next.split(/[?#]/, 1)[0] ?? "";
  if (/%(2f|5c|25)/i.test(path)) return fallback;

  let url: URL;
  try {
    url = new URL(next, BASE);
  } catch {
    return fallback;
  }
  if (url.origin !== BASE) return fallback;
  if (AUTH_PATHS.some((p) => url.pathname === p || url.pathname.startsWith(`${p}/`))) return fallback;

  return `${url.pathname}${url.search}${url.hash}`;
}
