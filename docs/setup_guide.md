# Setup & Installation Guide

This guide will walk you through the process of setting up the Mini ERP System for development.

## Prerequisites

Ensure you have the following installed on your system:
- **Python 3.11+**
- **Node.js** (for building Tailwind CSS)
- **Git**
- **Ollama** (Required for the Voice Assistant feature)

## 1. Clone the Repository

```bash
git clone https://github.com/JarshinJS/minierp.git
cd minierp
```

## 2. Python Environment Setup

It's highly recommended to use a virtual environment.

```bash
# Create the virtual environment
python -m venv .venv

# Activate the virtual environment
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Install dependencies (runtime + test tools)
pip install -r backend/requirements-dev.txt
```

> **Project layout:** the Django app lives in `backend/` (the Next.js frontend will
> live in `frontend/`). Run every command below from inside `backend/`, and copy
> the example environment file first:
>
> ```bash
> cd backend
> cp .env.example .env   # then set SECRET_KEY
> ```

## 3. Frontend Assets Setup

The project uses Tailwind CSS. You need to install the Node modules and compile the CSS.

```bash
# From backend/: install Node dependencies
npm install

# Build the CSS for the first time
npm run build:css
```

## 4. Database Setup

By default the app uses a local SQLite file (`backend/db.sqlite3`). To use a
Supabase Postgres **development** project instead, add its *Session pooler*
connection string to `backend/.env` (never commit it):

```bash
DATABASE_URL=postgresql://postgres.<project-ref>:<password>@<pooler-host>.pooler.supabase.com:5432/postgres
```

Use the Session pooler string from Supabase → **Connect**, not the direct
`db.<project-ref>.supabase.co` host (IPv6-only; it fails on most networks).
Keep development and production in separate Supabase projects. Tests always run on
a temporary SQLite database (`config.settings.test`), whatever `DATABASE_URL` says.

Apply the Django migrations to set up the database schema and create a superuser for admin access.

```bash
python manage.py migrate
python manage.py createsuperuser
```
Follow the prompts to set an email and password for the superuser.

**Optional: demo data.** `python manage.py seed_demo` adds one approved user per role
(e.g. `admin@demo.minierp.dev`, `sales@demo.minierp.dev`, password `Demo-pass-2026!`),
a pending account, a furniture catalogue with healthy, low and out-of-stock items,
and a few confirmed sales orders. It is idempotent and never deletes anything; the
destructive `--reset` flag only works under `config.settings.e2e` (the Playwright
database). Don't run it against a database other people use: the demo passwords are public.

## 5. Running the Application

For active development, you will typically want to run the Django server and the Tailwind CSS watcher simultaneously.

**Option A: Using the NPM script (Runs concurrently)**
```bash
npm run dev
```

**Option B: Separate terminals**
Terminal 1:
```bash
python manage.py runserver
```
Terminal 2:
```bash
npm run watch:css
```

The application will be accessible at `http://127.0.0.1:8000/`.

## 6. Setting up Ollama (Voice Assistant)

To utilize the ERP Voice Assistant, you must have Ollama running locally.

1. Download and install [Ollama](https://ollama.com/).
2. Start the Ollama server:
   ```bash
   ollama serve
   ```
3. Pull and run the desired model (the default model used in `core/api_views.py` is `llama3.1`, but you can update the code to use another model like `llama3`):
   ```bash
   ollama run llama3.1
   ```

*Note: The Django application communicates with Ollama via `requests` at `http://localhost:11434`.*

For deploying to Render, see [deployment.md](deployment.md).

## 7. Accounts, approval and documents in development

* `python manage.py createsuperuser` creates an **approved** Admin. Accounts created
  through the signup page start **pending**: sign in as the admin, open
  **Users & roles** (`/accounts/users/`) and approve them with a role. A pending user
  who tries to sign in sees "Waiting for approval".
* Uploaded trade documents go to `backend/media/` unless the `STORAGE_*` variables
  are set (see `backend/.env.example`). That folder is never served over HTTP:
  downloads always go through the signed `/api/trade/documents/<id>/download/` link.
  To try the private-bucket setup locally, point `STORAGE_*` at a **development**
  Supabase bucket, never the production one.

## 8. Running the tests

```bash
cd backend
pytest                      # whole backend suite, on a temporary SQLite database
```

Tests always use `config.settings.test` (set in `pytest.ini`): a throwaway database
and local file storage, whatever is in `backend/.env`. `conftest.py` refuses to run
at all if the configured database host is a Supabase host.

PostgreSQL 16 (matches production) with a throwaway container:

```bash
podman run -d --rm --name pg16 -e POSTGRES_PASSWORD=localonly -p 127.0.0.1:55432:5432 postgres:16-alpine
# a settings module that imports config.settings.test and points DATABASES at it, then:
pytest --ds=<that module>
```

Opt-in integration tests:
* **Private S3 storage**: against any local S3-compatible server; see the docstring of
  `apps/foreign_trade/tests/test_s3_storage.py` (`S3_TEST_*` variables).
* **Blockchain on Polygon Amoy testnet**: `apps/blockchain/tests/test_amoy_smoke.py`.

Frontend:

```bash
cd frontend
npm run lint && npm run typecheck && npm test && npm run build
```

`npm test` runs the open-redirect tests (`src/lib/safe-redirect.test.ts`) with Node's
built-in test runner and TypeScript support (verified on Node 24, the version used here).
