#!/usr/bin/env bash
# Render build step for the Django backend (runs from backend/).
set -o errexit
set -o pipefail
set -o nounset

TAILWIND_VERSION="3.4.19"   # keep in sync with package-lock.json

pip install --upgrade pip
pip install -r requirements.txt

# --- Build Tailwind CSS -> static/css/dist/styles.css -------------------------
if command -v npm >/dev/null 2>&1; then
  npm ci --no-audit --no-fund
  npm run build:css
else
  echo "npm not found; using the standalone Tailwind CLI v${TAILWIND_VERSION}"
  curl -fsSL -o /tmp/tailwindcss \
    "https://github.com/tailwindlabs/tailwindcss/releases/download/v${TAILWIND_VERSION}/tailwindcss-linux-x64"
  chmod +x /tmp/tailwindcss
  /tmp/tailwindcss -i ./static/css/src/input.css -o ./static/css/dist/styles.css --minify
fi

# collectstatic doesn't touch the database, but prod settings refuse to load
# without these, so give harmless placeholders if they aren't set at build time.
ALLOWED_HOSTS="${ALLOWED_HOSTS:-localhost}" \
DATABASE_URL="${DATABASE_URL:-sqlite:////tmp/build.sqlite3}" \
  python manage.py collectstatic --no-input
