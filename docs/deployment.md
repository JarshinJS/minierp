# Deployment

The repository is split into two independently deployed apps:

| Folder      | What                         | Host   |
|-------------|------------------------------|--------|
| `backend/`  | Django (API + current pages) | Render |
| `frontend/` | Next.js (being migrated to)  | Vercel |

## Backend on Render

Everything is described in [`render.yaml`](../render.yaml) (a Render Blueprint):

| Resource         | Type             | Purpose                                         |
|------------------|------------------|-------------------------------------------------|
| `minierp-api`    | Web service      | Gunicorn serving Django; migrations run pre-deploy |
| `minierp-worker` | Background worker| Celery, runs procurement tasks                  |
| `minierp-redis`  | Key Value        | Celery broker                                   |
| `minierp-db`     | Postgres         | Primary database                                |

### First deploy

1. Push the repo to GitHub.
2. In Render: **New → Blueprint**, pick the repo. Render reads `render.yaml`.
3. When prompted, fill in the `sync: false` variables. **`CSRF_TRUSTED_ORIGINS`
   must include the frontend's origin** (e.g. `https://minierp.vercel.app`),
   otherwise every API login is rejected with 403. Then:
   `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`
   (signup OTPs are emailed; signup fails cleanly without these), and optionally
   `OLLAMA_URL` for the voice assistant.
4. After the first deploy, create an admin from the service's **Shell** tab:
   ```bash
   python manage.py createsuperuser
   python populate_incoterms.py   # seed Incoterms reference data
   ```

### How it builds and runs

- `backend/build.sh`: installs `requirements.txt`, builds Tailwind CSS (npm,
  or the standalone Tailwind binary if Node is missing), runs `collectstatic`.
- Static files are served by WhiteNoise with hashed, compressed filenames.
- Settings: `DJANGO_SETTINGS_MODULE=config.settings.prod`. `DATABASE_URL`,
  `CELERY_BROKER_URL` and `SECRET_KEY` are wired automatically by the Blueprint;
  Render's own hostname is added to `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS`.
  For a custom domain, set `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`.
- API: everything under `/api/`; OpenAPI schema at `/api/schema/`, docs at
  `/api/docs/` (login required). See [api.md](api.md).
- Rate limiting (login/signup) uses Redis via `CACHE_URL`/`CELERY_BROKER_URL`.
  `NUM_PROXIES` tells Django how many proxies sit in front of it so it can see the
  real client IP: `1` for direct Render traffic, `2` once requests come through
  Vercel rewrites. If this is wrong, either all users share one rate-limit bucket
  (too low) or clients can spoof their IP (too high).
- Health check: `GET /healthz/` → `{"status": "ok"}` (checks the database).
- Python version: `backend/.python-version`.

### Cost notes

- `preDeployCommand` and background workers need paid plans. For a free/cheaper
  setup: delete `minierp-worker` and `minierp-redis`, set
  `CELERY_TASK_ALWAYS_EAGER=True`, and move the migrate step into
  `startCommand` (`python manage.py migrate --no-input && gunicorn ...`).

### Known gaps

- **Uploaded files** (trade documents) are written to local disk, which Render
  wipes on every deploy, and they aren't served in production. Move media to S3 /
  Cloudflare R2 (`django-storages`) before relying on uploads.
- **Voice assistant** needs a reachable Ollama server (`OLLAMA_URL`); Render
  can't run Ollama alongside the web service.

## Frontend on Vercel

1. In Vercel: **Add New → Project**, import the repo, set **Root Directory** to
   `frontend`. The framework (Next.js) is detected automatically.
2. Environment variable: `BACKEND_URL` = the Render URL of `minierp-api`
   (e.g. `https://minierp-api.onrender.com`, no trailing slash).
3. Deploy, then on **Render** set:
   - `CSRF_TRUSTED_ORIGINS` = the Vercel URL (e.g. `https://minierp.vercel.app`);
   - `NUM_PROXIES` = `2` (Vercel → Render), so login rate limiting sees real client IPs.
4. Use the **Vercel URL** from now on. It serves the rebuilt Next.js pages and
   proxies `/api/*` plus all not-yet-migrated Django pages to Render, so one login
   works everywhere. See [frontend/README.md](../frontend/README.md).
