# MiniERP frontend (Next.js)

The Next.js app that is gradually replacing the Django-rendered pages. It is a
pure client of the Django REST API in `../backend`.

## How it fits together

```
browser ──> Next.js (Vercel)
              ├─ pages rebuilt in Next.js      → rendered here
              ├─ /api/*                        → proxied to Django (REST API)
              └─ everything else (fallback)    → proxied to Django (old pages, /static/, /admin/)
```

Because every request goes through one domain, the Django session cookie works
for both apps, and modules can be migrated **one at a time**: as soon as a
Next.js page exists at a URL, it takes over from the Django page at that URL.
Rewrites live in `next.config.ts`; Next.js pages use the same URLs as the Django
pages (`/products/list/`, `/inventory/`, …, always with a trailing slash).

## Local development

```bash
# terminal 1, backend (from backend/)
python manage.py runserver            # http://localhost:8000

# terminal 2, frontend (from frontend/)
cp .env.example .env.local            # BACKEND_URL=http://localhost:8000
npm install
npm run dev                           # http://localhost:3000  ← use this one
```

Open **http://localhost:3000**. Django's dev settings already trust this origin
for CSRF.

| Command | What it does |
|---|---|
| `npm run dev` / `build` / `start` | Next.js |
| `npm run lint`, `npm run typecheck` | ESLint, TypeScript |
| `npm run api` | Regenerate `openapi.yaml` from Django and the TS types in `src/lib/api/schema.d.ts` (needs the backend virtualenv active). Run after any API change. |

## Code map

| Path | Purpose |
|---|---|
| `src/lib/api/client.ts` | Typed API client (`api.GET("/api/products/")`), CSRF header, `ApiError`, `unwrap()` |
| `src/lib/auth.ts` | `useMe`, `useLogin`, `useLogout`, `canAccess(user, module)` |
| `src/lib/nav.ts` | Sidebar; `next: true` marks items already rebuilt in Next.js |
| `src/lib/url-state.ts` | List filters kept in the URL query string |
| `src/components/ui.tsx` | Badges, page header, empty states, pagination, fields, modal… |
| `src/components/app-shell.tsx` | Sidebar, top bar, alerts, user menu, login guard |
| `src/app/globals.css` | Design system, ported from `backend/static/css/src/input.css` |

## Migration status

| Module | Status |
|---|---|
| Login, signup + email verification | ✅ Next.js |
| Dashboard | ✅ Next.js |
| Products (list, detail, create, edit, deactivate) | ✅ Next.js |
| Inventory (stock, ledger, adjustments) | ✅ Next.js |
| Sales, Purchase, Procurement, Manufacturing, Delivery | ⏳ Django (proxied) |
| Foreign Trade, Blockchain, Reports, Audit Logs, Users & Roles | ⏳ Django (proxied) |
| Voice assistant | ⏳ Django pages only |

### Checklist for migrating the next module

1. Check the Django template(s) and view for every field, filter and action.
2. If the API lacks something the page needs, add it in the backend (keep logic in
   services/selectors) and run `npm run api`.
3. Build the pages under `src/app/(app)/` **at the same URL as the Django page**.
4. Set `next: true` on its entries in `src/lib/nav.ts`.
5. Verify against the running backend: list, filters, create/edit (including
   server validation errors), each workflow action, and a role that must be denied.
6. `npm run lint && npm run typecheck && npm run build`.

Once every module is migrated, remove the `fallback` rewrites and the Django
templates.
