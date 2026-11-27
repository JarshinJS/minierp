# 0005. Playwright end-to-end tests against real servers and a disposable database

**Status:** Accepted

## Context

435 backend tests cover business rules and API permissions, but none of them proves
that the product works for a person: that the React pages call the API correctly,
that the Next.js proxy forwards sessions and CSRF, that a deep link survives the
login detour, or that a role sees only what it may use. These seams are exactly
where the migration (ADR 0001) can break things.

## Decision

A Playwright suite (`frontend/e2e/`) that:

- starts **real** servers itself: Django with `config.settings.e2e` and a production
  build of Next.js, wired exactly as in production;
- runs against a throwaway SQLite database that is reset and re-seeded by
  `manage.py seed_demo --reset` on every run. The settings ignore `DATABASE_URL`, and
  `--reset` refuses to run under any other settings module, so a real database can
  never be touched;
- signs each demo role in once through the real login API and reuses the session;
- reads signup codes from Django's file-based e-mail backend, so the full signup
  flow runs without a mail server;
- tests what users do (role-based selectors, visible text) and checks permissions
  twice: what the UI offers, and what the API allows when called directly;
- runs axe-core WCAG 2.1 AA checks on every migrated page;
- keeps traces, screenshots and videos of failures as CI artifacts.

## Consequences

- Catches integration bugs unit tests can't. Its first run found that deep links
  lost their query string at login, and WCAG contrast failures on every page.
- About 1–2 minutes per run, plus a Next.js production build; runs in CI on every pull request.
- One worker for determinism: tests create uniquely named records, but share one
  seeded database.
