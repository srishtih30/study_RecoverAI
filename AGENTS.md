# AGENTS.md

This file is for coding agents (Antigravity or otherwise) continuing this repository. Read it before making architectural changes. It complements — not replaces — [ARCHITECTURE.md](./ARCHITECTURE.md), [DATA_FLOW.md](./DATA_FLOW.md), and [PROJECT_STATUS.md](./PROJECT_STATUS.md).

## Project purpose

RecoverAI is an AI revenue-recovery agent for Razorpay (test mode). It watches for subscription payment failures, classifies why the money is at risk, executes a bounded recovery action (retry, payment-update link, notify, escalate, or halt), and reports recovered vs. at-risk revenue with a full audit trail.

**Primary demo flow:** trigger the batch simulator → watch cases populate the dashboard with diagnoses → drill into a case that recovers via retry, one that recovers via payment-link, one that halts after max attempts → show the aggregate recovery-rate panel → open one case's audit trail and narrate it end-to-end.

**Primary scope:** failed-subscription recovery. Checkout-abandonment recovery is stretch scope only — the architecture (event → classify → decide → act → audit) is generic enough to extend to it later, but it is not implemented.

## Core architecture

The whole system is one linear pipeline, implemented in `backend/app/services/webhook_orchestrator.py`:

```
Razorpay webhook
  → verify webhook signature
  → normalize event (raw payload → NormalizedEvent)
  → deduplicate event (idempotency)
  → classify failure (deterministic rules → LLM fallback)
  → load/create recovery case
  → check stopping rules
  → decide next action (pure decision engine)
  → schedule or execute action (Celery + Razorpay integration)
  → audit everything
  → expose updated state to dashboard (via the cases/metrics APIs)
```

The batch simulator (PRD F8) builds synthetic events and feeds them through the **exact same** pipeline (`webhook_orchestrator.process_event`), so simulated and real traffic never diverge in behavior — only in `EventSource` tagging.

See [DATA_FLOW.md](./DATA_FLOW.md) for the file-by-file walk-through of one request through this pipeline.

## Source-of-truth files

| Concept | File |
|---|---|
| Domain enums (CaseStatus, FailureCategory, RecoveryActionType, AttemptResult, AuditEventType, AuditActor, EventSource, NormalizedEventType) | `backend/app/domain/enums.py` |
| Normalized internal event model | `backend/app/domain/events.py` |
| Decision contract (types only) | `backend/app/domain/decision.py` |
| Decision engine (implementation) | `backend/app/services/decision_engine.py` |
| Database models | `backend/app/models/*.py` |
| API request/response schemas | `backend/app/schemas/*.py` |
| Razorpay integration (SDK, signature verification, payload normalization) | `backend/app/integrations/razorpay/*.py` |
| LLM fallback classifier | `backend/app/integrations/llm/classifier_fallback.py` |
| Audit write path | `backend/app/services/audit_service.py` |
| Idempotency foundation | `backend/app/services/idempotency.py` |
| Frontend API layer | `frontend/src/api/*.ts` |
| Frontend types (must mirror backend schemas) | `frontend/src/types/*.ts` |
| Project status / what's real vs. stubbed | `PROJECT_STATUS.md` |

## Rules future agents must follow

These are the mandatory architecture rules this boilerplate was built to enforce. Do not violate them when extending the code:

1. **The decision engine must not call Razorpay.** `app/services/decision_engine.py` takes a `DecisionContext` and returns a `Decision` — nothing else. It must not import `app.integrations.razorpay`, send notifications, schedule Celery jobs, or write to the database. All side effects belong to the caller (`webhook_orchestrator` → `recovery_executor`).
2. **Do not bypass the audit service.** Every automated decision or action must go through `app.services.audit_service.record_event(...)`. No other module should construct `models.AuditLog(...)` directly. Treat the audit log as append-only.
3. **Do not create unbounded retries.** Every case must terminate in `RECOVERED`, `HALTED`, or `ESCALATED` (`CaseStatus.terminal_statuses()`). `app/services/stopping_rules.py` enforces the hard limits (max retries, max days open, opt-out) and must run before the decision engine on every event.
4. **Do not duplicate domain enums.** `app/domain/enums.py` is the single source of truth on the backend; `frontend/src/types/*.ts` is its manually-maintained mirror. If you add or rename a value, update both in the same change. Never define an equivalent string constant elsewhere.
5. **Do not expose secrets to the frontend.** `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, and `LLM_API_KEY` are backend-only env vars. Only `VITE_`-prefixed vars in `frontend/.env.example` reach the browser, and none of them should ever be a secret.
6. **Do not use the LLM when deterministic rules already classify the event.** `app/services/classifier.py` checks `DETERMINISTIC_FAILURE_CODE_MAP` first; `app.integrations.llm.classifier_fallback.classify_with_llm` is only reached when that lookup misses.
7. **Do not treat simulator events as real Razorpay events.** Every `NormalizedEvent`, `RecoveryCase`, and audit entry carries `EventSource` (`razorpay_webhook` | `simulator`). Never blend or relabel these — the dashboard and metrics should always be able to say honestly which numbers came from simulated traffic.
8. **Do not silently change API response shapes without updating the frontend.** Backend response models live in `backend/app/schemas/*.py`; their frontend mirrors live in `frontend/src/types/*.ts`. A field rename/removal on one side without the other is exactly the kind of drift this repo is structured to avoid — update both, in the same commit.
9. **Keep the Razorpay SDK isolated.** Only `backend/app/integrations/razorpay/*.py` may `import razorpay` or hardcode a Razorpay API URL. Raw Razorpay JSON must not leak past `event_normalizer.py` — everything downstream consumes `NormalizedEvent`.
10. **Avoid circular dependencies between services.** See the dependency-direction docstring at the top of `backend/app/services/__init__.py`. `decision_engine.py` in particular must stay a leaf (imports `app.domain` only).
11. **Pass IDs across the Celery boundary, not ORM objects.** Every task in `backend/app/workers/tasks/*.py` takes a small serializable payload (e.g. `attempt_id: str`) and loads what it needs from the DB itself.

## How to continue development

1. Read `PROJECT_STATUS.md` first — it lists what's genuinely working, what's a placeholder, and what's not started. Don't assume a feature exists because a file for it exists.
2. Read `ARCHITECTURE.md` and `DATA_FLOW.md` to understand how the pieces connect before changing any one of them.
3. Search for `TODO(AG):` comments — every one is a specific, actionable pointer to unfinished or unverified behavior (Razorpay call shapes, LLM wiring, retry-interval tuning, etc.). Grep for them: `grep -rn "TODO(AG)" backend frontend`.
4. Run the test suite (`cd backend && pytest`) before and after your changes — it runs against SQLite with no external services required, so there's no excuse not to.
5. When you add a new domain concept, decide first whether it's an enum (→ `app/domain/enums.py`), a shared shape (→ `app/domain/events.py` or `app/domain/decision.py`), a persisted model (→ `app/models/`), or an API contract (→ `app/schemas/` + `frontend/src/types/`) — then add it in exactly one of those places, not several.
6. If you change a backend response shape, update the matching frontend type and any component reading it in the same change.
7. Keep the decision engine pure. If you're tempted to call Razorpay, schedule a task, or write to the DB from inside `decide_next_action`, that logic belongs in `recovery_executor.py` instead, driven by the `Decision` the engine already returned.
