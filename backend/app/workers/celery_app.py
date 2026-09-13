"""
Celery application. Start a worker with:

    celery -A app.workers.celery_app worker --loglevel=info

Task modules are discovered via `include=` below rather than relying on
autodiscovery magic — explicit is easier for another agent to trace.
"""

from __future__ import annotations

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "recoverai",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.tasks.process_webhook",
        "app.workers.tasks.execute_action",
        "app.workers.tasks.stale_case_check",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Nothing in this codebase reads a task's AsyncResult — every task
    # persists its outcome to Postgres itself (via audit_service /
    # case_service) instead. Ignoring results avoids Celery opening a
    # result-backend (Redis) pubsub connection on every `.delay()` call,
    # which otherwise hangs/retries for a long time if Redis is down —
    # see recovery_executor.schedule_or_execute's try/except around enqueue.
    task_ignore_result=True,
    # Fail fast (rather than retrying for minutes) if the broker is
    # unreachable when a task is sent — recovery_executor.schedule_or_execute
    # catches this and degrades gracefully instead of crashing the request.
    broker_connection_retry_on_startup=False,
    broker_transport_options={"max_retries": 1, "socket_connect_timeout": 2, "socket_timeout": 2},
    # Scheduled retries use eta; beat provides the safety-net sweep that
    # enforces max-days-open and requeues overdue PENDING attempts.
    beat_schedule={
        "recoverai-stale-case-check": {
            "task": "stale_case_check",
            "schedule": 300.0,
        }
    },
)
