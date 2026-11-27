# Architecture Decision Records

Short records of the decisions that shape this codebase: the context, what was
decided, and what it costs. Format: [Michael Nygard's ADR template](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions).

| # | Decision | Status |
|---|---|---|
| [0001](0001-strangler-fig-migration.md) | Migrate from Django templates to Next.js one module at a time behind one origin | Accepted, in progress |
| [0002](0002-session-auth-over-jwt.md) | Session cookies + CSRF instead of JWTs | Accepted |
| [0003](0003-service-layer.md) | All business rules in a service layer, shared by API and pages | Accepted |
| [0004](0004-blockchain-anchoring.md) | Anchor document hashes asynchronously; persistent mock chain | Accepted |
| [0005](0005-end-to-end-testing.md) | Playwright E2E against real servers and a disposable seeded database | Accepted |
