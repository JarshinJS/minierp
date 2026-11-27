# 0001. Strangler-fig migration from Django templates to Next.js

**Status:** Accepted, in progress (5 of 14 modules migrated)

## Context

MiniERP started as a server-rendered Django app (templates + HTMX + Alpine.js). It
worked, but every page mixed presentation with query logic, nothing on the frontend
was typed, and the UI could not be tested or evolved independently of the backend.
A full rewrite would freeze feature work for weeks and ship everything at once.

## Decision

Run both UIs behind **one origin**. The Next.js app is the only thing the browser
talks to; it:

1. serves the pages that have been rebuilt,
2. rewrites `/api/*` to the Django REST API (before its own routing),
3. rewrites **everything else** to Django as a fallback (`next.config.ts`).

Rebuilt pages keep the Django URLs (`/products/list/`, trailing slashes included),
so links between the two UIs keep working. When a module moves, its Django
templates and HTML views are deleted, but its URL names stay registered and point
at `core.views.FrontendPageView`, so remaining templates can still `{% url %}` them.

## Consequences

- One session cookie, first-party for both apps; no CORS configuration.
- Modules move independently; the app is fully usable at every step.
- Two design systems coexist (the Tailwind 3 Django CSS and the Tailwind 4 port)
  and the sidebar is defined twice (`navigation.py`, `nav.ts`) until the migration
  ends. This is the main cost, and the reason to finish rather than stay hybrid.
- An extra network hop for Django pages (browser → Next.js → Django).
- End state: delete the fallback rewrite, `base.html` and `components/`; Django is
  API-only.
