# 0002. Session cookies and CSRF instead of JWTs

**Status:** Accepted

## Context

The frontend needs to authenticate API calls. The common SPA default is a JWT kept
in `localStorage` or a JS-readable cookie, plus refresh-token rotation. The users
are staff of one company working in a browser; there are no third-party or mobile
API clients.

## Decision

Use Django's session authentication. Because the browser reaches the API through the
Next.js origin ([ADR 0001](0001-strangler-fig-migration.md)), the session cookie is
first-party: `HttpOnly`, `Secure`, `SameSite=Lax`. Unsafe requests carry Django's
CSRF token in `X-CSRFToken`, and the `Origin` must be listed in
`CSRF_TRUSTED_ORIGINS`. The unauthenticated auth endpoints (login, signup) enforce
CSRF explicitly to prevent login-CSRF, and are rate limited per IP and per e-mail.

## Consequences

- No token is ever readable by JavaScript, so an XSS bug can't exfiltrate a
  credential; logout and suspension take effect immediately (server-side state).
- No refresh-token logic, no token revocation lists, no clock-skew issues.
- Requires same-origin deployment (the proxy) and a correct `CSRF_TRUSTED_ORIGINS`;
  a misconfigured origin shows up as 403s on every write.
- Not suitable as-is for third-party API clients; those would get separate
  token auth if ever needed.
