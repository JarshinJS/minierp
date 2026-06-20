# Security Setup

## Create `.env`
1. Copy `.env.example` to `.env`.
2. Fill in your production values.
3. Keep `.env` out of Git. The repository already ignores it.

## Required environment variables
- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- `DB_ENGINE`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`

Recommended variables:
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GEMINI_API_KEY`
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `WEB3FORMS_ACCESS_KEY`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN`
- `AWS_REGION`
- `AZURE_CLIENT_ID`
- `AZURE_CLIENT_SECRET`
- `AZURE_TENANT_ID`
- `AZURE_STORAGE_CONNECTION_STRING`
- `FIREBASE_CREDENTIALS`
- `OAUTH_CLIENT_ID`
- `OAUTH_CLIENT_SECRET`
- `STRIPE_SECRET_KEY`
- `STRIPE_PUBLISHABLE_KEY`
- `RAZORPAY_KEY_ID`
- `RAZORPAY_KEY_SECRET`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_PHONE_NUMBER`

## Local development setup
1. Create and activate the virtual environment.
2. Install dependencies.
3. Copy `.env.example` to `.env`.
4. Run migrations.
5. Start the Django development server.

Example:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Production deployment setup
1. Set `DEBUG=False`.
2. Set a strong `SECRET_KEY`.
3. Configure `ALLOWED_HOSTS` for the deployed domain.
4. Configure database credentials through environment variables.
5. Set secure cookie and proxy settings in the production environment.
6. Collect static files during deployment.

## GitHub push checklist
- `.env` is ignored.
- `.env.example` is committed.
- No secrets remain in source files.
- No secret files such as credential JSON files are committed.
- The app runs with environment variables present.
- `DEBUG=False` works in production settings.
