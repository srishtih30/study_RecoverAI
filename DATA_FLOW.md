# DATA_FLOW.md

One full end-to-end flow, stage by stage, with the exact module/file responsible for each step. This is the pipeline implemented in `backend/app/services/webhook_orchestrator.py` and exercised by `backend/tests/test_normalized_event.py`, `test_idempotency.py`, and `test_decision_contract.py`.

## Flow: Razorpay sends a subscription payment failure

**1. Razorpay POSTs the webhook**
`POST /api/webhooks/razorpay` with a raw JSON body, an `X-Razorpay-Signature` header, and (per Razorpay's delivery convention) an `X-Razorpay-Event-Id` header.
→ File: `backend/app/api/webhooks.py` (`receive_razorpay_webhook`)

**2. Signature is verified**
The route reads the raw request bytes (must be the exact bytes — a re-serialized JSON body would break the HMAC comparison) and passes them, unparsed, to the orchestrator.
→ File: `backend/app/services/webhook_orchestrator.py` (`handle_raw_webhook`) calls `backend/app/integrations/razorpay/webhook_verifier.py` (`verify_signature`). An invalid signature raises `InvalidWebhookSignatureError`, is audited as `WEBHOOK_SIGNATURE_INVALID`, and the API layer returns HTTP 400 — nothing downstream runs.

**3. Payload is normalized**
The raw Razorpay JSON is converted into the internal `NormalizedEvent` shape — the provider event id, event type, subscription/payment/customer ids, amount, currency, and failure code/description are extracted; the raw payload is retained only for debugging/audit, never consumed downstream.
→ File: `backend/app/integrations/razorpay/event_normalizer.py` (`normalize_razorpay_payload`) → produces `backend/app/domain/events.py` (`NormalizedEvent`)

**4. Event id is checked for duplication**
`process_event` (the shared pipeline both real webhooks and the simulator call) first records a `WEBHOOK_RECEIVED` audit entry, then checks the event's `provider_event_id` against `processed_webhook_events`. A duplicate is acknowledged and audited (`WEBHOOK_DUPLICATE_IGNORED`) with no further processing — no new case, no new attempt.
→ Files: `backend/app/services/webhook_orchestrator.py` (`process_event`) → `backend/app/services/idempotency.py` (`check_and_record`) → `backend/app/models/processed_event.py` (`ProcessedWebhookEvent`, unique constraint on `provider_event_id`)

**5. Failure category is determined**
Deterministic rules run first (`DETERMINISTIC_FAILURE_CODE_MAP`); the LLM fallback is only reached if the code isn't recognized (currently a stub that returns `unknown` — see AGENTS.md rule 6).
→ File: `backend/app/services/classifier.py` (`classify_failure`) → falls back to `backend/app/integrations/llm/classifier_fallback.py` (`classify_with_llm`)

**6. Recovery case is loaded or created**
If an open (non-terminal) case already exists for this subscription, it's updated in place (failure category, raw reason) rather than forking a duplicate case; otherwise a new `RecoveryCase` is created, tagged with `EventSource` from the event (so simulator-originated cases are always distinguishable).
→ File: `backend/app/services/case_service.py` (`get_or_create_case`, `get_open_case_for_subscription`) → `backend/app/models/case.py` (`RecoveryCase`)
Audit entries: `CASE_CREATED` or `CASE_UPDATED`, then `FAILURE_CLASSIFIED`.

**7. Stopping rules are evaluated**
The configured (or default) `StoppingRuleConfig` for this failure category is loaded, then checked against the case: opted-out, max retries reached, or max days open exceeded.
→ File: `backend/app/services/stopping_rules.py` (`get_stopping_rule`, `evaluate`) → `backend/app/models/stopping_rule.py` (`StoppingRuleConfig`)
If triggered: audited as `STOPPING_RULE_TRIGGERED`, and the result is passed into the decision context rather than re-derived later.

**8. Decision engine returns the next action**
A read-only `DecisionContext` (case snapshot, failure category, attempt history, stopping-rule snapshot, and whether it was triggered) is built and handed to the pure decision function, which returns a `Decision` (action, next case status, human-readable reason, optional `execute_at`, metadata). The decision engine has no DB/Razorpay/Celery access — see AGENTS.md rule 1.
→ Files: `backend/app/services/case_service.py` (`to_snapshot`, `history_snapshots`) build the context; `backend/app/domain/decision.py` defines the types; `backend/app/services/decision_engine.py` (`decide_next_action`) implements the mapping.

**9. Action is scheduled or executed, and audited**
The decision becomes a `RecoveryAttempt` row; the case's status/retry_count are updated via `case_service.apply_decision_to_case`. If the action needs a real side effect (retry, payment-update link, notify), it's audited as `ACTION_SCHEDULED` and a Celery task is enqueued — immediately for `retry_now`, or at `decision.execute_at` for delayed actions. Otherwise (halt/escalate/no_action) it's audited as `DECISION_MADE` with no task. The Celery task (`execute_action`) later calls `backend/app/services/recovery_executor.py` (`execute_attempt`), which is the only place that reaches into `backend/app/integrations/razorpay/client.py` for the actual (currently stubbed) Razorpay call, then records `ACTION_EXECUTED`/`ACTION_FAILED` and — on a successful retry — `CASE_RECOVERED`.
→ Files: `backend/app/services/recovery_executor.py` (`schedule_or_execute`, `execute_attempt`) → `backend/app/workers/tasks/execute_action.py` → `backend/app/integrations/razorpay/client.py`

**10. Case state changes; dashboard reflects the update**
Because every write above goes through `case_service` / `audit_service` against Postgres, the dashboard doesn't need a push mechanism — it just polls the read APIs, which read current state directly.
→ Files: `backend/app/api/cases.py` (list/get case, get audit history), `backend/app/api/metrics.py` (aggregate metrics) → `frontend/src/api/cases.ts`, `frontend/src/api/metrics.ts` → `frontend/src/pages/DashboardPage.tsx`, `CasesPage.tsx`, `CaseDetailPage.tsx`

## The simulator takes the identical path from step 4 onward

`backend/app/services/simulator_service.py` (`run_simulation`) builds `NormalizedEvent`s directly (skipping steps 1–3, since there's no real webhook to verify/normalize) tagged `EventSource.SIMULATOR`, and calls `webhook_orchestrator.process_event` — the same function real webhooks reach at the end of step 3. This is what guarantees simulated and real traffic can never silently diverge in behavior (PRD Section 4: "Both share the same underlying architecture").
