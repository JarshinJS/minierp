# MiniERP documentation

Start with the [project README](../README.md) for an overview, screenshots and quick start.

| Document | What's in it |
|---|---|
| [Architecture](architecture.md) | System context, request routing during the Next.js migration, backend layering, frontend structure, auth/CSRF flow, domain model, business workflows, tamper-evident documents, and the security model with the full role × permission matrix |
| [Architecture Decision Records](adr/) | The reasoning behind the big choices, and what each one costs |
| [Testing](testing.md) | Test layers, how the Playwright suite is isolated, what each spec covers, bugs it found |
| [API reference](api.md) | Auth and CSRF conventions, errors, pagination, and every endpoint under `/api/` |
| [Setup guide](setup_guide.md) | Local development: backend, frontend, demo data, background jobs |
| [Modules](modules.md) | Responsibilities of each of the 14 Django apps |
| [Deployment](deployment.md) | Reference configuration for Render (API) and Vercel (frontend); not required to run the project |
