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
| `minierp-worker` | Background worker| Celery: procurement tasks + blockchain anchoring |
| `minierp-redis`  | Key Value        | Celery broker                                   |
| Supabase         | Postgres (external) | Primary database, via `DATABASE_URL`         |

### First deploy

1. Push the repo to GitHub.
2. In Render: **New → Blueprint**, pick the repo. Render reads `render.yaml`.
3. When prompted, fill in the `sync: false` variables. **`DATABASE_URL`** is the
   Supabase *Session pooler* connection string (see [Database (Supabase)](#database-supabase)).
   **`CSRF_TRUSTED_ORIGINS`
   must include the frontend's origin** (e.g. `https://minierp.vercel.app`),
   otherwise every API login is rejected with 403. Then:
   `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`
   (signup OTPs are emailed; signup fails cleanly without these), and optionally
   `OLLAMA_URL` for the voice assistant. The blockchain variables
   (`WEB3_PROVIDER_URL`, `BLOCKCHAIN_WALLET_ADDRESS`, and
   `BLOCKCHAIN_WALLET_PRIVATE_KEY` on the worker) can stay empty while
   `BLOCKCHAIN_MOCK_MODE=True`; see [Blockchain anchoring](#blockchain-anchoring).
   **The `STORAGE_*` variables are required**: production refuses to start without
   a private bucket (see [Document storage](#document-storage)).
4. After the first deploy, create an admin from the service's **Shell** tab:
   ```bash
   python manage.py createsuperuser   # approved Admin; signups need approval
   python populate_incoterms.py   # seed Incoterms reference data
   ```

### How it builds and runs

- `backend/build.sh`: installs `requirements.txt`, builds Tailwind CSS (npm,
  or the standalone Tailwind binary if Node is missing), runs `collectstatic`.
- Static files are served by WhiteNoise with hashed, compressed filenames.
- Settings: `DJANGO_SETTINGS_MODULE=config.settings.prod`. `CELERY_BROKER_URL`
  and `SECRET_KEY` are wired automatically by the Blueprint; `DATABASE_URL` is the
  Supabase secret you enter;
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
- Python version: Render's default unless pinned (`PYTHON_VERSION` env var or a
  `backend/.python-version` file, which does not exist yet). Use **3.12 or 3.13**:
  `web3` depends on `ckzg`, which has no wheels for newer Pythons yet (installation
  fails on 3.15).

### Database (Supabase)

Postgres is hosted on Supabase; Render only runs the web service and worker.

- **Connection string:** Supabase Dashboard → **Connect** → **Session pooler**
  (`postgresql://postgres.<project-ref>:<password>@<…>.pooler.supabase.com:5432/postgres`).
  - Not the *Direct connection* (`db.<project-ref>.supabase.co`): it is
    IPv6-only, and Render has no IPv6 egress, so connections fail.
  - Not the *Transaction pooler* (port 6543): it breaks Django's server-side
    cursors and psycopg's prepared statements.
  - Percent-encode special characters in the password (`@` → `%40`, `#` → `%23`, …).
- Set it as `DATABASE_URL` in the `minierp-backend` env group (shared by
  `minierp-api` and `minierp-worker`). TLS is enforced (`DB_SSL_REQUIRE=True`,
  and always for `*.supabase.*` hosts).
- **Separate projects:** use one Supabase project for development and another for
  production. Local experiments, `migrate` from a feature branch or a stray
  `flush` must never hit production data.
- **Connections:** each gunicorn worker and Celery process keeps one persistent
  connection (`DB_CONN_MAX_AGE`, default 60 s): with the Blueprint defaults
  that's 3 + 2 = 5, well inside the pooler's client limit. Lower
  `DB_CONN_MAX_AGE` to `0` if you scale out and hit the limit.
- Migrations run in `preDeployCommand` against Supabase like any Postgres.
- The blockchain nonce lock relies on Postgres row locks (`SELECT … FOR UPDATE`),
  which work through the session pooler.
- **Moving from the old Render database:** removing `minierp-db` from the
  Blueprint does not delete it. Copy the data first
  (`pg_dump --no-owner --no-acl "$OLD_URL" | psql "$SUPABASE_URL"`, with the old
  external URL from Render), check the app, then delete `minierp-db` in Render.
- Backups: Supabase takes daily backups on paid plans; on the free plan, schedule
  your own `pg_dump`.

### Document storage

Trade documents are stored in a **private** bucket in Supabase Storage, through its
S3-compatible API (`django-storages`). Nothing is ever public: users download through
`/api/trade/documents/<id>/download/` with a signed, per-user link that expires after
`DOCUMENT_DOWNLOAD_URL_TTL` seconds (default 300). Storage credentials stay on the
server. Supabase Storage was chosen because the database is already on Supabase (one
provider, same region, S3 API so `django-storages` works unchanged, and the bucket can
be swapped for any S3-compatible store by changing env vars only).

**Set up (per environment; use a separate project or at least a separate bucket for dev):**

1. Supabase → **Storage → New bucket**, e.g. `trade-documents`. Leave **Public
   bucket OFF**. Don't add public policies.
2. Supabase → **Storage → Settings → S3 Connection**: copy the endpoint
   (`https://<project-ref>.storage.supabase.co/storage/v1/s3`) and region, then
   **New access key**. The secret is shown once: put it straight into Render.
   These keys bypass row-level security, so treat them like the database password.
3. On Render (`minierp-backend` group, used by **both** web and worker): set
   `STORAGE_BUCKET`, `STORAGE_ENDPOINT_URL`, `STORAGE_REGION`,
   `STORAGE_ACCESS_KEY_ID`, `STORAGE_SECRET_ACCESS_KEY`.
4. Never put any `STORAGE_*` value in the frontend (Vercel). The browser doesn't need it.

**Moving existing files** (uploaded before this change, on a local disk):

```bash
# from a shell that has the old media directory and the new STORAGE_* env vars
python manage.py migrate_trade_documents_to_storage --dry-run --source /path/to/media
python manage.py migrate_trade_documents_to_storage --source /path/to/media
```

Files keep their existing keys, so database references don't change. Every copy is
verified by SHA-256, and against the blockchain-anchored hash where one exists.
Mismatches are reported (`TAMPERED` / `DIFFERS`), never silently fixed. Local files are
not deleted; remove them once the report is clean. Files that only ever existed on
a Render web instance are already gone (the disk is wiped on deploy); those documents
show as missing (download returns 404) and must be re-uploaded.

### Signup approval

Self-service signup creates a **pending** account. It can't sign in or call any API
until an Admin or Business Owner approves it **and chooses its role**, on the Django
**Users & roles** page (`/accounts/users/`, pending requests listed first) or via
`POST /api/users/<id>/approve/ {"role": "SALES_USER"}`. Requests can also be rejected;
approved users can be suspended (their sessions end at once) and reinstated. Only an
Admin can grant or manage Admin / Business Owner accounts. Nobody can approve or
change their own account.

**Existing accounts after this release**: the migration marks every existing account
as *approved*, so current users and admins keep working. Self-registered accounts
from before this release had immediate access, so **review the user list** after
deploying and suspend or deactivate anyone who shouldn't be there.

There is no approval notification yet: check the Users page (or
`GET /api/users/?account_status=PENDING`) for new requests.

### Security deployment checklist

- [ ] `DEBUG` is not set (prod settings force `False`); `SECRET_KEY` is generated by Render.
- [ ] `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` list only your domains (no wildcards).
- [ ] `DATABASE_URL` is the **production** Supabase project's Session pooler string; dev uses a different project.
- [ ] Private Supabase Storage bucket created; all `STORAGE_*` vars set on Render only.
- [ ] `python manage.py check --deploy` shows no warnings except the optional
      `SECURE_HSTS_PRELOAD` (enable only once you're sure every subdomain is HTTPS-only).
- [ ] `NUM_PROXIES` matches the real proxy chain (1 = Render direct, 2 = via Vercel), so
      rate limits see real client IPs. Login is limited per IP (`AUTH_THROTTLE_RATE`,
      10/min) and per account (`AUTH_ACCOUNT_THROTTLE_RATE`, 30/hour).
- [ ] Redis (`CACHE_URL`/`CELERY_BROKER_URL`) is set, so throttling is shared by all workers.
- [ ] After deploy: review existing users (see Signup approval); migrate old documents.
- [ ] `BLOCKCHAIN_WALLET_PRIVATE_KEY` only on `minierp-worker` (if live mode).
- [ ] Dependencies: `djangorestframework>=3.18.2` (earlier versions have unauthenticated
      DoS CVEs). Re-run `pip-audit -r backend/requirements.txt` and `npm audit` before releases.

### Cost notes

- `preDeployCommand` and background workers need paid plans. For a free/cheaper
  setup: delete `minierp-worker` and `minierp-redis`, set
  `CELERY_TASK_ALWAYS_EAGER=True`, and move the migrate step into
  `startCommand` (`python manage.py migrate --no-input && gunicorn ...`).
  Without a worker, blockchain anchoring runs inside the web request (right after
  it commits). That is fine with `BLOCKCHAIN_MOCK_MODE=True`; in live mode a submit
  can wait up to `BLOCKCHAIN_RECEIPT_TIMEOUT` for the transaction to be mined, so
  keep that well below gunicorn's 60 s `--timeout` (e.g. `30`), set
  `BLOCKCHAIN_WALLET_PRIVATE_KEY` on `minierp-api`, and expect slower uploads.

### Blockchain anchoring

Trade documents and key order events are fingerprinted (SHA-256) and the hash is
written into a self-transfer transaction from a dedicated wallet. "Verify" re-hashes
the file and checks it against that transaction.

**Modes**

| `BLOCKCHAIN_MOCK_MODE` | Behaviour |
|---|---|
| `True` (Blueprint default) | Simulated ledger stored in the app's own database. Works everywhere, costs nothing, **but provides no tamper evidence**: anyone who can edit the database can edit the ledger. Fine for demos/staging. |
| `False` | Real transactions on the configured chain. If the chain can't be reached the app **does not** fall back to the mock: anchoring tasks fail and retry, and "Verify" reports *Network unavailable* (stored status unchanged). Only with `DEBUG=True` (local dev) does it fall back to the mock, logged as an error. |

**Variables**

| Variable | Where | Default | Notes |
|---|---|---|---|
| `BLOCKCHAIN_MOCK_MODE` | group | `True` | See above. |
| `WEB3_PROVIDER_URL` | group, `sync: false` | — | JSON-RPC URL (Alchemy/Infura/QuickNode…). Usually contains an API key: treat as a secret. |
| `BLOCKCHAIN_WALLET_ADDRESS` | group, `sync: false` | — | Public address of the anchoring wallet. The web service needs it to check the sender of anchored transactions. |
| `BLOCKCHAIN_WALLET_PRIVATE_KEY` | **worker only**, `sync: false` | — | Signs transactions. Read from the environment at signing time; never stored in the DB or logged. Not needed by `minierp-api` (unless running without a worker, see Cost notes). |
| `BLOCKCHAIN_NETWORK_NAME` | group | `polygon-amoy` | Label stored with each record. |
| `BLOCKCHAIN_GAS_LIMIT_MULTIPLIER` | optional | `1.2` | Gas limit = `estimate_gas()` × this. |
| `BLOCKCHAIN_MAX_GAS` | optional | `100000` | Submissions estimating more gas than this are refused. An anchor needs ~22k. |
| `BLOCKCHAIN_MIN_PRIORITY_FEE_GWEI` | optional | `30` | Floor for the EIP-1559 tip; Polygon rejects tips below ~25 gwei. |
| `BLOCKCHAIN_MAX_FEE_PER_GAS_GWEI` | optional | `500` | Hard cap on `maxFeePerGas` (= 2 × base fee + tip). During a fee spike above the cap, submissions are refused and retried later instead of overpaying. Worst case per anchor ≈ `MAX_GAS × MAX_FEE`. |
| `BLOCKCHAIN_RECEIPT_TIMEOUT` | optional | `120` | Seconds a worker waits for a transaction to be mined before handing it back to the retry queue. |

**Enabling live mode on Polygon Amoy (testnet, free)**

1. Create a **new, dedicated** wallet (never reuse a personal one) and keep its key
   in a password manager. Fund it with test POL from the Polygon faucet. Testnet
   only until you've decided on mainnet; don't put real funds on it.
2. Get an Amoy RPC URL from a provider (chain id `80002`).
3. On Render: set `WEB3_PROVIDER_URL` and `BLOCKCHAIN_WALLET_ADDRESS` in the
   `minierp-backend` group, `BLOCKCHAIN_WALLET_PRIVATE_KEY` on `minierp-worker`,
   then `BLOCKCHAIN_MOCK_MODE=False`. Redeploy both services.
4. Upload a document, wait for the worker to anchor it (status *Verified*), and
   look the transaction up on the Amoy explorer. Records anchored in mock mode
   will verify as *Unverified* on the live chain; re-upload them if needed.

Never paste the private key or RPC URL into tickets, logs, chat or commits. If one
leaks, move the funds and rotate it (new wallet ⇒ new `BLOCKCHAIN_WALLET_ADDRESS`;
documents anchored by the old wallet then show *Unverified*).

**How anchoring runs (Celery)**

- Uploads and order events only *enqueue* work (`apps.blockchain.register_document`,
  `apps.blockchain.log_audit_event`), dispatched after the DB transaction commits.
  A new document shows *Pending* until the worker has anchored it.
- Tasks retry chain errors up to 5 times with jittered exponential backoff
  (starting around 30 s, capped at 10 min).
- **Nonces:** every worker allocates nonces through one locked database row per
  wallet (`BlockchainWallet`), so any worker concurrency is safe, as long as the
  wallet is used **only** by this deployment. Transfers made by hand from the same
  wallet are detected and worked around, but cost a retry.
- **Idempotency:** each signed transaction is saved (`BlockchainSubmission`)
  *before* it is broadcast. Retries after a crash, RPC error or receipt timeout
  re-send the identical transaction instead of creating a new one. A data hash
  gets a second transaction only if the first one reverted on-chain.
- **Operations:** Django admin → *Blockchain submissions* lists every transaction
  with its status. Rows stuck in `SIGNED`/`BROADCAST` for a long time usually mean
  the fee cap is below the network's current fees, or the wallet is out of gas
  money; check `last_error` and the worker logs. Don't edit these rows by hand
  (the admin is read-only for that reason).
- If you move off Postgres, keep a database with row-level locking for the worker
  (SQLite is only suitable for local development).

### Known gaps

- **No password reset / account recovery flow** exists yet; an Admin must reset
  passwords in Django admin.
- **No Content-Security-Policy** on HTML pages (Django pages use inline Alpine.js);
  file downloads do get a sandbox CSP.
- **Voice assistant** needs a reachable Ollama server (`OLLAMA_URL`); Render
  can't run Ollama alongside the web service.

## Frontend on Vercel

1. In Vercel: **Add New → Project**, import the repo, set **Root Directory** to
   `frontend`. The framework (Next.js) is detected automatically.
2. Environment variable: `BACKEND_URL` = the Render URL of `minierp-api`
   (e.g. `https://minierp-api.onrender.com`, no trailing slash).
3. Deploy, then on **Render** set:
   - `CSRF_TRUSTED_ORIGINS` = the Vercel URL (e.g. `https://minierp.vercel.app`);
   - `NUM_PROXIES` = `2` (Vercel → Render), so login rate limiting sees real client IPs;
   - `FRONTEND_URL` = the Vercel URL, so rebuilt pages opened on the Render URL
     redirect to the frontend.
4. Use the **Vercel URL** from now on. It serves the rebuilt Next.js pages and
   proxies `/api/*` plus all not-yet-migrated Django pages to Render, so one login
   works everywhere. See [frontend/README.md](../frontend/README.md).
