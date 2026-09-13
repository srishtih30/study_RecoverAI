"""
Service layer — RecoverAI's business logic, one module per responsibility.

Dependency direction (top calls bottom; bottom never imports top — this is
what "avoid circular dependencies between services" means in practice):

    api/*.py
        -> webhook_orchestrator   (orchestrates the full webhook flow)
        -> case_service, audit_service, metrics_service, simulator_service
            -> idempotency, classifier, stopping_rules, decision_engine
                -> app.domain (types only, no further service imports)
        -> recovery_executor
            -> app.integrations.razorpay (the ONLY place the Razorpay SDK is imported)

`decision_engine` in particular must stay a leaf: it may import app.domain
and nothing else in this package. See app/domain/decision.py docstring.
"""
