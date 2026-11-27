# 0003. Business rules live in a service layer

**Status:** Accepted

## Context

The same operation is reachable from several entry points: a REST endpoint, a
remaining Django page, a Celery task, the voice assistant. When rules live in views
or serializers, each entry point re-implements them and they drift apart. Early in
the project, the API could confirm or delete records that the HTML pages guarded.

## Decision

Every app has `services.py` (state changes) and `selectors.py` (read queries). Views
and serializers only parse input, check permissions and shape output.

- Services validate workflow transitions and raise `DomainError` / `WorkflowError`;
  one DRF exception handler maps those to `400 {"detail": …}`.
- Services run in transactions and write the audit trail.
- Stock is changed only by `inventory.services.post_ledger_entry`, with conditional
  `F()` updates, so concurrent requests can't oversell.
- Steps that also need a side effect (e.g. a blockchain audit event) are wrapped once
  (`foreign_trade/workflows.py`) and called by both the API and the pages.
- Hard deletes are not exposed; records are cancelled or deactivated.

## Consequences

- Business rules are unit-tested without HTTP, and every caller gets the same rules.
- Migrating a page (ADR 0001) is a UI change only.
- More files per module, and the discipline has to be kept in review: CI can't tell
  a view that quietly does `obj.save()` from one that calls a service.
