# Shiv Furniture Works ERP

A Django-based mini ERP for small manufacturing and retail operations.

## Overview

This repository contains the Shiv Furniture Works ERP system. It uses:
- Django 5.2
- Django REST Framework
- Django HTMX
- Tailwind CSS for frontend styling
- Celery + Redis for background task support
- SQLite by default for local development

## Project Structure

- `apps/` – business apps for accounts, products, inventory, sales, purchase, manufacturing, procurement, audit logs, and dashboard.
- `config/` – Django settings and project configuration.
- `templates/` – all application templates and shared layouts.
- `static/` – CSS sources and compiled assets.
- `.venv/` – local virtual environment (not committed in source control).

## Prerequisites

- Python 3.11
- Node.js / npm (for Tailwind CSS build)
- Redis (for Celery broker/backend if you use asynchronous tasks)

## Setup

1. Create and activate a virtual environment:

```powershell
cd d:\ODOO\Mini_ERP_System
python -m venv .venv
.venv\Scripts\Activate.ps1
```

2. Install Python dependencies:

```powershell
pip install -r requirements.txt
```

3. Install Node dependencies if using Tailwind locally:

```powershell
npm install
```

4. Copy the environment template and configure local settings:

```powershell
copy .env.example .env
```

5. Generate a secure `SECRET_KEY` and update `.env` before running in production.

## Database Migration

Run Django migrations:

```powershell
.venv\Scripts\python.exe manage.py migrate
```

## Running the Application

Start the development server:

```powershell
.venv\Scripts\python.exe manage.py runserver
```

Then visit `http://localhost:8000/`.

## Tailwind CSS Build

Build CSS once:

```powershell
npm run build:css
```

Watch CSS file changes:

```powershell
npm run watch:css
```

## Testing

Run the project tests via pytest:

```powershell
.venv\Scripts\python.exe -m pytest -q
```

## Notes for Stabilization

- The current project is in stabilization mode; no new feature development should be added without explicit approval.
- The system uses `django_filters` and `django_htmx` for filtering and dynamic page updates.
- Celery is configured in settings, but Redis must be available for asynchronous tasks.
- Most business logic is isolated in service modules under `apps/*/services.py`.

## Important Files

- `.env.example` — environment variable template.
- `requirements.txt` — Python dependencies.
- `package.json` — Tailwind build scripts.
- `pytest.ini` — pytest Django settings and discovery.

## Security

- Do not commit `.env` to version control.
- Keep `SECRET_KEY` private.
- Use proper `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` in production.
