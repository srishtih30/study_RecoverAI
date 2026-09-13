"""
Executes one scheduled/immediate recovery action.

Enqueued by `app.services.recovery_executor.schedule_or_execute` — either
immediately (`.delay(attempt_id)`) or at a future ETA
(`.apply_async(args=[attempt_id], eta=decision.execute_at)`) for delayed
actions like RETRY_LATER. Passes only the attempt's ID (a small
serializable payload), never a database object — per the mandatory rule of
preferring IDs over ORM objects across the Celery boundary.
"""

from __future__ import annotations

from app.db.session import SessionLocal
from app.services import recovery_executor
from app.workers.celery_app import celery_app


@celery_app.task(name="execute_action", bind=True, max_retries=3)
def execute_action(self, attempt_id: str) -> dict:
    db = SessionLocal()
    try:
        attempt = recovery_executor.execute_attempt(db, attempt_id)
        return {"attempt_id": attempt.id, "result": attempt.result.value}
    finally:
        db.close()
