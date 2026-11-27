# Testing

| Layer | Tool | Count | What it proves |
|---|---|---|---|
| Backend unit & integration | pytest + pytest-django | 435 | Business rules, workflows, permission matrix, API contracts, security fixes |
| Frontend unit | Node test runner | 7 | Pure logic such as `?next=` redirect validation |
| End-to-end | Playwright + axe-core | 35 | Real user journeys through Next.js → Django, per role, plus WCAG 2.1 AA |
| API contract | drf-spectacular + `diff` (CI) | n/a | The committed OpenAPI schema matches the code |

The backend suite runs on **SQLite and PostgreSQL** in CI: SQLite is what developers
run locally, PostgreSQL is what production runs.

Everything runs in [CI](../.github/workflows/ci.yml) on every pull request.

## Running the tests

```bash
# Backend (from backend/, virtualenv active)
python -m pytest                       # 435 tests, ~25 s, temporary SQLite database

# Same suite on PostgreSQL (what CI's second backend leg does), e.g. with a container:
podman run -d --rm --name pg -e POSTGRES_PASSWORD=postgres -p 127.0.0.1:5432:5432 postgres:17-alpine
TEST_DATABASE_URL=postgres://postgres:postgres@127.0.0.1:5432/postgres python -m pytest

# Frontend unit tests, lint, types (from frontend/)
npm test && npm run lint && npm run typecheck

# End-to-end (from frontend/). Starts Django and Next.js itself.
npx playwright install chromium        # first time only
npm run e2e                            # all specs, desktop + phone
npm run e2e:ui                         # interactive mode, time-travel debugging
npm run e2e:report                     # open the last HTML report
npm run e2e:screenshots                # regenerate docs/images/*.png
```

`npm run e2e` uses `../.venv/bin/python` if it exists; set `E2E_PYTHON` to use another
interpreter. The Django pages' CSS must be built first (`npm ci && npm run build:css`
in `backend/`); the setup step checks this and stops with that instruction if not.

## End-to-end suite

### How it is isolated

```mermaid
flowchart LR
    pw["Playwright"] -->|starts| dj["Django :8100<br/>config.settings.e2e"]
    pw -->|starts| nx["next build + start :3100<br/>BACKEND_URL=:8100"]
    dj --> db[("backend/.e2e/e2e.sqlite3<br/>reset + seed_demo every run")]
    dj --> mail["backend/.e2e/mail/<br/>file e-mail backend"]
    pw -->|reads signup codes| mail
    pw -->|browser| nx
    nx -->|"/api/* and Django pages"| dj
```

- `config.settings.e2e` always uses its own SQLite file, even if `DATABASE_URL` is
  set in `.env`. Files go to a local directory, never to object storage. The
  blockchain runs in persistent mock mode, and Celery tasks run inline.
- `seed_demo --reset` flushes the database **only** under `config.settings.e2e`;
  under any other settings it refuses.
- Each demo role signs in once through the real login API (`e2e/global.setup.ts`);
  specs reuse those sessions. Signing in through the UI is tested separately.

### What it covers

| Spec | Scenarios |
|---|---|
| `auth.spec.ts` | Sign in; wrong password; deep link with query string survives login; off-site `?next=` ignored (open-redirect guard); pending account told why; sign-out ends the session for Next.js **and** Django pages |
| `signup.spec.ts` | Request an account → read the e-mailed code → wrong code refused → right code creates a *pending* account → blocked until approved → admin approves as Sales User → first sign-in shows only sales modules |
| `rbac.spec.ts` | Sidebar per role (admin, sales, accountant, trade); sales users get a read-only catalogue **and** the API answers 403 to direct writes; a module outside the role shows a permission error, and its API returns 403 |
| `products.spec.ts` | Server-side validation shown per field; create; duplicate SKU refused; search/filter state in the URL survives reload; edit price; deactivate through a confirmation dialog |
| `inventory.spec.ts` | Out-of-stock tile filters the list; a receipt updates on-hand and appears in the ledger; over-issuing is refused with the server's reason and stock is unchanged |
| `dashboard.spec.ts` | KPIs, charts and low-stock list for an owner; every chart readable as a table; operational widgets hidden from an accountant |
| `strangler.spec.ts` | A not-yet-migrated Django page renders through Next.js with the same session (and its CSS loads); navigating between the two apps keeps you signed in |
| `accessibility.spec.ts` | axe-core WCAG 2.1 A/AA on sign-in, dashboard, product list, product form, inventory; any *serious* or *critical* violation fails |
| `procure-on-demand.spec.ts` | Tick "Procure on demand" on one product, untick on another, create a shortage for each: only the ticked one gets a procurement request (checked in the API **and** on the Django procurement page), and both shortages still show as out of stock |
| `mobile.spec.ts` | Pixel 7 viewport: drawer navigation, and no horizontal page scroll |

### Conventions

- **Find elements the way users do:** by role and accessible name
  (`getByRole("button", { name: "Record receipt" })`), not CSS classes. A
  test that can't find a control by its name usually means a real accessibility problem.
- **Check permissions twice:** what the UI offers, and what the API does when called
  directly (`e2e/support/api.ts`). Hiding a button is not access control.
- **Own your data:** tests that change data create their own uniquely named records
  (`uid()`), so they never depend on order or on each other.
- **Arrange through the API, act through the UI:** setup data is created with API
  calls; the behaviour under test is driven through the browser.

### Bugs the suite found

The first run surfaced real defects, now fixed and guarded by these tests:

- Deep links lost their query string at login (`/inventory/?tab=ledger` →
  `/inventory/`): the login redirect was built from the path only.
- WCAG contrast failures on every page: sidebar section headings (3.8:1), chart axis
  labels (2.6:1), and stock-status text (3.2:1).
- The alerts button's accessible name didn't include its visible count.

### Other regressions guarded

- **"Procure on demand" was ignored**: every stock shortage on sales-order confirmation
  raised a procurement request, whether or not the product had opted in. Now only
  opted-in products do; the order is still confirmed, stock still reserved, and the
  shortage still flagged either way. Guarded by
  `apps/procurement/tests/test_procure_on_demand.py` (service, API round trip, and
  proof that the flag is read at confirmation time) and `procure-on-demand.spec.ts`.

## Backend suite highlights

- `core/tests/test_permission_matrix.py` holds an independent copy of the role ×
  endpoint matrix from [architecture.md](architecture.md#role-and-permission-matrix)
  and fails if code and policy diverge.
- `apps/blockchain/tests/`: persistence across processes, live-service behaviour
  with a fake Web3 node, nonce allocation under concurrency, task retries.
- `apps/foreign_trade/tests/test_document_security.py`: upload validation (magic
  bytes, macros, size), signed expiring download links.
- `core/tests/test_security.py`, `core/tests/test_redirects.py`: signup hardening,
  XSS escaping, open-redirect protection.
- `config.settings.test` accepts `TEST_DATABASE_URL` (never `DATABASE_URL`) and only
  for local/CI hosts; `conftest.py` additionally refuses any Supabase host.
