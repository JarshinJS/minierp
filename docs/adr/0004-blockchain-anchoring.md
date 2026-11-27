# 0004. Anchor document hashes asynchronously, with a persistent mock chain

**Status:** Accepted

## Context

Trade documents (invoices, bills of lading, certificates) must be provably
unchanged. The feature hashes each uploaded version (SHA-256) and anchors the hash
in a transaction on Polygon Amoy; verification re-hashes the stored file and compares.

An earlier version had three defects found in an audit:

1. The development/production default was an **in-memory** mock chain, so each web
   worker and every restart had a different "chain"; genuine documents verified as
   `TAMPERED`.
2. The live verifier compared hex-encoded transaction input with the plain hash, so
   live verification could never succeed.
3. Submission waited up to 120 s for the receipt **inside the upload request**, past
   the web server's timeout, and concurrent uploads could reuse a nonce.

## Decision

- Anchoring runs in a Celery task, dispatched after the upload's transaction commits,
  with exponential backoff and a bounded retry count (`apps/blockchain/tasks.py`).
- Wallet nonces are allocated under a database lock (`BlockchainWallet`), and every
  attempt is recorded (`BlockchainSubmission`).
- The mock chain is **database-backed** (`MockBlockchainTransaction`), so every process
  sees the same ledger and results survive restarts.
- With mock mode off, a misconfigured live chain is an **error**; it falls back to the
  mock only when `DEBUG=True`, and logs that loudly. Nothing is silently "anchored"
  to a fake chain in production.
- Verification decodes the on-chain input before comparing.

## Consequences

- Uploads return immediately; the document shows `PENDING` until anchored.
- Verification answers are consistent and reproducible in every environment,
  including tests (`apps/blockchain/tests/`).
- Requires a running worker and broker for live anchoring.
- What this proves: a file's bytes are unchanged since anchoring. It does not prove
  who uploaded it or that the content was correct when uploaded.
