# Security Setup & Deployment Guidelines

This document provides setup guidelines to configure the Shiv Furniture Works ERP safely in local development and production environments.

---

## 1. Local Development Setup
1. Copy the environment template to create your `.env` file:
   ```bash
   cp .env.example .env
   ```
2. Activate your virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Run migrations and start the server:
   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

---

## 2. Environment Variables Configuration

The following variables must be configured in your environment or in `.env`:

### Django Core Settings
- `SECRET_KEY`: A long, unique, random string used in cryptography (required in production).
- `DEBUG`: Set to `True` for development, `False` for production.
- `ALLOWED_HOSTS`: Comma-separated list of domain names/IPs allowed to access the application (e.g. `erp.domain.com,12.34.56.78`).
- `CSRF_TRUSTED_ORIGINS`: Comma-separated list of origins trusted for CSRF protection (e.g., `https://erp.domain.com`).

### Database Configuration
- `DB_ENGINE`: The database backend (e.g., `django.db.backends.postgresql` or `django.db.backends.sqlite3`).
- `DB_NAME`: Database name (or path for SQLite).
- `DB_USER`: Database user.
- `DB_PASSWORD`: Database password.
- `DB_HOST`: Database host.
- `DB_PORT`: Database port.

### Email Configuration
- `EMAIL_BACKEND`: Mail transport backend class (defaults to Console backend in dev).
- `EMAIL_HOST`: SMTP server address.
- `EMAIL_PORT`: SMTP port (e.g. `587` or `465`).
- `EMAIL_USE_TLS`: Enable TLS protection (True/False).
- `EMAIL_USE_SSL`: Enable SSL protection (True/False).
- `EMAIL_HOST_USER`: Username/email for authenticating.
- `EMAIL_HOST_PASSWORD`: Application-specific password.

### Third-Party Keys
- `OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`: API keys for AI assistants.
- `WEB3FORMS_ACCESS_KEY`: Access token for contact forms.

---

## 3. Production Security Checklist
- [ ] Set `DEBUG=False` in environment.
- [ ] Change `SECRET_KEY` to a cryptographically secure key.
- [ ] Restrict `ALLOWED_HOSTS` to your production domain name.
- [ ] Configure `CSRF_TRUSTED_ORIGINS` to match your domain (e.g., `https://erp.domain.com`).
- [ ] Ensure `rest_framework.authentication.BasicAuthentication` is disabled (it is automatically disabled when running under `config.settings.prod`).
- [ ] Collect static files via `python manage.py collectstatic --settings=config.settings.prod`.

---

## 4. Git History Cleaning (Optional)
If any secret or default development key was historically committed to Git, run the following commands to safely rewrite the history before pushing to public GitHub:

### Using BFG Repo Cleaner
```bash
# Create a text file containing the secret to remove (e.g., secrets.txt)
echo "django-insecure-default-secret-key-for-development" > secrets.txt

# Run BFG to replace secrets in commits
bfg --replace-text secrets.txt

# Clean up reflogs and garbage collect
git reflog expire --expire=now --all && git gc --prune=now --aggressive
```

### Using git filter-repo
```bash
# Create expressions file (expressions.txt) with replacement pattern
echo "django-insecure-default-secret-key-for-development==>django-insecure-development-placeholder-key" > expressions.txt

# Run filter-repo to replace matches
git filter-repo --replace-text expressions.txt
```
